"""Tests hôte de didier_vision (sans ROS ni colcon build) — lot L1e-3d.

Le package s'importe depuis les sources : sa racine (packages/didier_vision) porte le module
didier_vision/ ET ce dossier test/. La vision n'a aucune donnée suivie (sa db/ et sa voix sont des
fichiers d'exécution posés par Ansible) : depuis L1e-4e (11/11) DIDIER_VISION_DATA_DIR pointe, AVANT
tout import de vision_config (décision 3 de la spec L1), vers un dossier TEMPORAIRE jetable (la
config y crée db/ à l'import) — plus vers legacy/dadou_vision_ros/, qui ne garde que de la doc.
conf/ et mediamtx/ sont dans machines/vision/ (src/vision/conf/ sur le Pi) : les tests hôte ne
lisent pas <racine>/conf/.
Lancer : cd packages/didier_vision && .venv/bin/python -m pytest -q -o addopts=
"""
import atexit
import os
import shutil
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(ICI)                      # packages/didier_vision
PACKAGES = os.path.dirname(PKG)                 # packages/ du mono-dépôt
MONO = os.path.dirname(PACKAGES)

# Racine des données lue par didier_vision/vision_config.py (sinon : chemin conteneur).
# setdefault : un DIDIER_VISION_DATA_DIR posé par l'appelant l'emporte.
if not os.environ.get("DIDIER_VISION_DATA_DIR"):
    _donnees = tempfile.mkdtemp(prefix="didier-vision-donnees-")
    atexit.register(shutil.rmtree, _donnees, ignore_errors=True)
    os.environ["DIDIER_VISION_DATA_DIR"] = _donnees + "/"

for chemin in (
    PKG,
    # theatre_contrats : le shim dadou_utils_ros/utils_static.py en ré-exporte le contrat —
    # sans ce chemin, tout import de la lib échoue sur l'hôte (pas de colcon build en dev).
    os.path.join(PACKAGES, "theatre_contrats"),
    # dadou_utils_ros (lib partagée, package de packages/ depuis L1e-3a).
    os.path.join(PACKAGES, "dadou_utils_ros"),
):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)
