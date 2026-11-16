"""Tests de didier_vision/ai/llm_providers.py et du branchement fournisseur (16/11).

Valeurs ATTENDUES GRAVÉES (jamais recalculées avec la fonction testée) : choix du
fournisseur, identifiants de modèle de l'API Anthropic, forme exacte de la requête,
erreurs qui basculent ou non sur OpenRouter. Aucun appel réseau sortant : faux
clients, ou VRAI client anthropic pointé sur un port local fermé (connexion refusée
en quelques ms) pour prouver qu'aucune ligne de journal, à aucun niveau, ne porte la
clé.
"""
import logging

import anthropic
import httpx2
import pytest

from didier_vision.ai import llm_providers as lp
from didier_vision.ai.llm_stream import StreamingBrain
from didier_vision.ai.reflection import Reflector
from didier_vision.db.chat_db import ChatDB
from didier_vision.vision_config import anthropic_api_key, anthropic_key_present

# Clé FACTICE (sans le préfixe d'une vraie : rien à signaler aux scanners de secrets) : ne doit
# apparaître dans AUCUN journal.
FAUSSE_CLE = "cle-anthropic-FACTICE-de-test-qui-ne-doit-jamais-etre-journalisee-0123456789"
HAIKU = "anthropic/claude-haiku-5.5"
SONNET = "anthropic/claude-sonnet-5.5"


# --- choix du fournisseur -------------------------------------------------------------

@pytest.mark.parametrize("reglage, modele, cle, attendu", [
    ("auto", HAIKU, True, "anthropic"),
    ("auto", HAIKU, False, "openrouter"),          # sans clé : comportement d'avant
    ("auto", SONNET, True, "anthropic"),
    ("auto", "openai/gpt-6.1-sol", True, "openrouter"),   # pas un Claude : OpenRouter
    ("openrouter", HAIKU, True, "openrouter"),
    ("anthropic", HAIKU, True, "anthropic"),
    ("anthropic", "openai/gpt-6.1-sol", True, "openrouter"),
])
def test_choix_du_fournisseur(reglage, modele, cle, attendu):
    assert lp.resolve_provider(reglage, modele, cle) == attendu


def test_anthropic_force_sans_cle_est_un_echec_explicite():
    with pytest.raises(lp.ProviderConfigError, match="ANTHROPIC_API_KEY absente"):
        lp.resolve_provider("anthropic", HAIKU, False)


def test_reglage_inconnu_refuse():
    with pytest.raises(lp.ProviderConfigError, match="inconnu"):
        lp.resolve_provider("openai", HAIKU, True)


def test_identifiants_api_anthropic_graves():
    # Doc officielle + models.retrieve vérifiés le 16/11 : sans suffixe de date.
    assert lp.ANTHROPIC_MODEL_IDS == {HAIKU: "claude-haiku-5-5", SONNET: "claude-sonnet-5-5"}


# --- réflexion coupée / effort ----------------------------------------------------------

def test_reflexion_coupee_haiku_bouche():
    # config["chat_llm_extra_body"] : panne « Didier muet » du 22/10 si la réflexion tourne.
    assert lp.anthropic_thinking_options("claude-haiku-5-5", {"reasoning": {"enabled": False}}) \
        == {"thinking": {"type": "disabled"}}


def test_reflexion_minimale_sonnet_coupee_sous_sa_forme_propre():
    # Sonnet 5.5 refuse `disabled` (400) : `between_tools`, effort low.
    assert lp.anthropic_thinking_options("claude-sonnet-5-5", {"reasoning": {"effort": "minimal"}}) \
        == {"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}}


def test_reflexion_effort_medium_metteur_en_scene():
    assert lp.anthropic_thinking_options("claude-haiku-5-5", {"reasoning": {"effort": "medium"}}) \
        == {"thinking": {"type": "adaptive"}, "output_config": {"effort": "medium"}}


def test_sans_reasoning_aucun_champ():
    assert lp.anthropic_thinking_options("claude-haiku-5-5", None) == {}


# --- traduction de la requête -------------------------------------------------------------

def test_traduction_systemes_joints_historique_alterne():
    system, turns = lp.to_anthropic_request([
        {"role": "system", "content": "P"},
        {"role": "system", "content": "OBJ"},
        {"role": "assistant", "content": "réplique tronquée"},   # tête d'historique coupé
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "c"},
        {"role": "user", "content": "d"},
    ])
    assert system == "P\n\nOBJ"
    assert turns == [
        {"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]},
        {"role": "assistant", "content": "c"},
        {"role": "user", "content": "d"},
    ]


def test_traduction_image_data_url():
    _, turns = lp.to_anthropic_request([{"role": "user", "content": [
        {"type": "text", "text": "T"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,QUJD"}},
    ]}])
    assert turns == [{"role": "user", "content": [
        {"type": "text", "text": "T"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}},
    ]}]


# --- erreurs qui basculent ----------------------------------------------------------------

_REQ = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status(cls, code, message="erreur"):
    return cls(message, response=httpx2.Response(code, request=_REQ), body=None)


@pytest.mark.parametrize("exc, attendu", [
    (anthropic.APIConnectionError(request=_REQ), True),
    (anthropic.APITimeoutError(request=_REQ), True),
    (_status(anthropic.RateLimitError, 429), True),
    (_status(anthropic.InternalServerError, 500), True),
    (_status(anthropic.APIStatusError, 529), True),            # surcharge
    (_status(anthropic.AuthenticationError, 401), True),       # clé refusée
    (_status(anthropic.PermissionDeniedError, 403), True),
    (_status(anthropic.BadRequestError, 400, "Your credit balance is too low"), True),
    (_status(anthropic.BadRequestError, 400, "messages: field required"), False),
    (_status(anthropic.NotFoundError, 404), False),
    (ValueError("bug"), False),
])
def test_erreurs_qui_basculent(exc, attendu):
    assert lp.is_fallback_error(exc) is attendu


def test_description_d_erreur_sans_contenu():
    exc = _status(anthropic.RateLimitError, 429, "corps de réponse " + FAUSSE_CLE)
    assert lp.describe_error(exc) == "RateLimitError (HTTP 429)"


# --- faux fournisseurs -------------------------------------------------------------------

class _Fournisseur:
    def __init__(self, name, deltas=(), echec=None, echec_apres=None):
        self.name, self.model = name, name + "-m"
        self._deltas, self._echec, self._echec_apres = list(deltas), echec, echec_apres
        self.appels = 0

    def stream(self, messages, max_tokens):
        self.appels += 1
        if self._echec is not None:
            raise self._echec
        for i, d in enumerate(self._deltas):
            if self._echec_apres is not None and i == self._echec_apres:
                raise anthropic.APIConnectionError(request=_REQ)
            yield d

    def complete(self, messages, max_tokens):
        self.appels += 1
        if self._echec is not None:
            raise self._echec
        return "".join(self._deltas), "end_turn"


def test_bascule_avant_le_premier_mot_journalisee(caplog):
    a = _Fournisseur("anthropic", echec=anthropic.APIConnectionError(request=_REQ))
    o = _Fournisseur("openrouter", ["Bon", "jour"])
    used = []
    with caplog.at_level(logging.WARNING, logger="didier_vision.ai.llm_providers"):
        assert list(lp.stream_with_fallback([a, o], [], 10, used=used)) == ["Bon", "jour"]
    assert used == [o]
    assert ("LLM anthropic (anthropic-m) en échec : APIConnectionError — bascule de secours "
            "sur openrouter (openrouter-m)") in caplog.text


def test_pas_de_bascule_apres_le_premier_mot():
    a = _Fournisseur("anthropic", ["Bon", "jour"], echec_apres=1)
    o = _Fournisseur("openrouter", ["X"])
    recu = []
    with pytest.raises(anthropic.APIConnectionError):
        for d in lp.stream_with_fallback([a, o], [], 10):
            recu.append(d)
    assert recu == ["Bon"] and o.appels == 0


def test_pas_de_bascule_sur_requete_fausse():
    a = _Fournisseur("anthropic", echec=_status(anthropic.BadRequestError, 400, "messages: bad"))
    o = _Fournisseur("openrouter", ["X"])
    with pytest.raises(anthropic.BadRequestError):
        list(lp.stream_with_fallback([a, o], [], 10))
    assert o.appels == 0


def test_bascule_non_streamee_reflexion():
    a = _Fournisseur("anthropic", echec=_status(anthropic.InternalServerError, 503))
    o = _Fournisseur("openrouter", ['{"situation": "s"}'])
    assert lp.complete_with_fallback([a, o], [], 10) == ('{"situation": "s"}', "end_turn", "openrouter")


# --- StreamingBrain / Reflector branchés sur Anthropic (faux client SDK) --------------------

class _FauxFlux:
    def __init__(self, morceaux):
        self.text_stream = iter(morceaux)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return type("M", (), {"stop_reason": "end_turn"})()


class _FauxMessages:
    def __init__(self, morceaux):
        self._morceaux, self.appels = morceaux, []

    def stream(self, **kwargs):
        self.appels.append(kwargs)
        return _FauxFlux(self._morceaux)

    def create(self, **kwargs):
        self.appels.append(kwargs)
        blocs = [type("B", (), {"type": "thinking"})(),
                 type("B", (), {"type": "text", "text": '{"situation": "rue calme"}'})()]
        return type("R", (), {"content": blocs, "stop_reason": "end_turn"})()


class _FauxAnthropic:
    def __init__(self, morceaux=("Salut", " David.")):
        self.messages = _FauxMessages(list(morceaux))


def test_bouche_sur_anthropic_requete_gravee(tmp_path):
    ChatDB.configure(str(tmp_path / "chat.db"))
    client = _FauxAnthropic()
    brain = StreamingBrain(model=HAIKU, base_url="https://or", system_prompt="PERSONA",
                           max_tokens=300, extra_body={"reasoning": {"enabled": False}},
                           provider="anthropic", anthropic_client_factory=lambda: client,
                           client_factory=lambda: pytest.fail("OpenRouter appelé"))
    brain.set_objects_prompt("OBJETS")
    assert "".join(brain.stream_reply("Bonjour", extra_system="sois triste")) == "Salut David."
    assert brain.last_provider == "anthropic"
    assert brain.providers == (("anthropic", "claude-haiku-5-5"), ("openrouter", HAIKU))
    assert client.messages.appels == [{
        "model": "claude-haiku-5-5", "max_tokens": 300,
        "messages": [{"role": "user", "content": "Bonjour"}],
        "thinking": {"type": "disabled"},
        "system": ("PERSONA\n\nOBJETS\n\nConsigne de mise en scène (à jouer, jamais à "
                   "prononcer) : sois triste"),
    }]


def test_reflexion_sur_anthropic_lit_les_blocs_par_type():
    client = _FauxAnthropic()
    r = Reflector(HAIKU, "https://or", {"reasoning": {"effort": "medium"}}, 3000,
                  provider="anthropic", anthropic_client_factory=lambda: client,
                  client_factory=lambda: pytest.fail("OpenRouter appelé"))
    assert r.reflect([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]).situation \
        == "rue calme"
    assert r.last_provider == "anthropic"
    assert client.messages.appels[0]["thinking"] == {"type": "adaptive"}
    assert client.messages.appels[0]["output_config"] == {"effort": "medium"}


def test_reflexion_profonde_non_claude_reste_chez_openrouter():
    r = Reflector(HAIKU, "https://or", None, 3000, provider="anthropic",
                  anthropic_client_factory=lambda: pytest.fail("Anthropic appelé"))
    assert [b.name for b in r._backends("openai/gpt-6.1-sol", None)] == ["openrouter"]


# --- clé : lecture, et JAMAIS dans un journal ----------------------------------------------

def test_lecture_de_la_cle_formats_shell(tmp_path):
    f = tmp_path / "secrets.env"
    f.write_text("# commentaire\nAUTRE=x\nexport ANTHROPIC_API_KEY='" + FAUSSE_CLE + "'\n")
    env = {"DIDIER_SECRETS_ENV": str(f)}
    assert anthropic_api_key(env) == FAUSSE_CLE
    assert anthropic_key_present(env) is True


def test_cle_absente_message_sans_valeur(tmp_path):
    f = tmp_path / "secrets.env"
    f.write_text("AUTRE=" + FAUSSE_CLE + "\nANTHROPIC_API_KEY=\n")
    env = {"DIDIER_SECRETS_ENV": str(f)}
    with pytest.raises(KeyError) as err:
        anthropic_api_key(env)
    assert FAUSSE_CLE not in str(err.value)
    assert anthropic_key_present(env) is False
    assert anthropic_key_present({"DIDIER_SECRETS_ENV": str(tmp_path / "absent")}) is False


def test_aucun_journal_ne_porte_la_cle(tmp_path, caplog, monkeypatch):
    """VRAI client anthropic, VRAIE clé factice, serveur injoignable (port local fermé) :
    échec réseau -> bascule sur un faux OpenRouter. Journal capturé à TOUS les niveaux
    (SDK et transport compris) : la clé n'y est jamais."""
    ChatDB.configure(str(tmp_path / "chat.db"))
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ANTHROPIC_LOG", "debug")

    class _FauxOpenRouter:
        """client.chat.completions.create(stream=True) -> deux morceaux de texte."""
        def __init__(self):
            def morceau(texte):
                choix = type("C", (), {"delta": type("D", (), {"content": texte})(),
                                       "finish_reason": None})()
                return type("K", (), {"choices": [choix]})()
            completions = type("Co", (), {"create": staticmethod(
                lambda **kw: [morceau("Je "), morceau("parle.")])})()
            self.chat = type("Ch", (), {"completions": completions})()

    brain = StreamingBrain(model=HAIKU, base_url="https://or", system_prompt="P",
                           extra_body={"reasoning": {"enabled": False}}, provider="anthropic",
                           anthropic_key_loader=lambda: FAUSSE_CLE,
                           client_factory=_FauxOpenRouter)
    with caplog.at_level(logging.DEBUG):
        texte = "".join(brain.stream_reply("Bonjour"))
    assert texte == "Je parle."
    assert brain.last_provider == "openrouter"
    assert "bascule de secours sur openrouter" in caplog.text
    # Le journal capturé contient bien le DÉBOGAGE du SDK (requête, en-têtes compris) :
    # sinon l'absence de la clé ne prouverait rien.
    assert any(r.name.startswith("anthropic") and r.levelno == logging.DEBUG for r in caplog.records)
    assert FAUSSE_CLE not in caplog.text
    assert FAUSSE_CLE[-20:] not in caplog.text
