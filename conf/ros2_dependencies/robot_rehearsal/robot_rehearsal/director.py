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
