"""Tests hôte de didier_core (sans ROS ni colcon build) — lot L1e-3c.

Le package s'importe depuis les sources : sa racine (packages/didier_core) porte le module
didier_core/ ET ce dossier test/ (les tests s'importent entre eux en `test.unit.…`).
Les données (json/, medias/, db/) vivent dans data/ du mono-dépôt depuis L1e-4b, enfants
directs de la racine comme sur le Pi (src/robot/) : DIDIER_DATA_DIR y pointe AVANT tout import
de robot_config (décision 3 de la spec L1). conf/ est dans machines/robot/ (L1e-4c) :
les tests hôte ne lisent pas <DIDIER_DATA_DIR>/conf/.
Lancer : cd packages/didier_core && ../../.venv/bin/python -m pytest -q -o addopts=
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(ICI)                      # packages/didier_core
PACKAGES = os.path.dirname(PKG)                 # packages/ du mono-dépôt
MONO = os.path.dirname(PACKAGES)
ATELIER = os.path.join(MONO, "atelier")        # firmwares déménagés de legacy/ au lot L1e-4e
DONNEES = os.path.join(MONO, "data")

# Racine des données lue par didier_core/robot_config.py (sinon : chemin conteneur).
# setdefault : un DIDIER_DATA_DIR posé par l'appelant l'emporte (essai sur d'autres données).
os.environ.setdefault("DIDIER_DATA_DIR", DONNEES + "/")

for chemin in (
    PKG,
    # Packages du mono-dépôt importés par les tests sans être installés (pas de colcon
    # build sur l'hôte de dev) : chaque dossier porte le module du même nom.
    os.path.join(PACKAGES, "didier_drive"),
    # didier_sim_lib (logique pure de leds_sim_node / servos_sim_node, paquet didier_sim).
    os.path.join(PACKAGES, "didier_sim"),
    # Protocole/catalogue purs du pont web ; web_bridge_node.py n'est PAS importé (rclpy,
    # aiohttp absents de l'hôte).
    os.path.join(PACKAGES, "didier_web"),
    # Salle de répétition (SIM-ONLY) : route.py, contrats ; les nœuds ne sont pas importés.
    os.path.join(PACKAGES, "didier_rehearsal"),
    # theatre_contrats : le shim dadou_utils_ros/utils_static.py en ré-exporte le contrat —
    # sans ce chemin, tout import de la lib échoue.
    os.path.join(PACKAGES, "theatre_contrats"),
    # dadou_utils_ros (lib partagée, package de packages/ depuis L1e-3a).
    os.path.join(PACKAGES, "dadou_utils_ros"),
    # Firmwares du Pico (odom_protocol.py) et de la télécommande USB (remote_protocol.py) :
    # logique PURE partagée avec les microcontrôleurs, restée dans atelier/firmware/ (main.py, code.py,
    # boot.py ne sont JAMAIS importés sur l'hôte — machine/rp2/board n'y existent pas).
    os.path.join(ATELIER, "firmware", "pico_odometry"),
    os.path.join(ATELIER, "firmware", "remote_usb"),
):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)
