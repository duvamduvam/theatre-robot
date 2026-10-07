"""Pannes de PROCESSUS — pause (SIGSTOP/SIGCONT) et kill (SIGTERM) de nodes de
la liste blanche, dans le conteneur sim. La décision est pure (whitelist,
refus) ; l'exécution (pgrep, os.kill) est isolée dans run_* pour être
remplaçable en test.

POURQUOI SIGSTOP : geler un node fige ses publications SANS changer la
topologie — visage figé, servos muets, route qui se tait (-> deadman) — et
SIGCONT rend tout tel quel. POURQUOI jamais la chaîne de sécurité : twist_mux,
twist_deadman, wheels_bridge et le bridge gz ne sont pas dans la liste, et
`check()` refuse tout nom hors liste AVANT tout appel système.
"""
from __future__ import annotations

import os
import signal
import subprocess
from typing import Callable, List

from robot_rehearsal.contracts import KILLABLE, PAUSABLE


class ProcessFaultError(ValueError):
    """Refus : processus hors liste blanche, ou action inconnue."""


def check(action: str, process: str) -> None:
    """Décision PURE : lève si (action, process) n'est pas autorisé."""
    if action in ("pause", "resume"):
        allowed = PAUSABLE
    elif action == "kill":
        allowed = KILLABLE
    else:
        raise ProcessFaultError(f"action inconnue {action!r}")
    if process not in allowed:
        raise ProcessFaultError(f"{action} refusé : « {process} » hors liste blanche {list(allowed)}")


def find_pids(process: str, *, pgrep: Callable[[List[str]], str] | None = None) -> List[int]:
    """PIDs dont la ligne de commande se TERMINE par /<process> (l'exécutable
    installé par colcon : .../lib/<pkg>/<process>) — pas de correspondance
    partielle (« route_driver » ne doit pas attraper « route_driver_test »)."""
    runner = pgrep or (lambda args: subprocess.run(["pgrep", "-f", *args], capture_output=True,
                                                   text=True).stdout)
    out = runner([rf"/{process}$|/{process} "])
    return [int(p) for p in out.split() if p.strip().isdigit()]


def apply(action: str, process: str, *, kill: Callable[[int, int], None] = os.kill,
          pgrep: Callable[[List[str]], str] | None = None) -> List[int]:
    """Vérifie, trouve, signale. -> PIDs touchés (vide si rien ne tournait)."""
    check(action, process)
    sig = {"pause": signal.SIGSTOP, "resume": signal.SIGCONT, "kill": signal.SIGTERM}[action]
    pids = find_pids(process, pgrep=pgrep)
    for pid in pids:
        kill(pid, sig)
    return pids
