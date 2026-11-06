"""Relais de pannes — logique PURE sur un flux de messages horodatés.

Opérations (RELAY_OPS) : pass (transparent) ; drop(p) (jette chaque message
avec probabilité p, graine fixée) ; delay(ms) (file bornée, relâche en retard) ;
freeze (répète le DERNIER message vu avant le gel à chaque arrivée) ; zero
(émet le sentinel ZERO à chaque arrivée — le node le traduit en message nul).

CHIEN DE GARDE : set_op() arme une opération avec une échéance until_ms ET le
relais exige un battement du régisseur (heartbeat) : sans battement depuis
HEARTBEAT_TIMEOUT_MS, il retombe en « pass » tout seul. Régisseur mort = aucune
panne ne reste armée. Toute sortie est une liste de messages à publier.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Any, Deque, List, Optional, Tuple

from didier_rehearsal.contracts import FAULT_MAX_DURATION_S, HEARTBEAT_TIMEOUT_MS, RELAY_OPS

ZERO = object()          # sentinel : « publie un message nul »
DELAY_QUEUE_MAX = 200    # borne dure de la file de retard (20 Hz × 10 s)
# Durée MAX d'une opération, imposée ICI aussi (revue du 08/10, défaut n°3) :
# un ordre sans échéance, ou avec une échéance absurde, est borné par le
# relais lui-même — pas seulement par le régisseur.
RELAY_MAX_MS = int(FAULT_MAX_DURATION_S["relay"] * 1000)


class FaultRelay:
    def __init__(self, name: str, *, seed: int = 0):
        self.name = name
        self._rng = random.Random(seed)
        self._op = "pass"
        self._params: dict = {}
        self._until_ms: Optional[int] = None
        self._last_heartbeat_ms: Optional[int] = None
        self._last_msg: Any = None
        self._queue: Deque[Tuple[int, Any]] = deque()
        self._passthrough_reason = "init"

    @property
    def op(self) -> str:
        return self._op

    def heartbeat(self, now_ms: int) -> None:
        self._last_heartbeat_ms = now_ms

    def set_op(self, op: str, params: dict | None, now_ms: int, until_ms: int | None) -> None:
        """Arme une opération jusqu'à until_ms (absolu, horloge monotone), BORNÉ
        à now + RELAY_MAX_MS ; sans échéance = la borne. Params VALIDÉS avant
        tout effet (ValueError, sans changer l'état courant)."""
        if op not in RELAY_OPS:
            raise ValueError(f"relais {self.name} : opération inconnue {op!r}")
        params = dict(params or {})
        if op == "drop":
            p = params.get("p", 1.0)
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0.0 <= p <= 1.0:
                raise ValueError(f"relais {self.name} : drop.p doit être dans [0, 1], reçu {p!r}")
            params["p"] = float(p)
        if op == "delay":
            d = params.get("delay_ms")
            if isinstance(d, bool) or not isinstance(d, (int, float)) or not 1 <= d <= RELAY_MAX_MS:
                raise ValueError(f"relais {self.name} : delay_ms doit être dans [1, {RELAY_MAX_MS}], reçu {d!r}")
            params["delay_ms"] = int(d)
        self._op = op
        self._params = params
        if op == "pass":
            self._until_ms = None
        else:
            cap = now_ms + RELAY_MAX_MS
            self._until_ms = cap if until_ms is None else min(int(until_ms), cap)
        # Toute nouvelle opération repart d'une file vide : des messages retardés
        # d'un ordre précédent ne doivent pas resurgir sous un autre régime.
        self._queue.clear()

    def _revert(self, reason: str) -> None:
        self._op = "pass"
        self._params = {}
        self._until_ms = None
        self._queue.clear()
        self._passthrough_reason = reason

    def _check(self, now_ms: int) -> None:
        if self._op == "pass":
            return
        if self._until_ms is not None and now_ms >= self._until_ms:
            self._revert("expired")
        elif self._last_heartbeat_ms is None or now_ms - self._last_heartbeat_ms > HEARTBEAT_TIMEOUT_MS:
            self._revert("watchdog")

    def process(self, msg: Any, now_ms: int) -> List[Any]:
        """Un message entrant -> messages à publier maintenant."""
        self._check(now_ms)
        out: List[Any] = []
        if self._op == "pass":
            out.append(msg)
        elif self._op == "drop":
            if self._rng.random() >= self._params.get("p", 1.0):
                out.append(msg)
        elif self._op == "delay":
            if len(self._queue) < DELAY_QUEUE_MAX:
                self._queue.append((now_ms + int(self._params.get("delay_ms", 0)), msg))
            out.extend(self._flush(now_ms))
        elif self._op == "freeze":
            out.append(self._last_msg if self._last_msg is not None else msg)
            return out   # ne met PAS à jour _last_msg : c'est le gel
        elif self._op == "zero":
            out.append(ZERO)
        self._last_msg = msg
        return out

    def tick(self, now_ms: int) -> List[Any]:
        """À cadence fixe : relâche les messages retardés, applique le chien de garde."""
        self._check(now_ms)
        return self._flush(now_ms) if self._op == "delay" else []

    def _flush(self, now_ms: int) -> List[Any]:
        out: List[Any] = []
        while self._queue and self._queue[0][0] <= now_ms:
            out.append(self._queue.popleft()[1])
        return out
