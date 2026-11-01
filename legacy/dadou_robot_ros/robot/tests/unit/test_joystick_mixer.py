"""Tests du mixage joystick/inclinomètre -> roues (robot_drive.joystick_mixer).

Ce module remplace robot/move/anglo_meter_translator.py (déplacé dans robot_drive
pour l'autonomie du conteneur sim). Les VALEURS DORÉES ci-dessous ont été relevées
sur l'ancien AngloMeterTranslator avant déplacement : le mixage pur doit les
reproduire EXACTEMENT (mapping en division entière plancher compris).
"""

import ast
import pathlib

import pytest

from robot_drive import joystick_mixer
from robot_drive.joystick_mixer import translate

# Paquets interdits dans robot_drive : le conteneur de simulation est autonome.
FORBIDDEN_IMPORTS = ("rclpy", "dadou_utils_ros", "robot")


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


# forward, turn -> (gauche, droite) : valeurs relevées sur l'implémentation d'origine.
GOLDEN = [
    ("avant pur",            99,   0, (100, 100)),
    ("arriere pur",         -99,   0, (-100, -100)),
    ("pivot gauche",          0, -99, (-100, 100)),
    ("pivot droite",          0,  99, (100, -100)),
    ("diag avant-droite",    99,  99, (100, 0)),
    ("diag avant-gauche",    99, -99, (0, 100)),
    ("diag arriere-droite", -99,  99, (0, -100)),
    ("diag arriere-gauche", -99, -99, (-100, 0)),
    ("demi avant",           50,   0, (50, 50)),
    ("zero",                  0,   0, (0, 0)),
]


@pytest.mark.parametrize("name, forward, turn, expected", GOLDEN)
def test_valeurs_dorees(name, forward, turn, expected):
    assert translate(forward=forward, turn=turn) == expected, name


def test_sortie_toujours_bornee():
    for forward in range(-99, 100, 33):
        for turn in range(-99, 100, 33):
            left, right = translate(forward=forward, turn=turn)
            assert -100 <= left <= 100 and -100 <= right <= 100


def test_module_reste_autonome():
    """robot_drive doit tourner dans le conteneur sim sans rclpy ni dadou_utils_ros
    ni robot.* : on vérifie les imports réels (AST), pas les mentions en commentaire."""
    roots = imported_roots(joystick_mixer)
    assert roots.isdisjoint(FORBIDDEN_IMPORTS), roots
