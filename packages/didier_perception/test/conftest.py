"""Tests hôte de didier_perception (sans ROS ni colcon build).

Chemins : le package, theatre_contrats (le contrat du tableau) et didier_rehearsal (la VRAIE
carte « chantiers » et director.objects_payload, purs : la séance du 15/11 est rejouée sur le
fichier de la régie, pas sur une copie).
Lancer : cd packages/didier_perception && ../../.venv/bin/python -m pytest -q -o addopts=
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(ICI)
MONO = os.path.dirname(os.path.dirname(PKG))
for chemin in (PKG, os.path.join(MONO, "packages", "theatre_contrats"),
               os.path.join(MONO, "packages", "didier_rehearsal")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)
