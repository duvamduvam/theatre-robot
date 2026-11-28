"""Tests hôte de theatre_gabarit (sans ROS ni colcon build).

Lancer : cd packages/theatre_gabarit && ../../.venv/bin/python -m pytest -q -o addopts=
Règle (spec L3 décision 7) : l'attendu est écrit EN DUR, jamais recalculé par le code testé.
"""
import os
import pathlib
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRATS = os.path.join(os.path.dirname(PKG), "theatre_contrats")
for chemin in (PKG, CONTRATS):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

MONO = pathlib.Path(PKG).resolve().parents[1]
