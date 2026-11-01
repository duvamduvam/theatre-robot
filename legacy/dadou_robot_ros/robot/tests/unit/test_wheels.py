"""Tests de Wheels avec un PCA9685 factice : mapping PWM et surtout le deadman.

Le deadman est la protection contre l'emballement des roues (incidents déjà
survenus) : 400 ms sans commande en manuel, échéance absolue basée sur la
durée d'animation sinon. Ces tests couvrent le correctif du trou pendant les
animations.
"""

import pytest

from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import ANIMATION, DURATION, WHEELS
from robot.robot_config import config
from robot.actions.wheels import Wheels

T0 = 1_000_000


class FakeChannel:
    def __init__(self):
        self.duty_cycle = 0


class FakePCA:
    def __init__(self):
        self.channels = [FakeChannel() for _ in range(16)]
        self.frequency = None


@pytest.fixture
def clock(monkeypatch):
    state = {"now": T0}
    monkeypatch.setattr(TimeUtils, "current_milli_time", staticmethod(lambda: state["now"]))
    return state


@pytest.fixture
def wheels(clock):
    return Wheels(config, pca9685=FakePCA())


def moving(wheels):
    return wheels.left_pwm.duty_cycle > 0 or wheels.right_pwm.duty_cycle > 0


def test_pair_command_sets_pwm_and_directions(wheels):
    wheels.update({WHEELS: [0.5, 0.5], ANIMATION: False})
    assert wheels.left_pwm.duty_cycle == wheels.right_pwm.duty_cycle > 0
    assert wheels.dir_left.duty_cycle == 0 and wheels.dir_right.duty_cycle == 0

    wheels.update({WHEELS: [0.6, -0.6], ANIMATION: False})
    assert wheels.dir_left.duty_cycle == 0           # avant
    assert wheels.dir_right.duty_cycle == wheels.MAX_DIR  # arrière


def test_stop_command_zeroes_pwm(wheels):
    wheels.update({WHEELS: [0.5, 0.5], ANIMATION: False})
    wheels.update({WHEELS: "stop", ANIMATION: False})
    assert not moving(wheels)


def test_manual_deadman_stops_after_400ms(wheels, clock):
    wheels.update({WHEELS: [0.5, 0.5], ANIMATION: False})

    clock["now"] = T0 + 399
    wheels.process()
    assert moving(wheels)

    clock["now"] = T0 + 401
    wheels.process()
    assert not moving(wheels)


def test_animation_deadman_uses_remaining_duration(wheels, clock):
    # animations_node estampille le temps restant (ici 5000 ms) sur l'événement roues
    wheels.update({WHEELS: [0.6, -0.6], ANIMATION: True, DURATION: 5000})

    clock["now"] = T0 + 401
    wheels.process()
    assert moving(wheels)                    # pas de deadman 400 ms pendant l'animation

    clock["now"] = T0 + 5000 + wheels.ANIMATION_STOP_MARGIN - 1
    wheels.process()
    assert moving(wheels)                    # dans la marge

    clock["now"] = T0 + 5000 + wheels.ANIMATION_STOP_MARGIN + 1
    wheels.process()
    assert not moving(wheels)                # animations_node mort : les roues s'arrêtent
    assert wheels.animation_ongoing is False


def test_animation_deadman_fallback_without_duration(wheels, clock):
    wheels.update({WHEELS: [0.5, 0.5], ANIMATION: True})

    clock["now"] = T0 + wheels.ANIMATION_FALLBACK_TIMEOUT + wheels.ANIMATION_STOP_MARGIN - 1
    wheels.process()
    assert moving(wheels)

    clock["now"] = T0 + wheels.ANIMATION_FALLBACK_TIMEOUT + wheels.ANIMATION_STOP_MARGIN + 1
    wheels.process()
    assert not moving(wheels)


def test_animation_stop_message_restores_manual_deadman(wheels, clock):
    wheels.update({WHEELS: [0.6, 0.6], ANIMATION: True, DURATION: 30000})
    wheels.update({WHEELS: "stop", ANIMATION: False})   # STOP de fin d'animation
    assert not moving(wheels)
    assert wheels.animation_ongoing is False

    # Une commande manuelle qui suit retombe sur le deadman 400 ms
    clock["now"] = T0 + 10000
    wheels.update({WHEELS: [0.5, 0.5], ANIMATION: False})
    clock["now"] = T0 + 10401
    wheels.process()
    assert not moving(wheels)


def test_apply_twist_forward(wheels):
    # Mode /cmd_vel : Twist avant pur -> les deux roues en avant, même vitesse.
    wheels.apply_twist(0.5, 0.0)
    assert wheels.left_pwm.duty_cycle == wheels.right_pwm.duty_cycle > 0
    assert wheels.dir_left.duty_cycle == 0 and wheels.dir_right.duty_cycle == 0


def test_apply_twist_backward(wheels):
    wheels.apply_twist(-0.5, 0.0)
    assert wheels.left_pwm.duty_cycle == wheels.right_pwm.duty_cycle > 0
    assert wheels.dir_left.duty_cycle == wheels.MAX_DIR
    assert wheels.dir_right.duty_cycle == wheels.MAX_DIR


def test_apply_twist_pivot(wheels):
    # angular_z > 0 = rotation vers la gauche (REP 103) : roue gauche en arrière,
    # roue droite en avant, vitesses symétriques.
    wheels.apply_twist(0.0, 1.0)
    assert wheels.dir_left.duty_cycle == wheels.MAX_DIR      # gauche en arrière
    assert wheels.dir_right.duty_cycle == 0                  # droite en avant
    assert wheels.left_pwm.duty_cycle == wheels.right_pwm.duty_cycle > 0


def test_apply_twist_zero_stops_pwm(wheels):
    wheels.apply_twist(0.5, 0.0)
    assert moving(wheels)
    wheels.apply_twist(0.0, 0.0)          # Twist nul -> coupure franche (pas de MIN_PWM)
    assert not moving(wheels)


def test_apply_twist_manual_deadman_still_active(wheels, clock):
    # Dernier rempart : si la chaîne ROS amont se tait, le deadman 400 ms coupe.
    wheels.apply_twist(0.5, 0.0)
    assert wheels.animation_ongoing is False   # pas de logique animation en mode cmd_vel

    clock["now"] = T0 + 399
    wheels.process()
    assert moving(wheels)

    clock["now"] = T0 + 401
    wheels.process()
    assert not moving(wheels)


def test_new_wheel_event_rearms_animation_deadline(wheels, clock):
    wheels.update({WHEELS: [0.6, 0.6], ANIMATION: True, DURATION: 10000})

    # Nouvel événement à mi-parcours : temps restant 5000 ms
    clock["now"] = T0 + 5000
    wheels.update({WHEELS: [0.3, 0.3], ANIMATION: True, DURATION: 5000})

    clock["now"] = T0 + 10000 + wheels.ANIMATION_STOP_MARGIN - 1
    wheels.process()
    assert moving(wheels)
    clock["now"] = T0 + 10000 + wheels.ANIMATION_STOP_MARGIN + 1
    wheels.process()
    assert not moving(wheels)


def test_apply_twist_zero_stops_only_once(wheels, monkeypatch):
    """Au repos le twist_deadman inonde de zéros à 20 Hz : stop() ne doit être
    appelé qu'à la transition mouvement->arrêt, pas à chaque zéro (spam log)."""
    calls = []
    original_stop = wheels.stop
    monkeypatch.setattr(wheels, "stop", lambda: (calls.append(1), original_stop())[1])
    wheels.apply_twist(0.3, 0.0)   # roule
    wheels.apply_twist(0.0, 0.0)   # premier zéro -> stop
    wheels.apply_twist(0.0, 0.0)   # zéros suivants -> silence
    wheels.apply_twist(0.0, 0.0)
    assert len(calls) == 1
