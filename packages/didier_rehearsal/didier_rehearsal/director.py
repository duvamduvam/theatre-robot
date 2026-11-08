"""Ordonnanceur du régisseur — machine à états PURE : tick(now_s) -> actions.

Garanties (testées) :
 - une panne démarre à son instant, s'arrête à instant + durée (ou tout de
   suite si ponctuelle) ; JAMAIS au-delà de FAULT_MAX_DURATION_S (déjà borné
   au chargement, re-borné ici par sécurité) ;
 - deux pannes sur la même CIBLE ne se chevauchent pas : la seconde est
   SAUTÉE (action "skip"), jamais empilée ;
 - abort() arrête tout ce qui est actif, en une fois — et AVANT start() ne
   fait RIEN (un STOP égaré ne doit pas tuer la séance qui n'a pas commencé) ;
 - close_active() termine sur-le-champ la panne active d'une cible (fermeture
   d'une lubie au fader par David) ;
 - la fin du scénario (duration_s) arrête tout ce qui reste actif ;
 - un déclencheur POI (t_s None) ne part QUE par trigger(), une seule fois ;
   jamais atteint -> « skipped » à la fin (ou à l'abort), comme un pending.
Le node exécute les actions ; ce module ne touche à rien. messages() donne,
pour les types purement messagers du lot R3, les messages EXACTS à publier
(contrats partagés avec chat_node, gravés par test). speed_factor /
speed_in_effect / fader_moved : la vitesse de cheminement telle que le
régisseur la raisonne (rendue à la fin, référence de la fermeture au fader).
VoiceMove (lot I1) : les ordres de marche demandés par Didier (« go » /
« stop »), décidés ici, exécutés par le node via route / route_speed.
« Aller voir » (lot M1, spec-aller-voir.md) : objects_payload (vocabulaire
latché pour chat_node), decide_goto (arbitrage : objet inconnu, route OFF par
David, trop loin), goto_order (l'ordre à route_driver), GotoPolicy (la
manœuvre que NOUS avons ordonnée, ce que la voix et le fader peuvent en
faire), VoiceMove.accept_goto (l'arrêt vocal levé à l'acceptation).
Gestes chiffrés (lot M2, spec §7.2-§7.3) : decide_turn (« tourner »,
angle_deg signé + = gauche, compat « sens ») et decide_forward (« avancer »,
metres, jamais de recul) — mêmes refus que « aller voir » (route OFF par
David, pas de pose), même acceptation (VoiceMove.accept_goto, GotoPolicy).
« Faire le tour » (lot M3, spec §8.3) : decide_tour — objet résolu comme
« aller voir », refus « no_tour » s'il n'a pas de tour (fichier généré),
mêmes refus ensuite, distance jugée au CENTRE du tour ; même acceptation.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from theatre_contrats import stringtime

from didier_rehearsal.contracts import (CHAT_FAULT_TOPIC, EXTERNAL_SPEED_DELTA, FAULT_MAX_DURATION_S,
                                       FORWARD_MAX_M, FORWARD_MIN_M, GOTO_MAX_DISTANCE_M, GOTO_STANDOFF_M, INSTRUCTION_TOPIC,
                                       ROUTE_CMD_TOPIC, ROUTE_SPEED_TOPIC, ROUTE_STATE_CAUSES, ROUTE_STATES, TOUR_SENS, TOUR_SENS_DEFAUT,
                                       TURN_DEG_COMPAT, TURN_MAX_DEG)
from didier_rehearsal.goto import forward_name, tour_name, turn_name
from didier_rehearsal.route import Poi, Tour, normalize_name
from didier_rehearsal.scenario import Fault, Scenario


@dataclass(frozen=True)
class Action:
    kind: str     # "start" | "stop" | "skip" | "end"
    fault: Fault | None
    t_s: float


class Director:
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self._status: Dict[str, str] = {f.id: "pending" for f in scenario.faults}
        self._stop_at: Dict[str, float] = {}
        self._active_targets: Dict[str, str] = {}   # cible -> id de la panne active
        self._started = False
        self._ended = False
        self._t0 = 0.0

    # --- état -----------------------------------------------------------------
    @property
    def started(self) -> bool:
        return self._started

    @property
    def ended(self) -> bool:
        return self._ended

    def status(self) -> Dict[str, str]:
        return dict(self._status)

    def active(self) -> List[str]:
        return sorted(self._active_targets.values())

    def active_fault(self, target: str) -> Fault | None:
        """Panne active sur `target`, ou None (mouvement à la voix : y a-t-il
        une lubie à fermer sur la cible `speed` ?)."""
        fid = self._active_targets.get(target)
        return None if fid is None else next(f for f in self.scenario.faults if f.id == fid)

    # --- transitions --------------------------------------------------------------
    def start(self, now_s: float) -> None:
        self._t0 = now_s
        self._started = True

    def abort(self, now_s: float) -> List[Action]:
        """Arrête tout ce qui est actif et clôt le scénario. Séance PAS encore
        démarrée : ne fait RIEN — ni pending -> skipped, ni fin. Sinon un STOP
        envoyé avant START (salve d'un script, page) sautait toute la timeline
        et le START suivant jouait une séance vide."""
        if not self._started:
            return []
        actions: List[Action] = []
        for fid in list(self._active_targets.values()):
            actions.append(self._stop(fid, now_s))
        for fid, st in self._status.items():
            if st == "pending":
                self._status[fid] = "skipped"
        if self._started and not self._ended:
            self._ended = True
            actions.append(Action("end", None, now_s))
        return actions

    def cancel(self, fid: str, now_s: float) -> None:
        """Le node n'a PAS pu appliquer le démarrage (processus absent…) : la
        panne passe en « error », libère sa cible et n'aura jamais de stop —
        un stop sur une panne jamais appliquée serait un mensonge au journal."""
        fault = next(f for f in self.scenario.faults if f.id == fid)
        self._status[fid] = "error"
        if self._active_targets.get(fault.target) == fid:
            self._active_targets.pop(fault.target, None)
        self._stop_at.pop(fid, None)

    def close_active(self, target: str, now_s: float, only_type: str = "lubie") -> List[Action]:
        """Termine TOUT DE SUITE la panne active sur `target` si elle est du
        type `only_type` (-> [stop]) ; sinon, ou si la cible est libre : [].
        Usage : David bouge le fader pendant une lubie -> elle se ferme ; une
        batterie faible (speed, même cible) ne se ferme PAS au fader."""
        fid = self._active_targets.get(target)
        if fid is None:
            return []
        fault = next(f for f in self.scenario.faults if f.id == fid)
        if fault.type != only_type:
            return []
        return [self._stop(fid, now_s)]

    def _stop(self, fid: str, now_s: float) -> Action:
        fault = next(f for f in self.scenario.faults if f.id == fid)
        self._status[fid] = "done"
        self._active_targets.pop(fault.target, None)
        self._stop_at.pop(fid, None)
        return Action("stop", fault, now_s)

    def _due_stops(self, rel: float, now_s: float) -> List[Action]:
        """Arrêts échus à l'instant relatif rel (sorted() copie : _stop vide _stop_at)."""
        return [self._stop(fid, now_s)
                for fid, stop_at in sorted(self._stop_at.items(), key=lambda kv: kv[1])
                if rel >= stop_at]

    def _begin(self, f: Fault, now_s: float, start_rel: float) -> List[Action]:
        """Démarre f (fin prévue à start_rel + durée) — ou la SAUTE si sa cible
        est occupée, jamais empilée. Dans les deux cas elle quitte « pending »."""
        if f.target in self._active_targets:
            self._status[f.id] = "skipped"
            return [Action("skip", f, now_s)]
        self._status[f.id] = "active"
        actions = [Action("start", f, now_s)]
        dur = min(f.duration_s, FAULT_MAX_DURATION_S[f.type])
        if dur <= 0.0:
            # Ponctuelle : start et stop dans le même tick.
            actions.append(self._stop(f.id, now_s))
        else:
            self._active_targets[f.target] = f.id
            self._stop_at[f.id] = start_rel + dur
        return actions

    def trigger(self, poi_name: str, now_s: float) -> List[Action]:
        """Événement « enter » d'un POI : démarre les déclencheurs `t: poi` de
        ce POI encore pending, avec la même exclusion par cible que tick()
        (arrêts échus d'abord, pour ne pas sauter une lubie à 50 ms d'une
        cible libérée). UN SEUL déclenchement par séance, PAS de seconde
        chance : sauté pour cible occupée, il passe « skipped » ; un 2e enter
        (Didier repoussé en arrière par la télécommande) ne rejoue rien — la
        lubie est liée au PASSAGE devant l'objet, pas à l'objet.
        Avant start / après la fin : rien (le déclencheur reste pending)."""
        if not self._started or self._ended:
            return []
        rel = now_s - self._t0
        if rel >= self.scenario.duration_s:
            return []   # le prochain tick clôt le scénario et le saute
        actions = self._due_stops(rel, now_s)
        for f in self.scenario.faults:
            if f.trigger_poi == poi_name and self._status[f.id] == "pending":
                actions.extend(self._begin(f, now_s, rel))
        return actions

    def skip_poi(self, poi_name: str, only_type: str = "lubie") -> List[str]:
        """Saute (« skipped », définitif) les déclencheurs `t: poi` de ce POI
        encore pending et du type `only_type` -> leurs ids. Lot M1 : la lubie
        de l'objet qu'on VA VOIR ne part pas (son « enter » arrive pendant
        l'approche, standoff < rayon) — Didier joue l'objet lui-même à
        l'arrivée. Hors séance : rien (comme trigger)."""
        if not self._started or self._ended:
            return []
        ids = [f.id for f in self.scenario.faults
               if f.trigger_poi == poi_name and f.type == only_type and self._status[f.id] == "pending"]
        for fid in ids:
            self._status[fid] = "skipped"
        return ids

    def tick(self, now_s: float) -> List[Action]:
        if not self._started or self._ended:
            return []
        rel = now_s - self._t0
        # 1. arrêts dus (avant les démarrages : libère les cibles)
        actions = self._due_stops(rel, now_s)
        # 2. démarrages dus — les déclencheurs POI (t_s None) ne partent que par trigger()
        for f in self.scenario.faults:
            if f.t_s is None or self._status[f.id] != "pending" or rel < f.t_s:
                continue
            actions.extend(self._begin(f, now_s, f.t_s))
        # 3. fin de scénario
        if rel >= self.scenario.duration_s:
            for fid in list(self._active_targets.values()):
                actions.append(self._stop(fid, now_s))
            for fid, st in self._status.items():
                if st == "pending":
                    self._status[fid] = "skipped"
            self._ended = True
            actions.append(Action("end", None, now_s))
        return actions


MESSAGE_TYPES = ("instruction", "lubie", "chat")

# Sentinelle de messages() : restore_value non fourni -> `restore` du scénario
# (dernier recours, rétro-compatible). None, lui, veut dire « ne rien rendre ».
SCENARIO_RESTORE = object()


def messages(f: Fault, kind: str, lubie_text: str = "",
             restore_value=SCENARIO_RESTORE) -> List[Tuple[str, str]]:
    """-> [(topic, payload StringTime)] d'un « start »/« stop » pour les types
    MESSAGE_TYPES. Pur : le node publie, rien d'autre. `lubie_text` = consigne
    RÉSOLUE de la lubie (texte du scénario ou champ `lubie` du POI).
    `restore_value` = vitesse rendue au stop d'une lubie stop=true : le node
    passe la vitesse EN VIGUEUR (speed_in_effect), ou None quand la lubie est
    fermée AU FADER (David vient de fixer la vitesse : pas de route_speed).
    Contrats : chat_instruction = chaîne JSON, "" = consigne levée ;
    rehearsal/chat_fault = {"op", "params", "until_ms"} — mêmes chaînes que
    les tests du dépôt vision."""
    p = f.params
    if f.type == "instruction":
        if kind == "start":
            return [(INSTRUCTION_TOPIC, json.dumps(p["text"], ensure_ascii=False))]
        # Consigne BORNÉE (R3) : levée à la fin. Ponctuelle (R2) : rien à lever,
        # chat_node la périme seul (120 s).
        return [(INSTRUCTION_TOPIC, json.dumps(""))] if f.duration_s > 0 else []
    if f.type == "lubie":
        if kind == "start":
            out = [(INSTRUCTION_TOPIC, json.dumps(lubie_text, ensure_ascii=False))]
            if p["stop"]:
                # Didier s'arrête devant l'objet : la télécommande (prio 100), le
                # fader ou l'expiration le font repartir.
                out.append((ROUTE_SPEED_TOPIC, "0"))
            return out
        out = [(INSTRUCTION_TOPIC, json.dumps(""))]
        # On ne rend la vitesse QUE si on l'a prise : une lubie stop=false ne
        # doit pas écraser le fader de David en finissant.
        value = p["restore"] if restore_value is SCENARIO_RESTORE else restore_value
        if p["stop"] and value is not None:
            out.append((ROUTE_SPEED_TOPIC, json.dumps(value)))
        return out
    if f.type == "chat":
        if kind == "start":
            # Re-borné ici aussi : ce canal n'a PAS de chien de garde.
            until_ms = int(min(f.duration_s, FAULT_MAX_DURATION_S["chat"]) * 1000)
            cmd = {"op": p["op"], "params": p["params"], "until_ms": until_ms}
        elif p["op"] == "phantom":
            # Ponctuel : rien à lever. Un « pass » couperait un garble/deaf en
            # cours (sa cible est `chat`, celle du phantom `chat:phantom`).
            return []
        else:
            cmd = {"op": "pass", "params": {}, "until_ms": None}
        return [(CHAT_FAULT_TOPIC, json.dumps(cmd, ensure_ascii=False))]
    raise ValueError(f"type {f.type!r} : pas un type messager {MESSAGE_TYPES}")


# --- Vitesse de cheminement (route_speed), vue du régisseur -------------------------

def speed_factor(raw) -> float | None:
    """Payload route_speed (ou paramètre) -> facteur tel que route_driver le
    VERRA : chaîne décodée en JSON sinon prise brute (même contrat que
    route_driver), non-nombre ou non-fini -> None (route_driver l'ignore
    aussi), hors 0..1 -> borné (route_driver borne aussi)."""
    if isinstance(raw, str):
        raw = stringtime.decode_or_raw(raw, ROUTE_SPEED_TOPIC)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return min(1.0, max(0.0, value))


def route_cmd_kind(raw: str) -> str | None:
    """Payload du topic `route` -> "on" | "off" | None, avec EXACTEMENT les
    formats que route_driver accepte (JSON sinon brut ; on/true/1/"1",
    off/false/0/"0"). Revue I1 : le régisseur ne reconnaissait que "off" —
    un `false` de David lui échappait."""
    value = stringtime.decode_or_raw(raw, ROUTE_CMD_TOPIC)
    if value in ("on", True, 1, "1"):
        return "on"
    if value in ("off", False, 0, "0"):
        return "off"
    return None


def speed_in_effect(external: float | None, initial: float | None, fallback: float) -> float:
    """Vitesse EN VIGUEUR côté route : la dernière consigne EXTERNE (fader,
    page) si connue, sinon la vitesse initiale du launch, sinon `fallback`
    (restore du scénario, dernier recours). C'est elle qu'on rend à la fin
    d'un speed / d'une lubie — rendre le restore figé du scénario écrasait le
    fader de David — et elle sert de référence à la fermeture au fader."""
    if external is not None:
        return external
    if initial is not None:
        return initial
    return fallback


def fader_moved(value: float, reference: float) -> bool:
    """Consigne externe `value` = un GESTE de David (et pas une ré-émission
    du boîtier, jitter compris) ? Écart STRICTEMENT supérieur à
    EXTERNAL_SPEED_DELTA. Arrondi au millionième : en flottant, 0.55 - 0.5
    vaut 0.05000000000000004, et « écart de 0,05 = pas un geste » doit tenir
    à la frontière."""
    return round(abs(value - reference), 6) > EXTERNAL_SPEED_DELTA


@dataclass
class Reenable:
    fault_id: str
    not_before_s: float
    deadline_s: float
    last_sent_s: float | None = None


class ReenablePolicy:
    """Relance de la route après un `kill` de route_driver — logique PURE, en
    BOUCLE FERMÉE (revue du 08/10 + bug vécu le même jour). Règles :
     - on n'arme une relance QUE si la route était ON au moment du kill
       (état latché `route_state` OU commande `route on` vue) ;
     - tout ordre `off` arrivé depuis l'ANNULE — jamais de « route on » contre
       l'ordre de David ;
     - une fois `min_delay_s` passé et le consommateur prêt, `due()` demande
       d'envoyer « on » puis de RÉ-ESSAYER toutes les `retry_s` : un message
       DDS unique peut se perdre pendant que les deux bouts se découvrent
       (vécu : « on » publié 300 ms après le respawn, jamais reçu) ;
     - la relance n'est CONFIRMÉE que par l'état latché « on » reçu après
       `not_before` (note_state) — c'est seulement là qu'on journalise
       route_reenable ; passé `max_delay_s` sans confirmation, elle EXPIRE et
       le journal le dit ;
     - abort() vide tout.
    """

    def __init__(self, *, min_delay_s: float = 6.0, max_delay_s: float = 30.0, retry_s: float = 1.0):
        self.min_delay_s = float(min_delay_s)
        self.max_delay_s = float(max_delay_s)
        self.retry_s = float(retry_s)
        self._route_on = False
        # Le dernier ordre vu sur `route` est-il un `off` (David, page, STOP
        # contenus) ? CEINTURE de la cause latchée ci-dessous (revue I1) : un
        # `off` peut échapper à l'écoute et un régisseur relancé l'oublie,
        # mais quand il a été vu, il interdit la relance vocale même après
        # un reboot. Inchangé par note_state.
        self._off_by_cmd = False
        # BRETELLES (revue I1, 22/10) : état et cause LATCHÉS publiés par
        # route_driver (None = jamais reçus). Seuls « off » + « boot » (route
        # éteinte par un respawn) autorisent la relance vocale.
        self._latched_state: str | None = None
        self._cause: str | None = None
        self._pending: List[Reenable] = []

    @property
    def route_on(self) -> bool:
        return self._route_on

    @property
    def off_by_cmd(self) -> bool:
        return self._off_by_cmd

    @property
    def cause(self) -> str | None:
        return self._cause

    @property
    def latched_state(self) -> str | None:
        return self._latched_state

    def note_cause(self, cause) -> None:
        """Cause latchée de l'état (route_state_cause) ; valeur hors
        ROUTE_STATE_CAUSES ignorée (la dernière connue tient)."""
        if cause in ROUTE_STATE_CAUSES:
            self._cause = cause

    def voice_relaunch_refusal(self) -> str | None:
        """La voix (« go ») peut-elle relancer la route ? -> None si oui,
        sinon la raison du refus. Seulement si l'état latché est « off » ET
        sa cause latchée « boot » (respawn), et qu'aucun `off` n'a été vu sur
        `route` : jamais de « route on » vocal contre l'ordre de David."""
        if self._off_by_cmd or self._cause == "cmd":
            return "route_off_par_david"
        if self._cause is None:
            return "cause_inconnue"
        if self._latched_state != "off":
            return "etat_inconnu"
        return None

    def voice_may_relaunch(self) -> bool:
        return self.voice_relaunch_refusal() is None

    def note_state(self, state: str, now_s: float) -> List[str]:
        """État latché de route_driver. « on » reçu après not_before CONFIRME
        les relances en attente (-> leurs ids). « off » (route_driver respawné
        qui démarre éteint) n'annule RIEN. « goto » / « arrived » (lot M1) :
        mémorisés, la route n'est PAS on (un kill pendant une manœuvre n'arme
        aucune relance : Didier reste arrêté)."""
        if state not in ROUTE_STATES:
            return []
        self._latched_state = state
        self._route_on = state == "on"
        if state != "on":
            return []
        done = [r.fault_id for r in self._pending if now_s >= r.not_before_s]
        self._pending = [r for r in self._pending if now_s < r.not_before_s]
        return done

    def note_route_cmd(self, cmd: str) -> None:
        """Commande vue sur `route` : seul un `off` ANNULE les relances."""
        if cmd == "on":
            self._route_on = True
            self._off_by_cmd = False
        elif cmd == "off":
            self._route_on = False
            self._off_by_cmd = True
            self._pending.clear()

    def arm(self, fault_id: str, now_s: float) -> bool:
        """-> True si une relance est armée (route ON au moment du kill)."""
        if not self._route_on:
            return False
        self._pending.append(Reenable(fault_id, now_s + self.min_delay_s, now_s + self.max_delay_s))
        return True

    def abort(self) -> List[str]:
        ids = [r.fault_id for r in self._pending]
        self._pending.clear()
        return ids

    def pending(self) -> List[str]:
        return [r.fault_id for r in self._pending]

    def due(self, now_s: float, ready: bool) -> tuple:
        """-> (envoyer « on » maintenant ?, ids expirés). Envoi au plus tous
        les retry_s tant qu'une relance due n'est pas confirmée."""
        expired = [r.fault_id for r in self._pending if now_s >= r.deadline_s]
        self._pending = [r for r in self._pending if now_s < r.deadline_s]
        send = False
        if ready:
            for r in self._pending:
                if now_s >= r.not_before_s and (r.last_sent_s is None or now_s - r.last_sent_s >= self.retry_s):
                    send = True
                    r.last_sent_s = now_s
        return send, expired


# --- Mouvement à la voix (lot I1, 22/10, étude §13.11) ------------------------------

# Anti-rebond : un ordre IDENTIQUE au précédent reçu il y a moins de ce délai
# est ignoré (le LLM peut redire « go » au tour suivant, une salve de test
# peut doubler un message).
VOICE_MOVE_DEBOUNCE_S = 2.0
# Relance vocale de la route : salve de VOICE_RELAUNCH_SENDS « on » espacés
# de VOICE_RELAUNCH_PERIOD_S (un message DDS unique peut se perdre, vécu le
# 08/10), confirmée SEULEMENT par l'état latché « on » ; sans confirmation
# VOICE_RELAUNCH_CONFIRM_S après le premier envoi, elle EXPIRE (journalisé).
VOICE_RELAUNCH_SENDS = 3
VOICE_RELAUNCH_PERIOD_S = 0.5
VOICE_RELAUNCH_CONFIRM_S = 3.0

VOICE_COMMANDS = ("go", "stop")


@dataclass(frozen=True)
class VoiceDecision:
    # "close_lubie" | "resume" | "relaunch" | "hold" | "ignored" ; lot M1 :
    # "rejoin" (« go » après une manœuvre, rien d'autre à lever) | "goto"
    # (acceptation d'un « aller voir », cf. accept_goto)
    effect: str
    reason: str | None = None    # pourquoi « ignored »
    speed: float | None = None   # route_speed à publier (hold : 0, resume : vitesse d'avant)
    # Lot M1 : en PLUS de l'effet, relancer la route (salve « on », comme
    # relaunch) — « go » après une manœuvre « aller voir » terminée.
    rejoin: bool = False


class VoiceMove:
    """Ordres de marche demandés par Didier (« go »/« stop », topic
    rehearsal/chat_move) — logique PURE ; le node publie. La voix n'agit QUE
    par route / route_speed, comme le reste du régisseur. Règles (gravées
    par test) :
     - ordre hors {"go","stop"} -> ignoré (« invalide ») ; « go » reçu moins
       de debounce_s après un « go » -> ignoré (« rebond ») — JAMAIS
       d'anti-rebond sur « stop » (revue I1) ;
     - hors séance : « go » ignoré (« hors_seance »), « stop » APPLIQUÉ —
       s'arrêter est toujours sûr ;
     - RÈGLE GÉNÉRALE (défaut trouvé en sim le 22/10 : une lubie qui finissait
       par sa durée rendait la vitesse et Didier repartait contre l'ordre de
       David) : tant qu'un ARRÊT VOCAL est posé, le régisseur ne publie
       JAMAIS de vitesse non nulle, sauf par « go » (voix) ou levée au fader
       (David). Le node l'applique aux lubies et aux pannes `speed` ;
     - « stop » : route_speed 0 TOUJOURS republié (idempotent, revue I1 :
       un 0 perdu ou écrasé ne doit pas rendre « stop » inopérant). Pose
       TOUJOURS l'ARRÊT VOCAL s'il n'y en a pas, même pendant une lubie stop
       (qui reste intacte) — vitesse retenue = vitesse en vigueur, jamais
       notre propre 0 ; la vitesse déjà retenue n'est jamais écrasée. Annule
       une relance vocale en cours ;
     - « go », dans cet ordre : lubie active -> la fermer (closed_by
       « voix ») ; sans arrêt vocal, la lubie rend la vitesse EN VIGUEUR ;
       avec un arrêt vocal, il est levé aussi et `speed` porte l'UNIQUE
       vitesse à publier, min(retenue, en vigueur) ; sinon arrêt vocal -> rendre
       la vitesse retenue (jamais plus que la vitesse en vigueur) ; sinon
       route OFF -> relance « route on » si `relaunch_refusal` est None (état
       latché off + cause latchée boot), sinon ignoré avec cette raison
       (« route_off_par_david », « cause_inconnue », « etat_inconnu ») ;
       sinon « deja_en_marche ». Jamais de vitesse inventée ;
     - lot M1 : `rejoin` (le node le calcule par GotoPolicy.rejoin_allowed :
       Didier arrêté par une manœuvre que nous avons ordonnée, jamais contre
       un `off` de David) -> « go » relance AUSSI la route (salve), en plus
       de la lubie fermée / de l'arrêt vocal levé ; seul, effet « rejoin » ;
     - le fader reste maître : une consigne externe qui s'écarte de plus de
       EXTERNAL_SPEED_DELTA de la vitesse retenue LÈVE l'arrêt vocal sans
       rien publier (le node ferme aussi une lubie stop active) ; abort / fin
       de séance le lèvent sans republier (abort). Le scénario (lubie,
       `speed`) ne le lève JAMAIS.
    """

    def __init__(self, *, debounce_s: float = VOICE_MOVE_DEBOUNCE_S):
        self.debounce_s = float(debounce_s)
        self._last: Tuple[str, float] | None = None   # (ordre, instant) du dernier ordre valide
        self._hold_before: float | None = None        # vitesse retenue par l'arrêt vocal, None = pas d'arrêt
        self._relaunch_since: float | None = None     # premier envoi de la salve, None = pas de relance
        self._relaunch_sent = 0
        self._relaunch_last: float | None = None

    @property
    def hold_before(self) -> float | None:
        return self._hold_before

    @property
    def relaunching(self) -> bool:
        return self._relaunch_since is not None

    def decide(self, cmd, now_s: float, *, in_session: bool, lubie_active: bool,
               route_on: bool, relaunch_refusal: str | None,
               speed_in_effect: float, rejoin: bool = False) -> VoiceDecision:
        """Décide l'effet d'un ordre et met l'état à jour (arrêt vocal posé
        ou levé, salve de relance armée). `lubie_active` : une lubie tient la
        cible `speed`. Le node exécute : close_lubie -> close_active +
        fermeture « voix » (+ `speed` publiée seule si non None) ; hold /
        resume -> route_speed `speed` ; relance -> relaunch_due()."""
        if cmd not in VOICE_COMMANDS:
            return VoiceDecision("ignored", "invalide")
        if (cmd == "go" and self._last is not None and self._last[0] == "go"
                and now_s - self._last[1] < self.debounce_s):
            return VoiceDecision("ignored", "rebond")
        self._last = (cmd, now_s)
        if cmd == "stop":
            # Un « stop » coupe toute relance vocale en vol : jamais de
            # « route on » qui suivrait un ordre d'arrêt.
            self._cancel_relaunch()
            if self._hold_before is None:
                self._hold_before = speed_in_effect
            # 0 entier : même texte « 0 » que l'arrêt d'une lubie.
            return VoiceDecision("hold", speed=0)
        if not in_session:
            return VoiceDecision("ignored", "hors_seance")
        if rejoin:
            self._arm_relaunch(now_s)
        if lubie_active:
            if self._hold_before is None:
                return VoiceDecision("close_lubie", rejoin=rejoin)
            # Lubie ET arrêt vocal : les deux tombent, UNE seule vitesse part.
            speed = min(self._hold_before, speed_in_effect)
            self._hold_before = None
            return VoiceDecision("close_lubie", speed=speed, rejoin=rejoin)
        if self._hold_before is not None:
            # Jamais plus vite que la vitesse en vigueur : le jitter du boîtier
            # (sous le seuil, donc arrêt maintenu) a pu la baisser un peu.
            speed = min(self._hold_before, speed_in_effect)
            self._hold_before = None
            return VoiceDecision("resume", speed=speed, rejoin=rejoin)
        if rejoin:
            return VoiceDecision("rejoin", rejoin=True)
        if not route_on:
            if relaunch_refusal is not None:
                return VoiceDecision("ignored", relaunch_refusal)
            self._arm_relaunch(now_s)
            return VoiceDecision("relaunch")
        return VoiceDecision("ignored", "deja_en_marche")

    def accept_goto(self, *, lubie_active: bool, speed_in_effect: float) -> VoiceDecision:
        """« Aller voir » ACCEPTÉ par le régisseur (lot M1, spec §3) : comme un
        « go » pour ce qui retient Didier — l'arrêt vocal est levé avec la
        MÊME vitesse que « go » (min(retenue, en vigueur) : jamais au-dessus
        du fader ni d'une panne batterie) et une lubie active est fermée
        (« close_lubie », closed_by « voix ») ; sinon effet « goto ». Une salve
        de relance en vol est ANNULÉE : son « route on » abandonnerait la
        manœuvre. Pas d'anti-rebond, pas de condition de séance : c'est David
        qui le demande (spec §3)."""
        self._cancel_relaunch()
        speed = None
        if self._hold_before is not None:
            speed = min(self._hold_before, speed_in_effect)
            self._hold_before = None
        return VoiceDecision("close_lubie" if lubie_active else "goto", speed=speed)

    def arm_relaunch(self, now_s: float) -> None:
        """Arme la salve de relance (reprise au fader après une manœuvre, lot M1)."""
        self._arm_relaunch(now_s)

    def _arm_relaunch(self, now_s: float) -> None:
        if self._relaunch_since is None:
            self._relaunch_since = now_s
            self._relaunch_sent = 0
            self._relaunch_last = None

    def release_hold(self) -> float | None:
        """Lève l'arrêt vocal SANS rien publier -> la vitesse qu'il retenait
        (None s'il n'y en avait pas). Appelé à l'abort / la fin, et par le
        node si le « 0 » d'un « stop » n'a pas pu partir."""
        held, self._hold_before = self._hold_before, None
        return held

    def fader(self, value: float) -> bool:
        """Consigne route_speed EXTERNE : -> True si elle LÈVE l'arrêt vocal
        (geste de David, même seuil que la fermeture d'une lubie au fader).
        Rien n'est publié : David vient de fixer la vitesse."""
        if self._hold_before is None or not fader_moved(value, self._hold_before):
            return False
        self._hold_before = None
        return True

    def note_route_cmd(self, cmd: str) -> bool:
        """Un `off` vu sur `route` annule la salve : jamais de « on » contre
        David. -> True si une relance a été annulée (le journal le dit)."""
        if cmd != "off" or self._relaunch_since is None:
            return False
        self._cancel_relaunch()
        return True

    def note_state(self, state: str) -> bool:
        """État latché « on » reçu pendant la salve -> True : relance CONFIRMÉE."""
        if state != "on" or self._relaunch_since is None:
            return False
        self._cancel_relaunch()
        return True

    def relaunch_due(self, now_s: float) -> Tuple[bool, bool]:
        """-> (envoyer « on » maintenant ?, relance expirée ?). Au plus
        VOICE_RELAUNCH_SENDS envois, espacés de VOICE_RELAUNCH_PERIOD_S."""
        if self._relaunch_since is None:
            return False, False
        if now_s - self._relaunch_since >= VOICE_RELAUNCH_CONFIRM_S:
            self._cancel_relaunch()
            return False, True
        if self._relaunch_sent < VOICE_RELAUNCH_SENDS and (
                self._relaunch_last is None or now_s - self._relaunch_last >= VOICE_RELAUNCH_PERIOD_S):
            self._relaunch_sent += 1
            self._relaunch_last = now_s
            return True, False
        return False, False

    def abort(self) -> Tuple[float | None, bool]:
        """Abort / fin de séance : lève l'arrêt vocal SANS republier de
        vitesse et annule la salve -> (vitesse qui était retenue, relance annulée ?)."""
        relaunching = self._relaunch_since is not None
        self._cancel_relaunch()
        return self.release_hold(), relaunching

    def _cancel_relaunch(self) -> None:
        self._relaunch_since = None
        self._relaunch_sent = 0
        self._relaunch_last = None


# --- « Aller voir » (lot M1, spec-aller-voir.md) -------------------------------------

def objects_payload(pois) -> str:
    """Payload LATCHÉ de rehearsal/objects (spec §2.1) : JSON liste
    [{"name", "desc", "x", "y"}] dans l'ordre de l'itinéraire, desc = nom si
    absente. Les alias n'y sont PAS : ils servent à la résolution ici, pas au
    prompt. x, y (m, repère du monde = ANCRE du POI, pas le centre de l'objet)
    ajoutés au lot A1 (02/11) pour que le sélecteur de jeu oriente le regard
    vers l'objet d'une lubie (SIM-ONLY) : champs ADDITIFS, chat_node ne lit
    que name/desc (didier_vision/ai/stage.decode_objects_payload) et les ignore."""
    return json.dumps([{"name": p.name, "desc": p.shown_desc, "x": p.x, "y": p.y} for p in pois])


def resolve_object(text, pois) -> Poi | None:
    """Texte dit (ou nom renvoyé par la bouche) -> POI, par correspondance
    NORMALISÉE exacte (normalize_name) sur le nom et les alias. load_route
    garantit qu'une clé ne désigne qu'un POI. Rien de flou : un objet mal
    compris est refusé (« unknown »), jamais deviné."""
    key = normalize_name(text)
    if not key:
        return None
    for p in pois:
        if key == normalize_name(p.name) or any(key == normalize_name(a) for a in p.alias):
            return p
    return None


@dataclass(frozen=True)
class GotoDecision:
    effect: str                  # "accepted" | "unknown" | "route_off_by_david" | "no_pose" | "too_far"
    poi: Poi | None = None
    distance: float | None = None


def decide_goto(objet, *, pois, pose, off_by_david: bool) -> GotoDecision:
    """Arbitrage d'un « aller voir » (spec §3), dans cet ordre : objet
    inconnu -> « unknown » ; route OFF par David -> « route_off_by_david »
    (jamais de mouvement contre lui) ; pas de pose fraîche -> « no_pose »
    (on ne sait pas mesurer la distance : refus, jamais deviné) ; distance
    pose -> objet > GOTO_MAX_DISTANCE_M -> « too_far ». `pose` : (x, y) ou None."""
    poi = resolve_object(objet, pois)
    if poi is None:
        return GotoDecision("unknown")
    if off_by_david:
        return GotoDecision("route_off_by_david", poi)
    if pose is None:
        return GotoDecision("no_pose", poi)
    distance = math.hypot(poi.x - pose[0], poi.y - pose[1])
    if distance > GOTO_MAX_DISTANCE_M:
        return GotoDecision("too_far", poi, distance)
    return GotoDecision("accepted", poi, distance)


def goto_order(poi: Poi, standoff: float = GOTO_STANDOFF_M) -> str:
    """Payload route_goto (spec §2.3), positions de l'itinéraire telles quelles."""
    return json.dumps({"name": poi.name, "x": poi.x, "y": poi.y, "standoff": standoff})


@dataclass(frozen=True)
class GestureDecision:
    # "accepted" | "invalid" | "route_off_by_david" | "no_pose"
    effect: str
    reason: str | None = None   # invalid : "illisible" | "hors_bornes" | "recul"
    name: str | None = None     # nom de la manœuvre — MÊME texte que route_driver (goto.*_name)
    order: str | None = None    # payload route_goto, si accepté


def _number(value) -> float | None:
    """Nombre fini (jamais un booléen), sinon None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _gesture(name: str, order: dict, *, pose_known: bool, off_by_david: bool) -> GestureDecision:
    """Refus communs à « aller voir », dans le même ordre (spec §7.2) : route
    OFF par David, puis pas de pose fraîche (route_driver resterait à zéro,
    mais le refus est DIT au journal plutôt que de laisser croire qu'il part)."""
    if off_by_david:
        return GestureDecision("route_off_by_david", name=name)
    if not pose_known:
        return GestureDecision("no_pose", name=name)
    return GestureDecision("accepted", name=name, order=json.dumps(order))


def decide_turn(intent: dict, *, pose_known: bool, off_by_david: bool) -> GestureDecision:
    """« Tourner » (spec §7.2) : {"angle_deg": a} signé, + = GAUCHE (ROS), ou
    compat {"sens": "gauche"|"droite"|"demi_tour"} (= +90 / −90 / +180).
    "angle_deg" présent fait foi (illisible -> refus, pas de repli sur "sens").
    0 < |a| ≤ TURN_MAX_DEG, sinon refus « hors_bornes » — jamais saturé : un
    pivot faux ne tourne pas. Ordre : {"turn_rad": radians(a)}."""
    if "angle_deg" in intent:
        angle = _number(intent["angle_deg"])
    else:
        sens = intent.get("sens")
        angle = TURN_DEG_COMPAT.get(sens.strip().lower()) if isinstance(sens, str) else None
    if angle is None:
        return GestureDecision("invalid", "illisible")
    if not 0.0 < abs(angle) <= TURN_MAX_DEG:
        return GestureDecision("invalid", "hors_bornes")
    rad = math.radians(angle)
    return _gesture(turn_name(rad), {"turn_rad": rad}, pose_known=pose_known, off_by_david=off_by_david)


def decide_forward(intent: dict, *, pose_known: bool, off_by_david: bool) -> GestureDecision:
    """« Avancer » (spec §7.3) : {"metres": m}, FORWARD_MIN_M ≤ m ≤ FORWARD_MAX_M.
    Négatif -> refus « recul » (on ne recule pas), sous 0,1 m ou trop loin ->
    « hors_bornes ».
    Ordre : {"forward_m": m}."""
    metres = _number(intent.get("metres"))
    if metres is None:
        return GestureDecision("invalid", "illisible")
    if metres < 0.0:
        return GestureDecision("invalid", "recul")
    if not FORWARD_MIN_M <= metres <= FORWARD_MAX_M:
        return GestureDecision("invalid", "hors_bornes")
    return _gesture(forward_name(metres), {"forward_m": metres}, pose_known=pose_known,
                    off_by_david=off_by_david)


@dataclass(frozen=True)
class TourDecision:
    # "accepted" | "unknown" | "no_tour" | "invalid" | "route_off_by_david" | "no_pose" | "too_far"
    effect: str
    poi: Poi | None = None
    reason: str | None = None     # invalid : "sens"
    name: str | None = None       # « tour de <poi> » — MÊME texte que route_driver (goto.tour_name)
    distance: float | None = None  # pose -> CENTRE du tour
    order: str | None = None      # payload route_goto, si accepté


def decide_tour(intent: dict, *, pois, tours, pose, off_by_david: bool) -> TourDecision:
    """« Faire le tour de X » (spec §8.2-§8.3), dans cet ordre : objet
    inconnu -> « unknown » ; connu sans tour (absent du fichier généré) ->
    « no_tour » ; sens autre que TOUR_SENS -> « invalid » (jamais deviné ;
    absent = TOUR_SENS_DEFAUT) ; puis comme « aller voir » : route OFF par
    David, pas de pose fraîche, centre du tour à plus de GOTO_MAX_DISTANCE_M.
    `tours` : {nom de POI: Tour} ; `pose` : (x, y) ou None.
    Ordre : {"name", "orbit_x", "orbit_y", "orbit_r", "orbit_dir"}."""
    poi = resolve_object(intent.get("objet"), pois)
    if poi is None:
        return TourDecision("unknown")
    name = tour_name(poi.name)
    tour: Tour | None = tours.get(poi.name)
    if tour is None:
        return TourDecision("no_tour", poi, name=name)
    sens = intent.get("sens", TOUR_SENS_DEFAUT)
    direction = TOUR_SENS.get(sens.strip().lower()) if isinstance(sens, str) else None
    if direction is None:
        return TourDecision("invalid", poi, reason="sens", name=name)
    if off_by_david:
        return TourDecision("route_off_by_david", poi, name=name)
    if pose is None:
        return TourDecision("no_pose", poi, name=name)
    distance = math.hypot(tour.x - pose[0], tour.y - pose[1])
    if distance > GOTO_MAX_DISTANCE_M:
        return TourDecision("too_far", poi, name=name, distance=distance)
    order = json.dumps({"name": name, "orbit_x": tour.x, "orbit_y": tour.y, "orbit_r": tour.radius,
                        "orbit_dir": direction})
    return TourDecision("accepted", poi, name=name, distance=distance, order=order)


class GotoPolicy:
    """La manœuvre « aller voir » que NOUS avons ordonnée — logique PURE.
    Sert à trois choses :
     - journaliser son issue d'après l'état LATCHÉ de route_driver :
       « arrived » -> goto_arrived ; « goto » puis « off » -> goto_cancelled
       (par notre cancel : stop, abort) ou goto_abort (route_driver l'a
       abandonnée seul : délai, distance — la raison est dans son log) ;
     - autoriser la REPRISE (« go », fader) d'un Didier arrêté par elle :
       rejoin_allowed, qui ne vaut JAMAIS contre un `off` de David ;
     - lever l'ambiguïté de la cause latchée : « cmd » peut dater d'un `off`
       de David suivi d'un `on` ; un état « off » qui SUIT notre manœuvre
       n'est pas un `off` de David (off_by_david).
    La manœuvre cesse d'être « la nôtre » (release) dès que David reprend la
    main (commande `route` on/off vue), que la route repart (état « on »),
    ou qu'une cause est publiée (route_driver la publie au boot et à CHAQUE
    `off` par commande : un `off` qui nous aurait échappé tombe ici)."""

    def __init__(self):
        self._name: str | None = None
        self._target: str | None = None   # POI visé (aller voir, tour) — sa lubie est sautée
        self._seen_goto = False
        self._cancel_by: str | None = None
        self._arrival_speed: float | None = None

    @property
    def owned(self) -> str | None:
        """Nom de l'objet de la manœuvre ordonnée, None si aucune."""
        return self._name

    def accept(self, name: str, target: str | None = None) -> None:
        """`target` : POI visé s'il diffère du nom (tour : « tour de X » vise
        X) ; défaut = le nom (aller voir : le nom EST le POI)."""
        self._reset(name)
        self._target = name if target is None else target

    def cancel(self, by: str) -> None:
        """Nous envoyons « cancel » (stop vocal, abort) : l'issue sera goto_cancelled."""
        if self._name is not None and self._cancel_by is None:
            self._cancel_by = by

    def release(self) -> None:
        self._reset(None)

    def _reset(self, name: str | None) -> None:
        self._name = name
        self._target = name
        self._seen_goto = False
        self._cancel_by = None
        self._arrival_speed = None

    def note_state(self, state: str, speed_in_effect: float):
        """État latché de route_driver -> (type, payload) à journaliser, ou None."""
        if self._name is None:
            return None
        if state == "goto":
            self._seen_goto = True
            return None
        if state == "arrived":
            self._seen_goto = False
            # Référence de la reprise au fader : la vitesse en vigueur à l'arrivée.
            self._arrival_speed = speed_in_effect
            return "goto_arrived", {"name": self._name}
        if state == "off" and self._seen_goto:
            self._seen_goto = False
            if self._cancel_by is not None:
                return "goto_cancelled", {"name": self._name, "by": self._cancel_by}
            return "goto_abort", {"name": self._name}
        if state == "on":
            self.release()
        return None

    def note_route_cmd(self, cmd: str):
        """Commande `route` vue (David, page, notre salve) : la manœuvre n'est
        plus la nôtre. -> (type, payload) si elle était en cours, sinon None."""
        if self._name is None or cmd not in ("on", "off"):
            return None
        event = None
        if self._seen_goto:
            event = "goto_cancelled", {"name": self._name, "by": f"route_{cmd}"}
        self.release()
        return event

    def note_cause(self) -> None:
        self.release()

    def is_target(self, poi_name: str, latched_state: str | None) -> bool:
        """`poi_name` est-il l'objet de NOTRE manœuvre, en cours ou atteint
        (état latché « goto » / « arrived ») ? Sa lubie ne doit pas partir."""
        return self._name is not None and self._target == poi_name and latched_state in ("goto", "arrived")

    def rejoin_allowed(self, latched_state: str | None, off_by_cmd: bool) -> bool:
        """« go » / fader peuvent-ils relancer la route ? Seulement si Didier
        est arrêté par NOTRE manœuvre (arrivé, ou abandonnée -> « off ») et
        qu'aucun `off` de David n'a été vu depuis."""
        return self._name is not None and latched_state in ("arrived", "off") and not off_by_cmd

    def off_by_david(self, latched_state: str | None, cause: str | None, off_by_cmd: bool) -> bool:
        """Refus « route_off_by_david » (spec §3) : `off` vu sur `route`, ou
        état latché « off » de cause « cmd » qui ne fait pas suite à notre
        manœuvre. Route « on », « goto », « arrived » : jamais refusé."""
        if off_by_cmd:
            return True
        return latched_state == "off" and cause == "cmd" and self._name is None

    def fader_rejoins(self, value: float, latched_state: str | None, off_by_cmd: bool) -> bool:
        """Consigne EXTERNE du fader pendant que Didier est ARRIVÉ devant
        l'objet : un geste (fader_moved, même seuil que la fermeture des
        lubies) vers une vitesse > 0 relance la route (spec §1 « ou curseur »)."""
        if latched_state != "arrived" or not self.rejoin_allowed(latched_state, off_by_cmd):
            return False
        if self._arrival_speed is None or value <= 0.0:
            return False
        return fader_moved(value, self._arrival_speed)
