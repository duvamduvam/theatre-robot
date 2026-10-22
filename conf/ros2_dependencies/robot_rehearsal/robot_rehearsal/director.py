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
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from robot_rehearsal.contracts import (CHAT_FAULT_TOPIC, EXTERNAL_SPEED_DELTA, FAULT_MAX_DURATION_S,
                                       INSTRUCTION_TOPIC, ROUTE_SPEED_TOPIC)
from robot_rehearsal.scenario import Fault, Scenario


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
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            pass
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return min(1.0, max(0.0, value))


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
        self._pending: List[Reenable] = []

    @property
    def route_on(self) -> bool:
        return self._route_on

    def note_state(self, state: str, now_s: float) -> List[str]:
        """État latché de route_driver. « on » reçu après not_before CONFIRME
        les relances en attente (-> leurs ids). « off » (route_driver respawné
        qui démarre éteint) n'annule RIEN."""
        if state not in ("on", "off"):
            return []
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
        elif cmd == "off":
            self._route_on = False
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
