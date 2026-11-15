"""Tâche en cours — « il fait ce qu'il annonce, jusqu'au bout » (lot M4, 01/11).

QUOI : MoveTask suit UNE tâche de mouvement ouverte par une demande HUMAINE
       (« fais le tour de la place », « va aux anneaux puis reviens ») : le
       nombre de gestes déjà faits, l'âge de la tâche, et si un geste est en
       vol (`awaiting`). Quand route_driver publie l'issue du geste
       (`route_goto_result`), `on_result` rend la DIRECTION de continuation
       et la range dans l'emplacement unique que le moteur de conversation
       sert pendant l'écoute (dadou_robot_ros/docs/spec-aller-voir.md §9).
POURQUOI : chaque geste finit par un arrêt et Didier ne reprenait JAMAIS la
       main à ce moment — un tour spontané ne peut pas le remettre en
       mouvement (revue B1 du 23/10, cf. ConversationEngine._notify_move).
       Décision de David (01/11) : assouplissement BORNÉ de B1 — seule une
       tâche ouverte par un humain enchaîne, et dans un budget fixe
       (TASK_MAX_STEPS gestes, TASK_MAX_S secondes).
POURQUOI un module PUR (aucun rclpy, horloge INJECTÉE par `now`) : les
       bornes (budget, défaut sûr des raisons) se testent en CI à la seconde
       près, sans ROS (cf. test/unit/test_move_task.py).
POURQUOI un verrou : `on_result` est appelé par le thread rclpy.spin
       (chat_node), `gesture_emitted`/`close`/`pop_continuation` par le
       thread de conversation, et `close("stop")` aussi par le thread STT de
       l'écoute garde. L'état tient en plusieurs champs liés (tâche, steps,
       awaiting, emplacement) : la continuation est rangée SOUS le même verrou
       que la fermeture — une tâche close ne peut jamais laisser derrière elle
       une continuation servie après coup.
PIÈGE (défaut SÛR) : seule une issue CONNUE poursuit la tâche (arrivée, ou
       abandon par une borne de manœuvre listée dans CONTINUE_REASONS) ; toute
       autre raison (cancel, stop, route on/off, raison inventée demain côté
       robot) FERME la tâche — ce qu'on ne connaît pas arrête Didier.
GESTE REFUSÉ (15/11, séance : « fais le tour de l'éléphant », refusé faute
       de tour ; la tâche restait ouverte, la réflexion imaginait le tour
       fini et Didier affirmait « j'ai fait le tour de l'éléphant » sans avoir
       bougé) : le régisseur — ou le sélecteur de jeu qui ne transmet pas —
       répond à CHAQUE geste (rehearsal/chat_move_reply, `on_reply`, appariée
       par égalité avec le geste émis). Un refus devient une fin de geste
       ÉCHOUÉE : direction « n'a PAS eu lieu : <raison en clair> », servie
       comme une continuation — Didier le dit en personnage, ne le prétend
       jamais fait, et la tâche continue honnêtement (autre geste) ou se
       ferme (réplique sans geste). Pas de réponse en ACK_TIMEOUT_S
       (`check_ack`, appelé par le timer de chat_node) : même chose, raison
       « personne n'a donné suite ». Une réponse ARRIVÉE AVANT que la
       conversation ait noté son geste (le régisseur répond en quelques ms)
       est gardée EARLY_REPLY_S et appliquée à la notation.
"""
from __future__ import annotations

import logging
import math
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Budget d'une tâche (spec §9.1, gravés dans les tests) : au plus 8 gestes et
# 180 s depuis son ouverture. Au-delà, la tâche est close ("budget") : un LLM
# qui ne dit jamais « c'est fini » ne fait pas tourner Didier indéfiniment.
TASK_MAX_STEPS = 8
TASK_MAX_S = 180.0

# Raison du geste remplacé par un ordre plus récent (route_driver,
# _abandon_goto) : la tâche attend l'issue du SIEN, rien à faire.
SUPERSEDED_REASON = "goto_suivant"

# Abandons par une borne de manœuvre (didier_rehearsal/goto.py) qui POURSUIVENT
# la tâche : Didier dit où il en est et tente la suite — avec la raison en
# clair pour le LLM (textes gravés dans les tests). Liste FERMÉE (défaut sûr).
CONTINUE_REASONS = {
    "timeout": "trop long",
    "stalled": "bloqué",
    "off_track": "sorti de sa trajectoire",
    "max_travel": "trop de chemin parcouru",
    "too_far": "trop loin",
}

# Fin commune du texte de continuation (spec §9.1, texte EXACT).
_TASK_TAIL = ("Ta tâche, demandée par David : « {request} ». Si elle n'est pas finie, "
              "dis où tu en es en quelques mots et fais le geste suivant ; si elle est "
              "finie, dis-le en une phrase, SANS clé de geste.")

# Geste REFUSÉ ou resté sans réponse (15/11, spec §9.6) — textes gravés dans
# les tests. Délai au-delà duquel un geste ni accepté ni refusé est déclaré
# sans suite : le sélecteur de jeu répond au plus tard ~6 s après la demande
# (TTL de l'offre 3 s, ou décision + deplacement_accuse 3 s), le régisseur en
# quelques ms. Réponse arrivée avant la notation du geste : gardée 2 s.
ACK_TIMEOUT_S = 8.0
EARLY_REPLY_S = 2.0
ACCEPTED = "accepted"
# Raisons EN CLAIR pour le LLM (2e personne : c'est Didier qui le dira).
# Clés : effect du régisseur (contracts.CHAT_MOVE_REPLY_TOPIC) ; ("invalid",
# sous-raison) ; codes du sélecteur de jeu (CHAT_MOVE_REPLY_JEU_REASONS) ;
# "no_reply" (jeu) et NO_ANSWER (ce module). Inconnu -> REFUSAL_DEFAULT.
NO_ANSWER = "sans_reponse"
REFUSAL_REASONS = {
    "unknown": "cet objet n'est pas dans ta liste, tu ne le trouves pas",
    "no_tour": "impossible d'en faire le tour, il n'y a pas la place tout autour (eau, mur ou obstacle)",
    "too_far": "c'est trop loin d'ici",
    "no_pose": "tu ne sais pas où tu es en ce moment",
    "route_off_by_david": "David a coupé ta route, tu ne bouges pas sans lui",
    ("invalid", "recul"): "tu ne sais pas reculer",
    ("invalid", "hors_bornes"): "c'est plus que ce que ton corps sait faire en un geste",
    ("invalid", "sens"): "le sens du tour était incompréhensible",
    "invalid": "ta demande de geste était incompréhensible",
    "arrete": "tu es arrêté jusqu'à ce qu'on te dise de repartir",
    "sans_superviseur": "personne ne te surveille, tu ne te déplaces pas seul",
    "fatigue": "tu es trop fatigué pour te déplacer maintenant",
    "trop_tot": "tu viens déjà de te déplacer, pas tout de suite",
    "ignore": "on t'a dit de laisser ça de côté",
    "pas_retenu": "ton corps ne t'a pas suivi",
    "degrade": "ton corps ne répond qu'à « stop » et « go » en ce moment",
    "no_reply": "personne n'a donné suite",
    NO_ANSWER: "personne n'a donné suite",
}
REFUSAL_DEFAULT = "le geste n'a pas pu se faire"
_REFUSED_TAIL = ("Ta tâche, demandée par David : « {request} ». Dis-le en personnage, en une "
                 "phrase : ne prétends JAMAIS l'avoir fait. Ne redemande pas ce geste-là ; si un "
                 "autre geste sert la tâche, fais-le, sinon dis que tu ne peux pas, SANS clé de geste.")
_REFUSED_FINAL_TAIL = ("Ta tâche, demandée par David : « {request} », s'arrête là. Dis-le en "
                       "personnage, en une phrase : ne prétends JAMAIS l'avoir fait, et SANS clé de geste.")


def refusal_reason(payload) -> str:
    """Réponse de refus (rehearsal/chat_move_reply) -> raison en clair.
    Défaut SÛR : une raison inconnue reste un ÉCHEC (REFUSAL_DEFAULT)."""
    effect = payload.get("effect") if isinstance(payload, dict) else None
    reason = payload.get("reason") if isinstance(payload, dict) else None
    if effect == "dropped":
        return REFUSAL_REASONS.get(reason, REFUSAL_DEFAULT) if isinstance(reason, str) else REFUSAL_DEFAULT
    for key in ((effect, reason), effect):
        try:
            if key in REFUSAL_REASONS:
                return REFUSAL_REASONS[key]
        except TypeError:   # clé non hachable (payload hostile)
            break
    return REFUSAL_DEFAULT


def gesture_label(gesture) -> str:
    """Geste émis (dict du contrat chat_move) -> libellé court pour le LLM."""
    if not isinstance(gesture, dict):
        return "?"
    cmd = gesture.get("cmd")
    if cmd == "aller_voir":
        return f"aller voir {gesture.get('objet')}"
    if cmd == "tour_de":
        return f"faire le tour de {gesture.get('objet')}"
    if cmd == "tourner":
        return f"tourner de {gesture.get('angle_deg')}°"
    if cmd == "avancer":
        return f"avancer de {gesture.get('metres')} m"
    return str(cmd)


def refused_text(gesture, reason_text: str, request: str, final: bool) -> str:
    """Direction d'un geste ÉCHOUÉ (texte EXACT gravé dans les tests)."""
    head = f"Ton geste « {gesture_label(gesture)} » n'a PAS eu lieu : {reason_text}. Tu n'as pas bougé."
    return head + " " + (_REFUSED_FINAL_TAIL if final else _REFUSED_TAIL).format(request=request)


def _format_travelled(raw) -> str:
    """Distance parcourue (m, déjà arrondie à 0,01 par route_driver) -> texte
    court (« 3.5 », « 1 ») ; illisible (absent, booléen, non fini) -> « ? » :
    un payload abîmé ne doit pas empêcher Didier de poursuivre."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        return "?"
    return f"{raw:g}"


def continuation_text(name, result, reason, travelled, request: str) -> str:
    """Direction de continuation (spec §9.1, texte EXACT gravé dans les tests).
    `result` "arrived" -> « est terminé (N m parcourus) » ; sinon `reason`
    doit être une clé de CONTINUE_REASONS (l'appelant l'a vérifié)."""
    name = name.strip() if isinstance(name, str) and name.strip() else "?"
    if result == "arrived":
        head = f"Ton geste « {name} » est terminé ({_format_travelled(travelled)} m parcourus)."
    else:
        head = f"Ton geste « {name} » s'est interrompu ({CONTINUE_REASONS[reason]})."
    return head + " " + _TASK_TAIL.format(request=request)


class MoveTask:
    """Tâche de mouvement en cours (au plus une), protégée par un verrou (cf.
    docstring de module). Toutes les méthodes datées prennent `now` (horloge
    MONOTONE de l'appelant, time.monotonic() en prod)."""

    def __init__(self):
        self._lock = threading.Lock()
        # Demande de David qui a ouvert la tâche ; None = aucune tâche.
        self._request: Optional[str] = None
        self._opened_at = 0.0
        self._steps = 0
        # Un geste est en vol : seule SON issue peut faire avancer la tâche.
        self._awaiting = False
        # Emplacement de continuation (spec §9.2) : UN seul, la plus récente
        # remplace ; vidé par close().
        self._continuation: Optional[str] = None
        # Geste en vol (dict du contrat, apparié aux réponses), quand il est
        # parti, et s'il a été ACCEPTÉ (alors seule route_goto_result le finit).
        self._gesture: Optional[dict] = None
        self._emitted_at = 0.0
        self._acked = False
        # Réponse arrivée avant la notation de son geste : (payload, instant).
        self._early: Optional[tuple] = None

    @property
    def steps(self) -> int:
        """Gestes déjà émis par la tâche en cours (0 sans tâche) — pour le log."""
        with self._lock:
            return self._steps if self._request is not None else 0

    def is_open(self) -> bool:
        with self._lock:
            return self._request is not None

    def gesture_emitted(self, request: str, continuation: bool, now: float,
                        gesture: Optional[dict] = None) -> None:
        """Une réplique NON spontanée vient d'émettre un geste de corps
        (aller_voir, tour_de, tourner, avancer — pas go/stop). Tour humain :
        NOUVELLE tâche (steps = 1). Tour de continuation : même tâche,
        steps += 1. Dans les deux cas un geste est en vol (awaiting).
        Continuation sans tâche ouverte (close tombée pendant la réplique) :
        ignoré — on ne rouvre jamais une tâche qu'un humain n'a pas demandée."""
        with self._lock:
            if continuation:
                if self._request is None:
                    logger.warning("Tâche : geste de continuation sans tâche ouverte, ignoré.")
                    return
                self._steps += 1
                logger.info("Tâche : geste %d/%d.", self._steps, TASK_MAX_STEPS)
            else:
                self._request = request
                self._opened_at = now
                self._steps = 1
                self._continuation = None
                logger.info("Tâche ouverte : %r (geste 1/%d).", request, TASK_MAX_STEPS)
            self._awaiting = True
            self._gesture, self._emitted_at, self._acked = gesture, now, False
            early, self._early = self._early, None
            if (early is not None and gesture is not None and now - early[1] <= EARLY_REPLY_S
                    and early[0].get("demande") == gesture):
                self._apply_reply_locked(early[0], now)

    def close(self, reason: str) -> bool:
        """Ferme la tâche en cours (et vide l'emplacement de continuation).
        -> True s'il y en avait une. Journalisé seulement dans ce cas : un
        "stop" sans tâche (le cas courant) ne doit pas remplir le log."""
        with self._lock:
            return self._close_locked(reason)

    def _close_locked(self, reason: str) -> bool:
        had_task = self._request is not None
        if had_task:
            logger.info("Tâche close (%s) : %r après %d geste(s).",
                        reason, self._request, self._steps)
        self._request = None
        self._steps = 0
        self._awaiting = False
        self._continuation = None
        self._gesture = None
        return had_task

    def on_result(self, payload, now: float) -> Optional[str]:
        """Issue d'un geste (route_goto_result {name, result, reason,
        travelled}). -> texte de continuation (aussi RANGÉ dans
        l'emplacement, sous le même verrou) ou None. Règles (spec §9.1) :
        aucune tâche / pas de geste en vol / "goto_suivant" -> None sans rien
        changer ; arrivée ou raison de CONTINUE_REASONS -> continuation si le
        budget le permet, sinon close("budget") ; tout le reste -> close."""
        with self._lock:
            if self._request is None or not self._awaiting:
                return None
            if not isinstance(payload, dict):
                self._close_locked("résultat illisible")
                return None
            reason = payload.get("reason")
            if reason == SUPERSEDED_REASON:
                return None
            result = payload.get("result")
            if result != "arrived" and reason not in CONTINUE_REASONS:
                # Défaut SÛR : cancel, stop, route on/off, raison inconnue.
                self._close_locked(f"geste {result} : {reason}")
                return None
            if self._steps >= TASK_MAX_STEPS or now - self._opened_at >= TASK_MAX_S:
                self._close_locked("budget")
                return None
            self._awaiting = False
            text = continuation_text(payload.get("name"), result, reason,
                                     payload.get("travelled"), self._request)
            self._continuation = text
            return text

    def on_reply(self, payload, now: float) -> Optional[str]:
        """Réponse au geste (rehearsal/chat_move_reply {demande, effect,
        reason, source}). -> direction d'échec (aussi RANGÉE) ou None.
        Appariée par ÉGALITÉ de `demande` avec le geste en vol ; sans geste
        en vol, gardée EARLY_REPLY_S (elle a pu devancer la notation)."""
        if not isinstance(payload, dict):
            return None
        with self._lock:
            if self._request is None or not self._awaiting or self._gesture is None:
                self._early = (payload, now)
                return None
            if payload.get("demande") != self._gesture:
                return None   # le geste d'un autre (sélecteur, console) ou un ancien
            return self._apply_reply_locked(payload, now)

    def check_ack(self, now: float) -> Optional[str]:
        """Borne de l'absence de réponse (timer de chat_node) : un geste ni
        accepté ni refusé depuis ACK_TIMEOUT_S = échoué (« personne n'a donné
        suite »). -> direction d'échec ou None."""
        with self._lock:
            if (self._request is None or not self._awaiting or self._gesture is None
                    or self._acked or now - self._emitted_at < ACK_TIMEOUT_S):
                return None
            return self._apply_reply_locked({"effect": NO_ANSWER}, now)

    def _apply_reply_locked(self, payload: dict, now: float) -> Optional[str]:
        if payload.get("effect") == ACCEPTED:
            self._acked = True
            return None
        reason = refusal_reason(payload)
        gesture, request = self._gesture, self._request
        final = self._steps >= TASK_MAX_STEPS or now - self._opened_at >= TASK_MAX_S
        logger.info("Tâche : geste %r refusé (%s)%s.", gesture, reason, ", budget épuisé" if final else "")
        if final:
            # Budget épuisé : la tâche se ferme, mais l'échec est QUAND MÊME dit
            # (jamais de silence qui laisserait croire au geste) — la réplique
            # n'enchaîne rien (conversation : geste refusé sans tâche ouverte).
            self._close_locked("budget")
        self._awaiting = False
        self._gesture = None
        text = refused_text(gesture, reason, request, final)
        self._continuation = text
        return text

    def pop_continuation(self) -> Optional[str]:
        """Consomme la continuation en attente, ou None (thread de conversation)."""
        with self._lock:
            text, self._continuation = self._continuation, None
            return text
