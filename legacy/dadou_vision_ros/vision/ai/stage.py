"""Régie du chat — état PUR partagé entre les topics de régie et le moteur de
conversation (lot R3 « Chantiers », 2026-10-14).

QUOI : StageState porte les trois choses qu'une régie peut imposer à la
       conversation SANS passer par le micro (spec fermée :
       dadou_robot_ros/docs/etude-repetition-simulee.md §13.4 point 3 et §13.6) :
       - la file des textes TAPÉS (topic `chat_text`, clavier de la régie) :
         « entendus » sans micro ni STT ;
       - la CONSIGNE de jeu courante (topic `chat_instruction`), injectée
         comme second message system à chaque tour (cf. llm_stream) ;
       - la PANNE de conversation courante (topic `rehearsal/chat_fault`,
         publié par le régisseur de la répétition simulée) : delay, garble,
         deaf, mute, phantom.
       Plus les décodeurs JSON de ces trois topics et l'encodage du
       transcript, pour que chat_node reste un node FIN (I/O seulement).
       Depuis le 2026-10-23 (metteur en scène intérieur, lot P,
       dadou_robot_ros/docs/spec-metteur-en-scene.md) : le TABLEAU DE
       SITUATION (topic chat_situation, relu à chaque tour, périmé en
       SITUATION_TTL_S) et la DIRECTION du tour spontané (topic chat_prompt,
       un seul emplacement, périmée en PROMPT_TTL_S) — même verrou, mêmes
       bornes tenues côté consommateur. Depuis le 2026-10-31 (lot M1 « Aller
       voir ») : le décodeur du vocabulaire d'objets (`rehearsal/objects`),
       sans état ici — la liste formatée vit dans StreamingBrain.
POURQUOI un module PUR (aucun rclpy) : même règle que _chat_wiring et
       arbitration — les bornes de sécurité de ce canal (plafond 60 s de la
       panne, péremption 120 s de la consigne, phantom ponctuel) doivent être
       testées en CI, sans ROS ni matériel (cf. vision/tests/unit/test_stage.py).
POURQUOI un threading.Lock (et pas l'argument « affectation atomique sous le
       GIL » de chat_node._animation_state) : ÉCRIT par le thread rclpy.spin
       (callbacks des trois topics) et LU par le thread de conversation
       (ConversationEngine.run_forever) — mais ici les lectures MODIFIENT
       (pop de la file, retombée sur "pass" à l'échéance) et l'état tient en
       plusieurs champs liés (op + params + échéance) : une lecture déchirée
       pourrait appliquer les params d'une panne à l'op d'une autre.
POURQUOI les bornes sont tenues ICI, côté consommateur, en plus du
       régisseur : ce canal n'a pas de chien de garde (c'est du texte, pas des
       roues, cf. §13.4) — si le régisseur meurt en pleine panne, son "pass"
       de fin n'arrive jamais. Le plafond local (FAULT_MAX_S) et la
       péremption de la consigne (INSTRUCTION_TTL_S) font retomber l'état
       SEULS, comme le deadman des roues.
"""
from __future__ import annotations

import json
import random
import threading
from collections import deque
from typing import Optional, Sequence, Tuple

from vision.ai.reflection_contract import SITUATION_TTL_S

# Péremption de la direction d'un tour SPONTANÉ (s, topic chat_prompt, lot
# P3 du metteur en scène intérieur) : la direction est servie quand l'écoute
# a duré au moins 3 s sans parole (SPONTANEOUS_MIN_SILENCE_S, conversation) —
# au-delà de 8 s d'attente (Didier parlait, quelqu'un parlait, chat OFF), la
# scène a bougé : une vieille direction ferait relancer Didier à contretemps.
# Elle se périme, la réflexion en proposera une neuve.
PROMPT_TTL_S = 8.0

# Péremption LOCALE de la consigne (s) : la lubie la plus longue du régisseur
# dure 120 s (FAULT_MAX_DURATION_S["lubie"], §13.4) — au-delà, une consigne
# encore posée signifie que le "" de levée s'est perdu (régisseur mort) : elle
# tombe seule, Didier ne reste pas coincé dans un délire pour toute la séance.
INSTRUCTION_TTL_S = 120.0

# Plafond LOCAL d'une panne de conversation (s), quel que soit `until_ms` reçu
# (None, absurde ou trop grand) : même borne que FAULT_MAX_DURATION_S["chat"]
# côté régisseur — tenue des DEUX côtés (§13.4 point 3).
FAULT_MAX_S = 60.0

# Opérations de panne reconnues (contrat JSON gravé dans les tests des deux
# dépôts, mêmes chaînes que le régisseur) — liste FERMÉE.
FAULT_OPS = ("pass", "delay", "garble", "deaf", "mute", "phantom")

# Rôles du transcript (topic `chat_transcript`, §13.6) : "david" = ce que
# Didier a COMPRIS (après garble), "didier" = chaque phrase qu'il dit.
ROLE_DAVID = "david"
ROLE_DIDIER = "didier"

# Contresens d'un whisper `tiny` sur du bruit de rue (panne `garble`, bug n°17
# du catalogue §13.5) — brouillons d'atelier, à valider par David. Deux
# familles, toutes deux VÉCUES avec whisper : les hallucinations de génériques
# (le modèle a appris sur des vidéos sous-titrées et les ressort sur du
# silence ou du bruit) et les contresens de phrase courte. Crédibles d'abord :
# Didier doit pouvoir y répondre sérieusement, c'est de là que vient le drôle.
GARBLE_TEXTS = (
    "Il parle d'Astérix ?",
    "Sous-titres réalisés par la communauté d'Amara.org",
    "Merci d'avoir regardé cette vidéo !",
    "N'oubliez pas de vous abonner à la chaîne.",
    "C'est combien le kilo de boulons ?",
    "Tu as vu ma tante Ginette ?",
    "Le chien a mangé la télécommande.",
    "Il paraît qu'il pleut des grenouilles à Rezé.",
)


def garble_text(rng: random.Random, texts: Optional[Sequence[str]] = None) -> str:
    """Tire un contresens : dans `texts` (params.texts de la panne) s'il est
    fourni, sinon dans la liste gravée GARBLE_TEXTS. `rng` INJECTÉ (jamais le
    module random global) : déterministe en test avec une graine, et la
    répétition reste rejouable si un jour la graine du régisseur est relayée."""
    return rng.choice(list(texts) if texts else GARBLE_TEXTS)


def fault_duration_s(until_ms) -> float:
    """Durée (s) d'une panne à partir du champ `until_ms` du contrat. C'est
    une DURÉE relative à la réception (même convention que les ordres relais
    du régisseur, robot_rehearsal/contracts.py : `"until_ms": durée` — les
    horloges du Pi vision et du conteneur sim ne sont pas partagées, un
    instant absolu n'aurait pas de sens). None, booléen, non-nombre, NaN,
    ≤ 0 ou au-delà du plafond = LE PLAFOND : une valeur absurde ne doit
    jamais produire une panne plus longue que FAULT_MAX_S."""
    if (isinstance(until_ms, bool) or not isinstance(until_ms, (int, float))
            or not 0 < until_ms <= FAULT_MAX_S * 1000):
        return FAULT_MAX_S
    return until_ms / 1000.0


def _validate_fault_params(op: str, params) -> dict:
    """Params NORMALISÉS de la panne `op` (seules les clés connues sont
    gardées), ou ValueError avec un message précis — appelée AVANT tout effet
    sur l'état (même règle que FaultRelay.set_op côté robot : un ordre refusé
    ne change pas le régime en cours)."""
    if op not in FAULT_OPS:
        raise ValueError(f"panne chat : op inconnue {op!r} — attendues : {list(FAULT_OPS)}")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError(f"panne chat {op} : params doit être un objet, reçu {params!r}")
    if op == "delay":
        delay_ms = params.get("delay_ms")
        # Borne haute = le plafond de la panne : le sommeil est fait par le
        # thread de conversation (time.sleep, non interruptible) — un
        # delay_ms absurde le gèlerait bien au-delà de la vie de la panne.
        if (isinstance(delay_ms, bool) or not isinstance(delay_ms, (int, float))
                or not 1 <= delay_ms <= FAULT_MAX_S * 1000):
            raise ValueError(
                f"panne chat delay : delay_ms doit être un entier dans "
                f"[1, {int(FAULT_MAX_S * 1000)}], reçu {delay_ms!r}")
        return {"delay_ms": int(delay_ms)}
    if op == "garble":
        texts = params.get("texts")
        if texts is None:
            return {}
        if (not isinstance(texts, list) or not texts
                or not all(isinstance(t, str) and t.strip() for t in texts)):
            raise ValueError(
                f"panne chat garble : texts doit être une liste NON VIDE de "
                f"chaînes non vides, reçu {texts!r}")
        return {"texts": [t.strip() for t in texts]}
    if op == "phantom":
        text = params.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"panne chat phantom : text doit être une chaîne non vide, reçu {text!r}")
        return {"text": text.strip()}
    # pass/deaf/mute : aucun paramètre (ceux reçus sont ignorés).
    return {}


class StageState:
    """État de régie du chat, protégé par un verrou (cf. docstring de module).
    Toutes les méthodes datées prennent `now_s` en argument (horloge
    MONOTONE de l'appelant, time.monotonic() en prod) : aucune lecture
    d'horloge ici, les bornes se testent à la seconde près."""

    def __init__(self, rng: Optional[random.Random] = None):
        self._lock = threading.Lock()
        # File NON bornée : elle n'est remplie que par un humain au clavier
        # (et par phantom, ponctuel) — un tour la vide d'un texte à la fois.
        self._texts: deque = deque()
        self._instruction: Optional[str] = None
        self._instruction_deadline_s = 0.0
        self._fault_op = "pass"
        self._fault_params: dict = {}
        self._fault_deadline_s: Optional[float] = None
        # Tableau de situation (topic chat_situation) : texte + heure de
        # RÉCEPTION (horloge locale — l'horodatage du payload vient d'une
        # autre machine, cf. reflection_contract).
        self._situation: Optional[str] = None
        self._situation_at_s = 0.0
        # Tour spontané (topic chat_prompt) : UN seul emplacement, cf. push_prompt.
        self._prompt: Optional[str] = None
        self._prompt_at_s = 0.0
        # Tirage des contresens (garble) : utilisé par le SEUL thread de
        # conversation, d'où l'absence de verrou dessus.
        self.rng = rng if rng is not None else random.Random()

    # --- Textes tapés (topic chat_text, et phantom) -----------------------

    def push_text(self, text: str) -> None:
        """Enfile un texte « entendu » sans micro. Vide (après strip) =
        ValueError : un Entrée sans texte sur la console ne doit pas coûter un
        appel LLM ni faire répondre Didier au silence."""
        text = (text or "").strip()
        if not text:
            raise ValueError("texte tapé vide ignoré")
        with self._lock:
            self._texts.append(text)

    def pop_text(self) -> Optional[str]:
        """Le plus ancien texte en attente, ou None."""
        with self._lock:
            return self._texts.popleft() if self._texts else None

    def has_text(self) -> bool:
        """Sondage SANS consommer (attente « micro mort » du moteur, cf.
        ConversationEngine._wait_dead_mic_backoff)."""
        with self._lock:
            return bool(self._texts)

    # --- Consigne de jeu (topic chat_instruction) --------------------------

    def set_instruction(self, text: str, now_s: float) -> None:
        """Pose la consigne courante (péremption à now_s + INSTRUCTION_TTL_S),
        ou la LÈVE si `text` est vide (le "" de fin de lubie du régisseur)."""
        text = (text or "").strip()
        with self._lock:
            if text:
                self._instruction = text
                self._instruction_deadline_s = now_s + INSTRUCTION_TTL_S
            else:
                self._instruction = None

    def instruction(self, now_s: float) -> Optional[str]:
        """Consigne en vigueur, ou None (jamais posée, levée, ou PÉRIMÉE —
        auquel cas elle est oubliée pour de bon)."""
        with self._lock:
            if self._instruction is not None and now_s >= self._instruction_deadline_s:
                self._instruction = None
            return self._instruction

    # --- Tableau de situation (topic chat_situation, metteur en scène) -----

    def set_situation(self, text: str, now_s: float) -> None:
        """Range le dernier tableau reçu. Vide = tableau vide (la réflexion
        n'a rien à dire) : la parole retire le bloc du prompt."""
        text = (text or "").strip()
        with self._lock:
            self._situation = text or None
            self._situation_at_s = now_s

    def situation(self, now_s: float) -> Optional[str]:
        """Tableau en vigueur, ou None (vide, jamais reçu, ou reçu il y a plus
        de SITUATION_TTL_S). La réflexion republie toutes les secondes : un
        tableau qui vieillit signifie qu'elle est morte — Didier parle alors
        sans, jamais avec une vision du monde figée (une personne partie
        depuis 30 s dont il parlerait encore)."""
        with self._lock:
            if self._situation is None or now_s - self._situation_at_s > SITUATION_TTL_S:
                return None
            return self._situation

    # --- Tour spontané (topic chat_prompt, metteur en scène) ---------------

    def push_prompt(self, direction: str, now_s: float) -> None:
        """Pose la direction du prochain tour spontané. UN SEUL emplacement :
        la plus récente REMPLACE l'ancienne (une vieille direction n'a plus
        de valeur, et deux tours spontanés d'affilée n'ont pas de sens).
        Vide = ValueError (même règle que push_text : rien à faire avancer)."""
        direction = (direction or "").strip()
        if not direction:
            raise ValueError("direction de tour spontané vide ignorée")
        with self._lock:
            self._prompt = direction
            self._prompt_at_s = now_s

    def pop_prompt(self, now_s: float) -> Optional[str]:
        """Consomme la direction en attente, ou None (vide, ou plus vieille
        que PROMPT_TTL_S — auquel cas elle est jetée pour de bon)."""
        with self._lock:
            direction, self._prompt = self._prompt, None
            if direction is None or now_s - self._prompt_at_s > PROMPT_TTL_S:
                return None
            return direction

    def clear_prompt(self) -> None:
        """Vide l'emplacement du tour spontané. Appelé dès qu'un énoncé de
        David est servi (ConversationEngine._reply_with_stage). Revue
        adversariale du 23/10 (I7) : une direction calculée AVANT sa
        dernière réplique (« demande-lui son prénom ») était jouée APRÈS,
        à contretemps — David venait justement de le donner."""
        with self._lock:
            self._prompt = None

    # --- Panne de conversation (topic rehearsal/chat_fault) ----------------

    def set_fault(self, op: str, params, until_ms, now_s: float) -> None:
        """Arme la panne `op` pour fault_duration_s(until_ms) (plafonnée à
        FAULT_MAX_S). Params validés AVANT tout effet (ValueError, état
        inchangé). "pass" désarme. `phantom` est PONCTUEL : son texte est
        enfilé comme un énoncé entendu et la panne en cours n'est PAS
        touchée — un fantôme est un événement, pas un régime (le régisseur
        publie de toute façon "pass" à la fin de chaque panne chat, et ses
        pannes chat ne se chevauchent pas : cible d'exclusion `chat`)."""
        params = _validate_fault_params(op, params)
        if op == "phantom":
            self.push_text(params["text"])
            return
        with self._lock:
            self._fault_op = op
            self._fault_params = params
            self._fault_deadline_s = None if op == "pass" else now_s + fault_duration_s(until_ms)

    def fault(self, now_s: float) -> Tuple[str, dict]:
        """(op, params) en vigueur ; retombe SEUL sur ("pass", {}) à
        l'échéance (régisseur mort = la panne ne reste pas armée). params
        est une COPIE : l'appelant ne touche jamais l'état sous verrou."""
        with self._lock:
            if self._fault_deadline_s is not None and now_s >= self._fault_deadline_s:
                self._fault_op = "pass"
                self._fault_params = {}
                self._fault_deadline_s = None
            return self._fault_op, dict(self._fault_params)


# --- Décodage des topics de régie (même esprit que
# _chat_wiring.decode_persona_command : jamais d'exception autre que
# ValueError, le node la transforme en warning) -----------------------------

def decode_text_payload(raw) -> str:
    """Payload de `chat_text` / `chat_instruction` -> texte rogné. JSON
    toléré comme brut : le régisseur et la console web publient
    json.dumps(texte) ; un `ros2 topic pub` de débogage envoie souvent du
    brut. Un JSON qui n'est PAS une chaîne (42, true, null…) est gardé tel
    que tapé : c'est un texte, pas une valeur. Peut renvoyer "" (= consigne
    levée pour chat_instruction ; refusé par push_text pour chat_text)."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        value = raw
    if not isinstance(value, str):
        value = raw
    return str(value if value is not None else "").strip()


def decode_fault_command(raw) -> Tuple[str, dict, object]:
    """Payload de `rehearsal/chat_fault` -> (op, params, until_ms).
    Contrat (§13.4 point 3) : objet JSON {"op", "params", "until_ms"} ; params
    absent/null = {} ; until_ms rendu TEL QUEL (None ou absurde = plafond,
    décidé par StageState.set_fault, qui valide aussi les params par op).
    ValueError avec un message précis sur tout le reste — PAS de forme brute
    ici : une panne sans structure n'a pas de sens, mieux vaut la refuser
    bruyamment que de deviner."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"panne chat illisible (objet JSON attendu) : {raw!r}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"panne chat : objet JSON attendu, reçu {value!r}")
    op = value.get("op")
    if op not in FAULT_OPS:
        raise ValueError(f"panne chat : op inconnue {op!r} — attendues : {list(FAULT_OPS)}")
    params = value.get("params")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError(f"panne chat {op} : params doit être un objet, reçu {params!r}")
    return op, params, value.get("until_ms")


# Bornes du vocabulaire d'objets (topic `rehearsal/objects`, lot M1 « Aller
# voir », dadou_robot_ros/docs/spec-aller-voir.md §2.1). Ce texte part au LLM à
# CHAQUE tour (cf. personas.objects_prompt) : chaque caractère se paie en
# latence. Le régisseur promet desc ≤ 6 mots ; ces plafonds tiennent même si
# l'itinéraire grossit ou si un YAML déraille (l'itinéraire « Chantiers »
# compte une trentaine de POI au 31/10).
OBJECTS_MAX = 40
OBJECT_NAME_MAX_CHARS = 40
OBJECT_DESC_MAX_CHARS = 60


def decode_objects_payload(raw) -> list:
    """Payload de `rehearsal/objects` -> [(name, desc)], dans l'ordre reçu.
    Contrat (§2.1) : liste JSON [{"name": "anneaux", "desc": "bagues
    géantes"}, …]. TOLÉRANT élément par élément : un élément sans `name`
    chaîne non vide est sauté ; `desc` absente ou non chaîne = "" (le prompt
    n'affiche alors que le nom). Champs rognés puis tronqués, liste tronquée
    à OBJECTS_MAX. ValueError (le node garde sa liste précédente et loggue)
    si le payload n'est pas une liste JSON, ou si une liste NON vide ne
    contient aucun élément valable — un vocabulaire illisible ne doit pas
    effacer celui qui marchait. [] est valable : plus aucun objet."""
    try:
        value = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"objets illisibles (liste JSON attendue) : {raw!r}") from exc
    if not isinstance(value, list):
        raise ValueError(f"objets : liste JSON attendue, reçu {value!r}")
    objects = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        desc = item.get("desc")
        desc = desc.strip() if isinstance(desc, str) else ""
        objects.append((name.strip()[:OBJECT_NAME_MAX_CHARS], desc[:OBJECT_DESC_MAX_CHARS]))
        if len(objects) == OBJECTS_MAX:
            break
    if value and not objects:
        raise ValueError(f"objets : aucun élément valable (\"name\" manquant) : {raw!r}")
    return objects


def encode_transcript(role: str, text: str, t_ms: int) -> str:
    """Payload StringTime du topic `chat_transcript` (§13.6) : JSON
    {"role", "text", "t_ms"}. ensure_ascii=False : le texte est lu par un
    humain (page « scène », journal) — des \\u00e9 partout le rendraient
    illisible au débrief sans rien apporter."""
    return json.dumps({"role": role, "text": text, "t_ms": t_ms}, ensure_ascii=False)
