"""Scénario de pannes (robot_rehearsal.scenario) — validation à refus explicite,
expansion déterministe par graine. Valeurs gravées : random.Random(42)
.uniform(0, 90) = 57.548 puis .uniform(0, 100) = 2.501 ; Random(7).uniform(0, 90)
= 29.145 (calculées UNE fois hors de la fonction testée, le 2026-10-08).
Mutation : retirer une borne de validation -> test_refus ; ne pas trier ->
test_timeline_triee ; ignorer la graine -> test_graine_deterministe."""
import pytest

from robot_rehearsal.scenario import ScenarioError, load_scenario

BASE = {"name": "demo", "seed": 42, "duration_s": 100.0}


def _sc(*faults, **over):
    d = dict(BASE); d.update(over); d["faults"] = list(faults); return d


def test_graine_deterministe():
    a = {"type": "pause", "process": "face_sim", "t": "random", "duration_s": 10.0}
    b = {"type": "instruction", "text": "tu boudes", "t": "random"}
    sc = load_scenario(_sc(a, b))
    assert [(f.id, f.t_s) for f in sc.faults] == [("f1", 2.501), ("f0", 57.548)]
    assert load_scenario(_sc(a, b)) == sc                       # rejouable
    sc7 = load_scenario(_sc(a, b), seed=7)
    assert sc7.seed == 7 and sc7.faults[-1].t_s == 29.145         # la graine en argument écrase


def test_timeline_triee_et_cibles():
    sc = load_scenario(_sc(
        {"id": "b", "type": "speed", "value": 0.3, "t": 50, "duration_s": 20},
        {"id": "a", "type": "relay", "relay": "cmd_vel_follow", "op": "drop", "p": 0.5, "t": 10, "duration_s": 5},
        {"id": "k", "type": "kill", "process": "route_driver", "t": 10},
    ))
    assert [f.id for f in sc.faults] == ["a", "k", "b"]
    assert sc.faults[0].target == "relay:cmd_vel_follow"
    assert sc.faults[0].params == {"relay": "cmd_vel_follow", "op": "drop", "p": 0.5}
    assert sc.faults[1].params == {"process": "route_driver", "reenable": True}
    assert sc.faults[2].params == {"value": 0.3, "restore": 1.0}


@pytest.mark.parametrize("fault, fragment", [
    ({"type": "pause", "process": "twist_deadman", "t": 0, "duration_s": 1}, "process"),
    ({"type": "pause", "process": "face_sim", "t": 0, "duration_s": 31}, "maximum 30"),
    ({"type": "kill", "process": "route_driver", "t": 0, "duration_s": 5}, "ponctuelle"),
    ({"type": "relay", "relay": "cmd_vel", "op": "zero", "t": 0, "duration_s": 1}, "relay"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "pass", "t": 0, "duration_s": 1}, "op"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "delay", "t": 0, "duration_s": 1}, "delay_ms"),
    ({"type": "relay", "relay": "cmd_vel_follow", "op": "drop", "p": 1.5, "t": 0, "duration_s": 1}, "p"),
    ({"type": "speed", "value": 2, "t": 0, "duration_s": 1}, "value"),
    ({"type": "instruction", "text": "  ", "t": 0}, "text"),
    ({"type": "explosion", "t": 0}, "type"),
    ({"type": "pause", "process": "face_sim", "t": -1, "duration_s": 1}, ".t"),
    ({"type": "pause", "process": "face_sim", "t": 101, "duration_s": 1}, ".t"),
    ({"type": "pause", "process": "face_sim", "t": 0, "duration_s": 1, "bonus": 1}, "inconnues"),
])
def test_refus(fault, fragment):
    with pytest.raises(ScenarioError) as exc:
        load_scenario(_sc(fault))
    assert fragment in str(exc.value)


def test_refus_racine():
    with pytest.raises(ScenarioError):
        load_scenario(_sc(duration_s=0.5))
    with pytest.raises(ScenarioError):
        load_scenario(_sc(name=""))
    with pytest.raises(ScenarioError):
        load_scenario(_sc(seed="42"))
    with pytest.raises(ScenarioError) as exc:
        load_scenario(_sc({"id": "x", "type": "instruction", "text": "a", "t": 0},
                          {"id": "x", "type": "instruction", "text": "b", "t": 1}))
    assert "double" in str(exc.value)


def test_scenario_vide_valide():
    sc = load_scenario(_sc())
    assert sc.faults == () and sc.seed == 42
