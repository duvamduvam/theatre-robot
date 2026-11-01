"""Tests de la cinématique différentielle Twist <-> roues (REP 103)."""

import pytest

from robot_drive.diff_drive import DiffDrive

SEPARATION = 0.42
MAX_SPEED = 1.0


@pytest.fixture
def kinematics():
    return DiffDrive(wheel_separation=SEPARATION, max_wheel_speed=MAX_SPEED)


def test_straight_line(kinematics):
    assert kinematics.twist_to_wheels(0.5, 0.0) == (0.5, 0.5)
    assert kinematics.twist_to_wheels(-0.5, 0.0) == (-0.5, -0.5)


def test_stop(kinematics):
    assert kinematics.twist_to_wheels(0.0, 0.0) == (0.0, 0.0)


def test_spin_in_place_positive_is_counter_clockwise(kinematics):
    left, right = kinematics.twist_to_wheels(0.0, 1.0)
    assert left < 0 < right                      # rotation vers la gauche (REP 103)
    assert left == -right


def test_turn_left_right_wheel_faster(kinematics):
    left, right = kinematics.twist_to_wheels(0.5, 1.0)
    assert right > left > 0


def test_saturation_preserves_curvature(kinematics):
    left, right = kinematics.twist_to_wheels(2.0, 1.0)   # demande > max
    assert max(abs(left), abs(right)) == 1.0             # saturé à 1
    # le ratio gauche/droite (donc le rayon de courbure) est préservé
    raw_left = 2.0 - 1.0 * SEPARATION / 2
    raw_right = 2.0 + 1.0 * SEPARATION / 2
    assert left / right == pytest.approx(raw_left / raw_right)


def test_output_always_in_range(kinematics):
    for v in (-3.0, -1.0, 0.0, 1.0, 3.0):
        for w in (-5.0, -1.0, 0.0, 1.0, 5.0):
            left, right = kinematics.twist_to_wheels(v, w)
            assert -1.0 <= left <= 1.0 and -1.0 <= right <= 1.0


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        DiffDrive(wheel_separation=0, max_wheel_speed=1)
    with pytest.raises(ValueError):
        DiffDrive(wheel_separation=0.4, max_wheel_speed=-1)


def test_wheels_to_twist_straight_line(kinematics):
    assert kinematics.wheels_to_twist(0.5, 0.5) == (0.5, 0.0)
    assert kinematics.wheels_to_twist(-0.5, -0.5) == (-0.5, 0.0)


def test_wheels_to_twist_spin_in_place(kinematics):
    linear_x, angular_z = kinematics.wheels_to_twist(-0.5, 0.5)
    assert linear_x == 0.0
    assert angular_z > 0                         # rotation vers la gauche (REP 103)


def test_wheels_to_twist_stop(kinematics):
    assert kinematics.wheels_to_twist(0.0, 0.0) == (0.0, 0.0)


def test_round_trip_twist_wheels_twist_without_saturation(kinematics):
    # Cas sans saturation : l'aller-retour twist -> roues -> twist est fidèle.
    for linear_x, angular_z in [(0.3, 0.5), (-0.2, -0.8), (0.1, 0.0), (0.0, 1.0)]:
        left, right = kinematics.twist_to_wheels(linear_x, angular_z)
        round_trip_linear, round_trip_angular = kinematics.wheels_to_twist(left, right)
        assert round_trip_linear == pytest.approx(linear_x)
        assert round_trip_angular == pytest.approx(angular_z)
