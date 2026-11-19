"""Tests hôte de didier_corps_sur (sans ROS ni colcon build).

Lancer : cd packages/didier_corps_sur && ../../.venv/bin/python -m pytest -q -o addopts=
Règle (spec A0 §6.2) : l'attendu est écrit EN DUR, jamais recalculé par la
fonction testée.
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(ICI)
if PKG not in sys.path:
    sys.path.insert(0, PKG)

CONFIG_YAML = os.path.join(PKG, "config", "corps_sur.yaml")
# theatre_contrats (noms de topics du contrat, didier_corps_sur.contrat) : pur, sans ROS.
CONTRATS = os.path.join(os.path.dirname(os.path.dirname(PKG)), "packages", "theatre_contrats")
if CONTRATS not in sys.path:
    sys.path.insert(0, CONTRATS)
import pathlib  # noqa: E402

MONO = pathlib.Path(PKG).resolve().parents[1]
