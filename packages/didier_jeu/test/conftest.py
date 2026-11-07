"""Tests hôte de didier_jeu (sans ROS ni colcon build).

Chemins : le package lui-même, theatre_contrats (contrat commun), dadou_utils_ros (lib partagée), la racine
de legacy/dadou_robot_ros (robot.diagnostic.journal, module PUR) et
didier_rehearsal (garde-fou check_domain + contrats du régisseur, purs).
Lancer : legacy/dadou_robot_ros/.venv/bin/python -m pytest packages/didier_jeu/test -q
"""
import copy
import os
import sys

import pytest
import yaml

ICI = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(ICI)
MONO = os.path.dirname(os.path.dirname(PKG))
LEGACY_ROBOT = os.path.join(MONO, "legacy", "dadou_robot_ros")
for chemin in (PKG, os.path.join(MONO, "packages", "theatre_contrats"),
               os.path.join(MONO, "packages", "dadou_utils_ros"), LEGACY_ROBOT,
               os.path.join(MONO, "packages", "didier_rehearsal")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

REGLAGES_YAML = os.path.join(PKG, "config", "reglages.yaml")
DEPLACEMENTS_YAML = os.path.join(PKG, "config", "deplacements.yaml")
SEQUENCES = os.path.join(LEGACY_ROBOT, "json", "sequences")


def donnees_reglages():
    with open(REGLAGES_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fabriquer(surcharges=None, pools=None):
    """Sélecteur sur les VRAIS réglages et le VRAI vocabulaire, avec des
    surcharges pointées {"hysteresis.marge": 0.0} (tests de mutation) et des
    pools de séquences factices déterministes."""
    from didier_jeu.reglages import Reglages
    from didier_jeu.repertoire import Sequence, charger_deplacements
    from didier_jeu.selecteur import Selecteur
    data = copy.deepcopy(donnees_reglages())
    for chemin, valeur in (surcharges or {}).items():
        node = data
        cles = chemin.split(".")
        for cle in cles[:-1]:
            node = node[cle]
        node[cles[-1]] = valeur
    if pools is None:
        pools = {
            "accueil": [Sequence("bonjour-a", ("bonjour",), 4.0, "a.json", False, True)],
            "spontanee": [Sequence("spont-a", ("random",), 4.0, "s1.json", False, True),
                          Sequence("spont-b", ("random",), 4.0, "s2.json", False, True)],
        }
    return Selecteur(Reglages(data), pools, charger_deplacements(DEPLACEMENTS_YAML))


@pytest.fixture
def sel():
    return fabriquer()
