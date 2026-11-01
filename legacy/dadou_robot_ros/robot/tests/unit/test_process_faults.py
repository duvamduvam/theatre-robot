"""Pannes de processus (robot_rehearsal.process_faults) — listes blanches
GRAVÉES, refus avant tout appel système, correspondance exacte.
Mutation (2026-10-08) : élargir PAUSABLE -> test_listes_blanches_exactes ;
retirer check() de apply() -> test_apply_refuse_sans_signal."""
import signal

import pytest

from robot_rehearsal import contracts
from robot_rehearsal.process_faults import ProcessFaultError, apply, check, find_pids


def test_listes_blanches_exactes():
    assert contracts.PAUSABLE == ("route_driver", "face_sim", "servos_sim_node", "leds_sim_node",
                                  "animations_node", "gaze_follower", "person_follower")
    assert contracts.KILLABLE == ("route_driver",)
    for interdit in ("twist_mux", "twist_deadman", "wheels_bridge", "parameter_bridge", "gz"):
        assert interdit not in contracts.PAUSABLE and interdit not in contracts.KILLABLE


@pytest.mark.parametrize("action, proc", [
    ("pause", "twist_deadman"), ("kill", "face_sim"), ("explose", "route_driver"), ("pause", ""),
])
def test_apply_refuse_sans_signal(action, proc):
    appels = []
    with pytest.raises(ProcessFaultError):
        apply(action, proc, kill=lambda pid, sig: appels.append((pid, sig)),
              pgrep=lambda args: "123\n")
    assert appels == []


def test_apply_signale_les_pids_trouves():
    appels = []
    pids = apply("pause", "face_sim", kill=lambda pid, sig: appels.append((pid, sig)),
                 pgrep=lambda args: "12\n34\n")
    assert pids == [12, 34]
    assert appels == [(12, signal.SIGSTOP), (34, signal.SIGSTOP)]
    assert apply("resume", "face_sim", kill=lambda *a: appels.append(a), pgrep=lambda a: "12\n")[0] == 12
    assert appels[-1] == (12, signal.SIGCONT)
    assert apply("kill", "route_driver", kill=lambda *a: appels.append(a), pgrep=lambda a: "")== []


def test_find_pids_motif_exact():
    motifs = []
    find_pids("route_driver", pgrep=lambda args: motifs.append(args) or "7\n")
    assert motifs == [[r"/route_driver$|/route_driver "]]
    assert find_pids("x", pgrep=lambda a: "abc\n 9 \n") == [9]


def test_check_pure():
    check("pause", "route_driver"); check("kill", "route_driver")
    with pytest.raises(ProcessFaultError):
        check("kill", "leds_sim_node")


# --- revue adversariale du 2026-10-08 ---------------------------------------

def test_resume_hors_liste_refuse():
    with pytest.raises(ProcessFaultError):
        check("resume", "twist_deadman")


def test_pid_disparu_ignore():
    def kill(pid, sig):
        if pid == 12:
            raise ProcessLookupError
    assert apply("pause", "face_sim", kill=kill, pgrep=lambda a: "12\n34\n") == [34]


def test_resume_command_gravee():
    from robot_rehearsal.process_faults import resume_command
    assert resume_command([12, 34], 5.0) == [
        "sh", "-c", "sleep 5.000 ; kill -CONT 12 2>/dev/null || true ; kill -CONT 34 2>/dev/null || true"]
    assert resume_command([], 5.0) == [] and resume_command([12], 0.0) == []


def test_pause_bounded_lance_le_gardien_detache():
    from robot_rehearsal.process_faults import pause_bounded
    spawned, signaled = [], []
    pids = pause_bounded("face_sim", 3.0, spawn=lambda cmd: spawned.append(cmd),
                         kill=lambda pid, sig: signaled.append((pid, sig)), pgrep=lambda a: "7\n")
    assert pids == [7] and signaled == [(7, signal.SIGSTOP)]
    assert spawned == [["sh", "-c", "sleep 3.000 ; kill -CONT 7 2>/dev/null || true"]]
    with pytest.raises(ProcessFaultError):
        pause_bounded("twist_mux", 3.0, spawn=lambda c: spawned.append(c))
    assert len(spawned) == 1
