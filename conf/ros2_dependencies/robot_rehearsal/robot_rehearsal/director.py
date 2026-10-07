"""Ordonnanceur du régisseur — machine à états PURE : tick(now_s) -> actions.

Garanties (testées) :
 - une panne démarre à son instant, s'arrête à instant + durée (ou tout de
   suite si ponctuelle) ; JAMAIS au-delà de FAULT_MAX_DURATION_S (déjà borné
   au chargement, re-borné ici par sécurité) ;
 - deux pannes sur la même CIBLE ne se chevauchent pas : la seconde est
   SAUTÉE (action "skip"), jamais empilée ;
 - abort() arrête tout ce qui est actif, en une fois ;
 - la fin du scénario (duration_s) arrête tout ce qui reste actif.
Le node exécute les actions ; ce module ne touche à rien.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from robot_rehearsal.contracts import FAULT_MAX_DURATION_S
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
        """Arrête tout ce qui est actif et clôt le scénario."""
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

    def _stop(self, fid: str, now_s: float) -> Action:
        fault = next(f for f in self.scenario.faults if f.id == fid)
        self._status[fid] = "done"
        self._active_targets.pop(fault.target, None)
        self._stop_at.pop(fid, None)
        return Action("stop", fault, now_s)

    def tick(self, now_s: float) -> List[Action]:
        if not self._started or self._ended:
            return []
        rel = now_s - self._t0
        actions: List[Action] = []
        # 1. arrêts dus (avant les démarrages : libère les cibles)
        for fid, stop_at in sorted(self._stop_at.items(), key=lambda kv: kv[1]):
            if rel >= stop_at:
                actions.append(self._stop(fid, now_s))
        # 2. démarrages dus
        for f in self.scenario.faults:
            if self._status[f.id] != "pending" or rel < f.t_s:
                continue
            if f.target in self._active_targets:
                self._status[f.id] = "skipped"
                actions.append(Action("skip", f, now_s))
                continue
            self._status[f.id] = "active"
            actions.append(Action("start", f, now_s))
            dur = min(f.duration_s, FAULT_MAX_DURATION_S[f.type])
            if dur <= 0.0:
                # Ponctuelle : start et stop dans le même tick.
                actions.append(self._stop(f.id, now_s))
            else:
                self._active_targets[f.target] = f.id
                self._stop_at[f.id] = f.t_s + dur
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
