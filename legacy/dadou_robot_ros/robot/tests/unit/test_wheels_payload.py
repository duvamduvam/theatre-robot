"""Tests du parsing pur du payload roues (robot_drive.wheels_payload).

Couvre toutes les formes acceptées par la branche WHEELS de
robot/actions/wheels.py (voir wheels_payload.py pour la correspondance).
"""

import ast
import pathlib

from dadou_utils_ros.utils_static import ANIMATION, BACKWARD, FORWARD, LEFT, RIGHT, SPEED, STOP, \
    WHEELS
from robot_drive import wheels_payload
from robot_drive.wheels_payload import payload_to_pair, payload_to_speed


def imported_roots(module):
    """Racines des paquets réellement importés par un module (via son AST)."""
    tree = ast.parse(pathlib.Path(module.__file__).read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_wheels_key_returns_none():
    assert payload_to_pair({}) is None
    assert payload_to_pair({ANIMATION: True}) is None


def test_stop():
    assert payload_to_pair({WHEELS: STOP}) == STOP


def test_dict_left_right_is_converted_from_percent():
    assert payload_to_pair({WHEELS: {LEFT: 50, RIGHT: -100}}) == (0.5, -1.0)
    assert payload_to_pair({WHEELS: {LEFT: 0, RIGHT: 0}}) == (0.0, 0.0)


def test_pair_list_used_as_is():
    assert payload_to_pair({WHEELS: [0.3, -0.4]}) == (0.3, -0.4)
    assert payload_to_pair({WHEELS: (0.3, -0.4)}) == (0.3, -0.4)


def test_pair_list_is_clamped_to_unit_range():
    assert payload_to_pair({WHEELS: [2.0, -3.0]}) == (1.0, -1.0)


def test_string_forward():
    assert payload_to_pair({WHEELS: FORWARD}) == (0.5, 0.5)


def test_string_backward():
    assert payload_to_pair({WHEELS: BACKWARD}) == (-0.5, -0.5)


def test_string_left():
    assert payload_to_pair({WHEELS: LEFT}) == (-0.5, 0.5)


def test_string_right():
    assert payload_to_pair({WHEELS: RIGHT}) == (0.5, -0.5)


def test_speed_key_returns_none():
    assert payload_to_pair({WHEELS: {SPEED: 80}}) is None


def test_unrecognized_form_returns_none():
    assert payload_to_pair({WHEELS: {"unknown": 1}}) is None
    assert payload_to_pair({WHEELS: 42}) is None
    assert payload_to_pair({WHEELS: [0.1, 0.2, 0.3]}) is None


def test_slider_reel_de_la_telecommande():
    """Format réel émis par le slider double de la télécommande (serial_inputs
    send_sliders) : {WHEELS: {LEFT: <-100..100>, RIGHT: <-100..100>}}."""
    assert payload_to_pair({WHEELS: {LEFT: 100, RIGHT: -100}}) == (1.0, -1.0)
    assert payload_to_pair({WHEELS: {LEFT: -60, RIGHT: 60}}) == (-0.6, 0.6)


def test_up_down_non_pilotes():
    """Le D-pad manette publie {WHEELS: "UP"} / {WHEELS: "down"} (constantes
    UP="UP", DOWN="down") que le robot legacy ne traite pas : on renvoie None."""
    assert payload_to_pair({WHEELS: "UP"}) is None
    assert payload_to_pair({WHEELS: "down"}) is None


def test_payload_to_speed_slider_vitesse():
    """{WHEELS: {SPEED: pct}} (slider vitesse) -> facteur 0..1."""
    assert payload_to_speed({WHEELS: {SPEED: 80}}) == 0.8
    assert payload_to_speed({WHEELS: {SPEED: 0}}) == 0.0
    assert payload_to_speed({WHEELS: {SPEED: 100}}) == 1.0


def test_payload_to_speed_borne():
    assert payload_to_speed({WHEELS: {SPEED: 150}}) == 1.0
    assert payload_to_speed({WHEELS: {SPEED: -20}}) == 0.0


def test_payload_to_speed_none_hors_reglage_vitesse():
    assert payload_to_speed({}) is None
    assert payload_to_speed({WHEELS: STOP}) is None
    assert payload_to_speed({WHEELS: [0.5, 0.5]}) is None
    assert payload_to_speed({WHEELS: {LEFT: 10, RIGHT: 10}}) is None
    assert payload_to_speed({WHEELS: {SPEED: "abc"}}) is None


def test_module_reste_autonome():
    """robot_drive doit s'importer dans le conteneur sim sans rclpy ni
    dadou_utils_ros ni robot.* : on inspecte les imports réels (AST)."""
    roots = imported_roots(wheels_payload)
    assert roots.isdisjoint(("rclpy", "dadou_utils_ros", "robot")), roots


def test_constantes_alignees_avec_utils_static():
    """Anti-dérive : les constantes du protocole sont dupliquées dans
    robot_drive (autonomie du conteneur sim, qui n'a pas dadou_utils_ros) ;
    elles doivent rester identiques aux originales."""
    from dadou_utils_ros import utils_static
    from robot_drive import wheels_payload
    for name in ("WHEELS", "STOP", "FORWARD", "BACKWARD", "LEFT", "RIGHT", "SPEED"):
        assert getattr(wheels_payload, name) == getattr(utils_static, name), name
