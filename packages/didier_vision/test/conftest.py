"""Tests hôte de didier_vision (sans ROS ni colcon build) — lot L1e-3d.

Le package s'importe depuis les sources : sa racine (packages/didier_vision) porte le module
didier_vision/ ET ce dossier test/. Les données (conf/, db/, medias/, models/, mediamtx/) sont
restées dans legacy/dadou_vision_ros/ : DIDIER_VISION_DATA_DIR y pointe AVANT tout import de
vision_config (décision 3 de la spec L1).
Lancer : cd packages/didier_vision && <venv vision> -m pytest -q
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(ICI)                      # packages/didier_vision
PACKAGES = os.path.dirname(PKG)                 # packages/ du mono-dépôt
MONO = os.path.dirname(PACKAGES)
LEGACY_VISION = os.path.join(MONO, "legacy", "dadou_vision_ros")

# Racine des données lue par didier_vision/vision_config.py (sinon : chemin conteneur).
# setdefault : un DIDIER_VISION_DATA_DIR posé par l'appelant l'emporte.
os.environ.setdefault("DIDIER_VISION_DATA_DIR", LEGACY_VISION + "/")

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
