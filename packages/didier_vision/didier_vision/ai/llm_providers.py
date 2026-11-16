"""Fournisseurs LLM de la tête : API Anthropic en direct, OpenRouter en secours.

QUOI : choix du fournisseur (`resolve_provider`), traduction d'une requête au
      format Chat Completions (celui que bâtissent StreamingBrain et
      reflection.build_messages) vers l'API Messages d'Anthropic
      (`to_anthropic_request`), classement des erreurs qui justifient la
      bascule de secours (`is_fallback_error`), et deux adaptateurs aux mêmes
      méthodes (`stream` streamé pour la bouche, `complete` pour la réflexion).
POURQUOI (décision de David du 16/11) : les modèles Claude passent DIRECTEMENT
      par l'API Anthropic (clé de David, crédit prépayé) ; OpenRouter reste (a)
      le SECOURS automatique quand Anthropic échoue — bascule journalisée, la
      parole ne se bloque pas — et (b) le fournisseur de ce qu'Anthropic ne
      fait pas (STT Voxtral, modèles non Claude). Sans clé Anthropic, le
      comportement d'avant est inchangé (OpenRouter seul).
POURQUOI les identifiants de modèle en table : les chaînes de config restent
      celles d'OpenRouter (« anthropic/claude-haiku-5.5 », liste fermée de
      vision_config) ; l'identifiant côté API Anthropic vient de la doc
      officielle (Claude Haiku 5.5 = `claude-haiku-5-5`, sans suffixe de date)
      — jamais deviné. Un modèle absent de la table (ex. openai/gpt-6.1-sol)
      reste chez OpenRouter, quel que soit le réglage.
POURQUOI la réflexion COUPÉE se traduit ici : panne « Didier muet » du 22/10
      (réflexion adaptative de Haiku 5.5 active par défaut, tokens comptés dans
      max_tokens, zéro texte). Côté OpenRouter c'est extra_body
      {"reasoning": {"enabled": false}} ; côté Anthropic `thinking: disabled`
      (Haiku 5.5, accepté jusqu'à l'effort `high`) ou `between_tools` (Sonnet
      5.5, qui refuse `disabled`). Une seule source de vérité : l'extra_body
      de vision_config, traduit par `anthropic_thinking_options`.
SECRETS : la clé n'est JAMAIS journalisée ni mise dans un message d'erreur —
      `describe_error` ne rend que la classe et le code HTTP de l'erreur.
      Import `anthropic`/`openai` DIFFÉRÉ (même patron que llm_stream) : les
      fabriques de client sont injectables, les tests n'appellent aucun réseau.
"""
from __future__ import annotations

import logging
from typing import Callable, Iterator, Optional

logger = logging.getLogger(__name__)

PROVIDER_AUTO = "auto"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_OPENROUTER = "openrouter"
PROVIDER_SETTINGS = (PROVIDER_AUTO, PROVIDER_ANTHROPIC, PROVIDER_OPENROUTER)

# Identifiant OpenRouter (config) -> identifiant de l'API Anthropic. Source : doc
# officielle des modèles Claude (lue le 16/11) — ID exacts, sans suffixe de date.
ANTHROPIC_MODEL_IDS = {
    "anthropic/claude-haiku-5.5": "claude-haiku-5-5",
    "anthropic/claude-sonnet-5.5": "claude-sonnet-5-5",
}
# Sonnet 5.5 refuse `thinking: disabled` (400) : sa forme « réflexion coupée »
# est `between_tools` (sans autre champ, effort <= high).
_THINKING_OFF = {
    "claude-haiku-5-5": {"type": "disabled"},
    "claude-sonnet-5-5": {"type": "between_tools"},
}
# reasoning.effort d'OpenRouter -> output_config.effort d'Anthropic (pas de
# « minimal » chez Anthropic : réflexion coupée + effort low, le plus proche).
_EFFORTS = {"minimal": "low", "low": "low", "medium": "medium", "high": "high"}

_DATA_URL_PREFIX = "data:"


class ProviderConfigError(ValueError):
    """Réglage de fournisseur impossible (inconnu, ou anthropic sans clé)."""


def resolve_provider(setting: str, model: str, anthropic_key_present: bool) -> str:
    """Fournisseur EFFECTIF pour `model` : "anthropic" ou "openrouter".

    auto (défaut) = anthropic si la clé est là ET que le modèle est un Claude
    connu de ANTHROPIC_MODEL_IDS, sinon openrouter (comportement d'avant).
    anthropic explicite sans clé = ProviderConfigError (échec de démarrage
    clair, jamais un Didier qui croit parler à Anthropic). Un modèle non Claude
    reste chez OpenRouter même si anthropic est demandé (journalisé par
    l'appelant via la valeur rendue)."""
    if setting not in PROVIDER_SETTINGS:
        raise ProviderConfigError(
            f"fournisseur LLM {setting!r} inconnu : attendu {' / '.join(PROVIDER_SETTINGS)}")
    if setting == PROVIDER_OPENROUTER or model not in ANTHROPIC_MODEL_IDS:
        return PROVIDER_OPENROUTER
    if anthropic_key_present:
        return PROVIDER_ANTHROPIC
    if setting == PROVIDER_ANTHROPIC:
        raise ProviderConfigError(
            "fournisseur LLM « anthropic » demandé mais clé ANTHROPIC_API_KEY absente "
            "(secrets.env de la tête, cf. vision_config.anthropic_api_key)")
    return PROVIDER_OPENROUTER


def anthropic_thinking_options(anthropic_model: str, extra_body: Optional[dict]) -> dict:
    """Traduit l'extra_body OpenRouter de vision_config en champs de l'API
    Messages (`thinking`, `output_config`). Sans « reasoning » : {} (défauts
    du modèle). reasoning.enabled False, ou effort « minimal » : réflexion
    coupée (forme propre au modèle, cf. _THINKING_OFF) ; effort low/medium/
    high : réflexion adaptative à cet effort."""
    reasoning = (extra_body or {}).get("reasoning")
    if not isinstance(reasoning, dict):
        return {}
    effort = reasoning.get("effort")
    options: dict = {}
    if reasoning.get("enabled") is False or effort == "minimal":
        options["thinking"] = dict(_THINKING_OFF.get(anthropic_model, {"type": "disabled"}))
    elif effort in _EFFORTS:
        options["thinking"] = {"type": "adaptive"}
    if effort in _EFFORTS:
        options["output_config"] = {"effort": _EFFORTS[effort]}
    return options


def _anthropic_content(content):
    """Contenu d'un message Chat Completions -> contenu Messages : une chaîne
    reste une chaîne ; une liste de parties est traduite (texte tel quel,
    image_url data-URL base64 -> bloc image base64)."""
    if isinstance(content, str):
        return content
    blocks = []
    for part in content or []:
        kind = part.get("type")
        if kind == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif kind == "image_url":
            url = part["image_url"]["url"]
            if not url.startswith(_DATA_URL_PREFIX) or ";base64," not in url:
                raise ValueError("image non data-URL base64 : non transmissible à Anthropic")
            media_type, data = url[len(_DATA_URL_PREFIX):].split(";base64,", 1)
            blocks.append({"type": "image",
                           "source": {"type": "base64", "media_type": media_type, "data": data}})
        else:
            raise ValueError(f"partie de message inconnue : {kind!r}")
    return blocks


def _as_blocks(content) -> list:
    return [{"type": "text", "text": content}] if isinstance(content, str) else list(content)


def to_anthropic_request(messages: list) -> tuple:
    """Messages Chat Completions -> (system, messages) de l'API Messages.

    - TOUS les messages `system` (prompt, objets, consigne, situation,
      direction — StreamingBrain les place en tête) sont joints, dans l'ordre,
      en UN system de premier niveau (séparateur ligne vide) ;
    - les tours user/assistant gardent leur ordre ; deux tours consécutifs du
      même rôle sont fusionnés (alternance garantie) ;
    - un historique tronqué (history_limit) qui commencerait par une réplique
      de Didier perd cette réplique de tête : l'API veut un premier tour user."""
    system_parts, turns = [], []
    for message in messages:
        role, content = message["role"], message["content"]
        if role == "system":
            system_parts.append(content)
            continue
        if role not in ("user", "assistant"):
            raise ValueError(f"rôle de message inconnu : {role!r}")
        content = _anthropic_content(content)
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] = _as_blocks(turns[-1]["content"]) + _as_blocks(content)
        else:
            turns.append({"role": role, "content": content})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return "\n\n".join(system_parts), turns


def is_fallback_error(exc: BaseException) -> bool:
    """Vrai si l'échec d'Anthropic justifie la bascule sur OpenRouter.

    Consigne (16/11) : réseau, délai, 429, 5xx. En plus, ce qui rendrait Didier
    muet sans être un défaut de NOTRE requête : clé refusée (401/403),
    identifiants illisibles, compte suspendu, crédit prépayé épuisé (400
    « credit balance »). Une autre 400/404/413/422 = requête fausse de notre
    côté : pas de bascule (OpenRouter échouerait pareil), l'erreur remonte."""
    try:
        import anthropic
    except ImportError:  # pragma: no cover - le client anthropic n'existerait pas non plus
        return False
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError,
                        anthropic.InternalServerError, anthropic.AuthenticationError,
                        anthropic.PermissionDeniedError, anthropic.CredentialsError,
                        anthropic.OrganizationOnHoldError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        status = exc.status_code
        if status in (408, 429) or status >= 500:
            return True
        if status == 400 and "credit balance" in str(getattr(exc, "message", "")).lower():
            return True
    return False


def describe_error(exc: BaseException) -> str:
    """Description SANS contenu d'une erreur fournisseur (classe + code HTTP) :
    c'est elle qu'on journalise à la bascule — jamais str(exc), qui reprend le
    corps de la réponse."""
    status = getattr(exc, "status_code", None)
    return type(exc).__name__ + (f" (HTTP {status})" if isinstance(status, int) else "")


class AnthropicBackend:
    """API Messages d'Anthropic (SDK officiel `anthropic`)."""

    name = PROVIDER_ANTHROPIC

    def __init__(self, model: str, extra_body: Optional[dict], api_key_loader: Callable[[], str],
                 timeout_s: float, connect_timeout_s: float = 3.0, max_retries: int = 0,
                 client_factory=None):
        """`model` = identifiant de CONFIG (OpenRouter), traduit par
        ANTHROPIC_MODEL_IDS. `max_retries` 0 par défaut : le secours, c'est
        OpenRouter, pas trois essais qui retarderaient la parole.
        `api_key_loader` n'est appelé qu'à la construction du vrai client."""
        self.model = ANTHROPIC_MODEL_IDS[model]
        self._options = anthropic_thinking_options(self.model, extra_body)
        self._api_key_loader = api_key_loader
        self._timeout_s = timeout_s
        self._connect_timeout_s = connect_timeout_s
        self._max_retries = max_retries
        self._client_factory = client_factory
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                import anthropic  # import différé, cf. docstring de module

                self._client = anthropic.Anthropic(
                    api_key=self._api_key_loader(), max_retries=self._max_retries,
                    timeout=anthropic.Timeout(self._timeout_s, connect=self._connect_timeout_s))
        return self._client

    def _request(self, messages: list, max_tokens: int) -> dict:
        system, turns = to_anthropic_request(messages)
        request = dict(model=self.model, max_tokens=max_tokens, messages=turns, **self._options)
        if system:
            request["system"] = system
        return request

    def stream(self, messages: list, max_tokens: int) -> Iterator[str]:
        """Deltas de texte, au fil de l'eau (blocs de réflexion ignorés)."""
        self.last_stop_reason = None
        with self._get_client().messages.stream(**self._request(messages, max_tokens)) as stream:
            for text in stream.text_stream:
                if text:
                    yield text
            self.last_stop_reason = stream.get_final_message().stop_reason

    def complete(self, messages: list, max_tokens: int) -> tuple:
        """(texte, stop_reason) d'un appel non streamé — blocs lus par TYPE (une
        réponse peut commencer par des blocs de réflexion)."""
        response = self._get_client().messages.create(**self._request(messages, max_tokens))
        text = "".join(block.text for block in response.content if block.type == "text")
        return text, response.stop_reason


class OpenRouterBackend:
    """OpenRouter via le client OpenAI officiel (base_url) — le chemin d'avant."""

    name = PROVIDER_OPENROUTER

    def __init__(self, model: str, base_url: str, extra_body: Optional[dict],
                 api_key_loader: Callable[[], str], timeout_s: Optional[float] = None,
                 max_retries: Optional[int] = None, client_factory=None):
        self.model = model
        self._base_url = base_url
        self._extra_body = extra_body
        self._api_key_loader = api_key_loader
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._client_factory = client_factory
        self._client = None

    def _get_client(self):
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                from openai import OpenAI  # import différé, cf. docstring de module

                kwargs = {"base_url": self._base_url, "api_key": self._api_key_loader()}
                if self._timeout_s is not None:
                    kwargs["timeout"] = self._timeout_s
                if self._max_retries is not None:
                    kwargs["max_retries"] = self._max_retries
                self._client = OpenAI(**kwargs)
        return self._client

    def _request(self, messages: list, max_tokens: int, **extra) -> dict:
        request = dict(model=self.model, messages=messages, max_tokens=max_tokens, **extra)
        if self._extra_body:
            request["extra_body"] = self._extra_body
        return request

    def stream(self, messages: list, max_tokens: int) -> Iterator[str]:
        self.last_stop_reason = None
        stream = self._get_client().chat.completions.create(
            **self._request(messages, max_tokens, stream=True))
        for chunk in stream:
            if not chunk.choices:
                # Chunk sans choix (ex. chunk final d'usage d'OpenRouter) :
                # rien à lire, et choices[0] lèverait IndexError.
                continue
            self.last_stop_reason = (getattr(chunk.choices[0], "finish_reason", None)
                                     or self.last_stop_reason)
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def complete(self, messages: list, max_tokens: int) -> tuple:
        response = self._get_client().chat.completions.create(**self._request(messages, max_tokens))
        choices = getattr(response, "choices", None)
        if not choices:
            return "", None
        return choices[0].message.content or "", getattr(choices[0], "finish_reason", None)


def stream_with_fallback(backends: list, messages: list, max_tokens: int,
                         used: Optional[list] = None) -> Iterator[str]:
    """Deltas du premier fournisseur qui répond. Bascule sur le suivant SEULEMENT
    si l'échec arrive AVANT le premier delta (après, des mots sont déjà partis
    au haut-parleur : on ne recommence pas une réplique) et si
    is_fallback_error l'autorise ; journalisée en WARNING sans contenu.
    `used` (liste) reçoit le fournisseur (objet) qui a effectivement servi."""
    for index, backend in enumerate(backends):
        produced = False
        deltas = backend.stream(messages, max_tokens)
        try:
            for delta in deltas:
                if not produced and used is not None:
                    used.append(backend)
                produced = True
                yield delta
            if not produced and used is not None:
                used.append(backend)
            return
        except Exception as exc:
            last = index == len(backends) - 1
            if produced or last or not is_fallback_error(exc):
                raise
            logger.warning("LLM %s (%s) en échec : %s — bascule de secours sur %s (%s)",
                           backend.name, backend.model, describe_error(exc),
                           backends[index + 1].name, backends[index + 1].model)
        finally:
            # Réplique interrompue (« stop » : ConversationEngine ferme le flux) ou
            # échec : le flux HTTP du fournisseur est fermé tout de suite.
            deltas.close()


def complete_with_fallback(backends: list, messages: list, max_tokens: int) -> tuple:
    """(texte, stop_reason, fournisseur) du premier fournisseur qui répond —
    mêmes règles de bascule que stream_with_fallback."""
    for index, backend in enumerate(backends):
        try:
            text, stop_reason = backend.complete(messages, max_tokens)
            return text, stop_reason, backend.name
        except Exception as exc:
            if index == len(backends) - 1 or not is_fallback_error(exc):
                raise
            logger.warning("LLM %s (%s) en échec : %s — bascule de secours sur %s (%s)",
                           backend.name, backend.model, describe_error(exc),
                           backends[index + 1].name, backends[index + 1].model)
    raise RuntimeError("aucun fournisseur LLM")  # pragma: no cover - liste vide


def build_backends(provider: str, model: str, *, base_url: str, extra_body: Optional[dict],
                   openrouter_key_loader: Callable[[], str],
                   anthropic_key_loader: Callable[[], str], timeout_s: float,
                   openrouter_timeout_s: Optional[float] = None,
                   openrouter_max_retries: Optional[int] = None,
                   anthropic_client_factory=None, openrouter_client_factory=None) -> list:
    """Chaîne de fournisseurs : [Anthropic, OpenRouter (secours)] si provider
    vaut anthropic, sinon [OpenRouter] seul (comportement d'avant)."""
    openrouter = OpenRouterBackend(model, base_url, extra_body, openrouter_key_loader,
                                   timeout_s=openrouter_timeout_s,
                                   max_retries=openrouter_max_retries,
                                   client_factory=openrouter_client_factory)
    if provider != PROVIDER_ANTHROPIC:
        return [openrouter]
    return [AnthropicBackend(model, extra_body, anthropic_key_loader, timeout_s,
                             client_factory=anthropic_client_factory), openrouter]
