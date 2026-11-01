"""Tests de la logique pure de simulation des servos (robot_sim_lib.servos_logic).

Le temps ET le générateur aléatoire sont toujours injectés (jamais
time.time()/random.* non seedé côté production) : chaque test avance une
horloge simulée explicite et seede son propre rng, pour rester déterministe.
"""
import json
import math
import os

import pytest

from robot_sim_lib.servos_logic import (
    JOINT_LIMITS,
    NORMAL,
    RANDOM,
    ServoSim,
    pos99_to_radians,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PARLE_JSON = os.path.join(REPO_ROOT, "json", "sequences", "didier", "parle.json")


def load_left_arm_keyframe():
    """Charge la VRAIE piste left_arm de json/sequences/didier/parle.json
    (séquence jouée en spectacle) : garde-fou anti-régression, cf.
    robot/tests/unit/test_servo_random_mode.py qui applique la même méthode
    côté vrai Servo -- si le JSON dérive, ce test casse aussi."""
    with open(PARLE_JSON) as f:
        sequence = json.load(f)
    _t, keyframe = sequence["left_arm"][0]
    return keyframe


# ======================================================================
# update() : valeur directe / stop / default
# ======================================================================

def test_update_numeric_value_moves_position_directly():
    servo = ServoSim(default_pos=50, now_ms=0)
    servo.update(70, now_ms=0)
    assert servo.position == 70
    assert servo.mode == NORMAL
    # tick() doit republier ce changement une fois (anti-spam : une seule fois).
    assert servo.tick(now_ms=100) == 70
    assert servo.tick(now_ms=200) is None


def test_update_fractional_value_0_1_is_scaled_to_percent():
    # Même quirk que Servo.set_angle : une valeur dans [0,1] est interprétée
    # comme une fraction (0.5 -> 50), pas une position brute.
    servo = ServoSim(default_pos=0, now_ms=0)
    servo.update(0.5, now_ms=0)
    assert servo.position == 50


def test_stop_returns_to_default_pos_and_clears_random_mode():
    servo = ServoSim(default_pos=42, now_ms=0)
    servo.update(90, now_ms=0)
    servo.tick(now_ms=10)  # consomme le dirty du update() numérique
    servo.update("stop", now_ms=20)
    assert servo.position == 42
    assert servo.mode == NORMAL
    assert servo.tick(now_ms=30) == 42  # le retour à default doit être publié


def test_default_dict_changes_default_pos_and_moves_there():
    servo = ServoSim(default_pos=50, now_ms=0)
    servo.update({"default": 25}, now_ms=0)
    assert servo.default_pos == 25
    assert servo.position == 25


# ======================================================================
# Mode random : armement depuis une VRAIE keyframe de séquence
# ======================================================================

def test_random_keyframe_from_real_sequence_arms_random_mode():
    keyframe = load_left_arm_keyframe()

    servo = ServoSim(default_pos=50, now_ms=0)
    servo.update(keyframe, now_ms=0)

    assert servo.mode == RANDOM
    # Bornes exactes de parle.json, piste "left_arm" (cf. json/sequences/didier/parle.json) :
    # si elles changent dans le JSON, ce test doit être mis à jour en même temps.
    assert servo.random_move_min == 60
    assert servo.random_move_max == 95
    assert servo.random_time_min == 500
    assert servo.random_time_max == 1000


def test_random_draws_stay_within_move_and_time_bounds():
    keyframe = load_left_arm_keyframe()  # move [60,95], time [500,1000]
    servo = ServoSim(default_pos=50, now_ms=0, rng=__import__("random").Random(1234))
    servo.update(keyframe, now_ms=0)

    # On observe les tirages RÉELS via random_last_time (état interne), pas
    # via tick()/anti-spam : un tirage peut par hasard retomber sur la même
    # position (60-95 = 36 valeurs possibles) et ne rien publier -- ça ne
    # veut pas dire que la PÉRIODE de tirage a été violée. L'anti-spam de
    # tick() est déjà couvert par test_update_numeric_value_moves_position_directly.
    draws = []  # (instant du tirage, position tirée)
    last_seen = servo.random_last_time
    now_ms = 0
    # 20s d'horloge simulée, pas de 50 ms -- largement assez pour plusieurs
    # tirages (période max 1000 ms).
    while now_ms <= 20_000:
        servo.tick(now_ms)
        if servo.random_last_time != last_seen:
            draws.append((servo.random_last_time, servo.position))
            last_seen = servo.random_last_time
        now_ms += 50

    assert len(draws) >= 5, "pas assez de tirages collectés pour valider les bornes"
    for _, position in draws:
        assert 60 <= position <= 95

    gaps = [t2 - t1 for (t1, _), (t2, _) in zip(draws, draws[1:])]
    for gap in gaps:
        # random_last_time est mis à jour au premier tick constatant le
        # dépassement de random_next_time (tiré dans [500,1000]) : le pas de
        # simulation (50 ms) peut retarder la détection d'au plus 50 ms.
        assert 500 <= gap <= 1000 + 50, gap


def test_random_duration_triggers_automatic_exit():
    servo = ServoSim(default_pos=50, now_ms=0, rng=__import__("random").Random(42))
    servo.update({
        "mode": "random",
        "random move min": 60, "random move max": 95,
        "random time min": 100, "random time max": 200,
        "random duration": 1000,
    }, now_ms=0)
    assert servo.mode == RANDOM

    # Avant l'échéance : toujours en random.
    servo.tick(now_ms=500)
    assert servo.mode == RANDOM

    # Après les 1000 ms de random_duration : sortie automatique.
    servo.tick(now_ms=1500)
    assert servo.mode == NORMAL

    # Une fois sorti, un nouvel ordre random doit pouvoir s'armer (preuve que
    # ce n'est pas resté bloqué en random) :
    servo.update({
        "mode": "random",
        "random move min": 10, "random move max": 20,
        "random time min": 100, "random time max": 200,
    }, now_ms=1500)
    assert servo.mode == RANDOM
    assert servo.random_move_min == 10


def test_random_dict_received_while_random_active_is_ignored():
    servo = ServoSim(default_pos=50, now_ms=0)
    servo.update({
        "mode": "random",
        "random move min": 60, "random move max": 95,
        "random time min": 500, "random time max": 1000,
    }, now_ms=0)

    # Un second ordre random pendant que le premier tourne encore : ignoré
    # ("let the last instruction finish", cf. Servo.update).
    servo.update({
        "mode": "random",
        "random move min": 0, "random move max": 5,
        "random time min": 10, "random time max": 20,
    }, now_ms=10)

    assert servo.random_move_min == 60
    assert servo.random_move_max == 95


# ======================================================================
# Mapping consigne 0-99 -> radians
# ======================================================================

def test_pos99_to_radians_bounds_and_midpoint():
    joint_min, joint_max = -math.pi / 2, math.pi / 2
    assert pos99_to_radians(0, joint_min, joint_max) == pytest.approx(joint_min)
    assert pos99_to_radians(99, joint_min, joint_max) == pytest.approx(joint_max)
    # 50 n'est pas exactement le milieu de 0-99 (qui vaut 49.5) : léger écart
    # assumé, même quirk documenté dans robot.move.gaze_control.consigne_to_radians.
    assert pos99_to_radians(50, joint_min, joint_max) == pytest.approx(0.0, abs=0.02)


def test_joint_limits_cover_all_servo_names():
    assert set(JOINT_LIMITS) == {"neck", "left_arm", "right_arm", "left_eye", "right_eye"}
