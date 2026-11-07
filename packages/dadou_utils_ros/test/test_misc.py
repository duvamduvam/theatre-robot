"""Tests de Misc.mapping, utilisé pour tous les mappages servo/roues -> PWM."""

from dadou_utils_ros.misc import Misc


def test_mapping_linear():
    assert Misc.mapping(0, 0, 100, 0, 180) == 0
    assert Misc.mapping(50, 0, 100, 0, 180) == 90
    assert Misc.mapping(100, 0, 100, 0, 180) == 180


def test_mapping_symmetric_range():
    assert Misc.mapping(0, -99, 99, -100, 100) == 0
    assert Misc.mapping(99, -99, 99, -100, 100) == 100
    assert Misc.mapping(-99, -99, 99, -100, 100) == -100


def test_mapping_clamps_out_of_range_input():
    assert Misc.mapping(150, 0, 100, 0, 180) == 180
    assert Misc.mapping(-10, 0, 100, 0, 180) == 0


def test_mapping_wheel_duty_cycle_range():
    # Le cas réel des roues : 0..100 -> MIN_PWM..MAX_PWM
    assert Misc.mapping(0, 0, 100, 5000, 39318) == 5000
    assert Misc.mapping(100, 0, 100, 5000, 39318) == 39318
