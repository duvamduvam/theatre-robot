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

from didier_rehearsal.contracts import KILLABLE, PAUSABLE


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
    """Vérifie, trouve, signale. -> PIDs effectivement signalés (un PID disparu
    entre pgrep et le signal est ignoré, pas une erreur : ProcessLookupError)."""
    check(action, process)
    sig = {"pause": signal.SIGSTOP, "resume": signal.SIGCONT, "kill": signal.SIGTERM}[action]
    done: List[int] = []
    for pid in find_pids(process, pgrep=pgrep):
        try:
            kill(pid, sig)
            done.append(pid)
        except ProcessLookupError:
            continue
    return done


def resume_command(pids: List[int], duration_s: float) -> List[str]:
    """Commande du GARDIEN de pause (pure) : un processus DÉTACHÉ du régisseur
    qui attend `duration_s` puis envoie SIGCONT — la révocation d'une pause ne
    dépend donc pas de la survie du régisseur (revue du 08/10, défaut n°2).
    SIGCONT sur un processus déjà repris ou disparu est sans effet (`|| true`)."""
    if duration_s <= 0 or not pids:
        return []
    conts = " ; ".join(f"kill -CONT {int(pid)} 2>/dev/null || true" for pid in pids)
    return ["sh", "-c", f"sleep {float(duration_s):.3f} ; {conts}"]


def pause_bounded(process: str, duration_s: float, *, spawn: Callable[[List[str]], object] | None = None,
                  kill: Callable[[int, int], None] = os.kill,
                  pgrep: Callable[[List[str]], str] | None = None) -> List[int]:
    """SIGSTOP + gardien détaché qui fera SIGCONT après duration_s quoi qu'il
    arrive au régisseur. Le régisseur enverra AUSSI SIGCONT à la fin normale
    (idempotent). -> PIDs mis en pause."""
    check("pause", process)
    pids = apply("pause", process, kill=kill, pgrep=pgrep)
    cmd = resume_command(pids, duration_s)
    if cmd:
        runner = spawn or (lambda c: subprocess.Popen(c, start_new_session=True,
                                                     stdin=subprocess.DEVNULL,
                                                     stdout=subprocess.DEVNULL,
                                                     stderr=subprocess.DEVNULL))
        runner(cmd)
    return pids
