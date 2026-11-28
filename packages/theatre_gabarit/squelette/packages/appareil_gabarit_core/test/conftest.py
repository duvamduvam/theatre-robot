"""Tests hôte de appareil_gabarit_core (sans ROS ni colcon build).

Lancer : cd packages/appareil_gabarit_core && ../../.venv/bin/python -m pytest -q -o addopts=
Règle (spec L3 décision 7) : l'attendu est écrit EN DUR, jamais recalculé par le code testé ;
une règle faussée doit faire rougir au moins un test (mutation, notée dans la PR).
"""
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parents[1]
MONO = PKG.parents[1]
for chemin in (PKG, MONO / "packages" / "theatre_contrats", MONO / "packages" / "theatre_gabarit"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
