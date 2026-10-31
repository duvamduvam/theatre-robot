"""Jeu de réflexion (vision/ai/thinking_show.py) : bornes gravées en dur."""
import random

from vision.ai.thinking_show import ThinkingShow


def _run(seed, until=20.0, step=0.1):
    show = ThinkingShow(random.Random(seed))
    actions = [(0.0, a) for a in show.start(0.0)]
    t = 0.0
    while t < until:
        t = round(t + step, 3)
        actions += [(t, a) for a in show.tick(t)]
    return show, actions


def test_visage_reflechit_d_abord():
    show = ThinkingShow(random.Random(1))
    assert show.start(0.0) == [("face", "reflechit")]
    assert show.active
    assert show.tick(0.1) == []           # délai avant le premier coup d'œil


def test_au_plus_trois_coups_d_oeil_bornes():
    # 3 = 1 ordre + 2 réarmements : sous la limite du robot (3 réarmements).
    for seed in range(50):
        show, actions = _run(seed)
        looks = [(t, a[1]) for t, a in actions if a[0] == "look"]
        assert 1 <= len(looks) <= 3
        for t, look in looks:
            assert 15.0 <= abs(look["angle_deg"]) <= 35.0
            assert 1000 <= look["hold_ms"] <= 1600
            assert t <= 12.0
        assert not show.active


def test_le_hasard_varie_le_jeu():
    jeux = set()
    for seed in range(20):
        _show, actions = _run(seed)
        jeux.add(tuple(a[1]["angle_deg"] for _t, a in actions if a[0] == "look"))
    assert len(jeux) >= 15


def test_stop_coupe_net():
    show = ThinkingShow(random.Random(3))
    show.start(0.0)
    show.stop()
    assert not show.active
    assert show.tick(5.0) == []


def test_timeout_rend_le_visage_sans_coup_d_oeil():
    show = ThinkingShow(random.Random(4))
    show.start(0.0)
    assert show.tick(12.0) == [("face", "stop")]   # échéance : visage rendu
    assert not show.active
    assert show.tick(12.1) == []


def test_reste_pensif_apres_les_coups_d_oeil():
    show, actions = _run(6, until=11.0)
    assert show.active                     # pas de visage rendu avant l'échéance
    assert ("face", "stop") not in [a for _t, a in actions]


def test_restart_repart_a_zero():
    show, _ = _run(5)
    assert show.start(30.0) == [("face", "reflechit")]
    looks = []
    t = 30.0
    while t < 50.0:
        t = round(t + 0.1, 3)
        looks += [a for a in show.tick(t) if a[0] == "look"]
    assert 1 <= len(looks) <= 3
