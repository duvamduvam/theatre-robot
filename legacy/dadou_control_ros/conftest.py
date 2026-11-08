import os
import sys

# La racine du dépôt donne accès au package controller/ ; la lib partagée vient
# de packages/dadou_utils_ros (voir plus bas).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# theatre_contrats (packages/ du mono-dépôt theatre-robot, lot L1a) : le shim
# dadou_utils_ros/utils_static.py en ré-exporte le contrat — sans ce chemin,
# tout import de la lib échoue sur l'hôte (pas de colcon build en dev).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "theatre_contrats"))

# dadou_utils_ros (lib partagée, packages/ du mono-dépôt depuis L1e-3a : plus de
# symlink dans le dépôt) : son dossier porte le module du même nom.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "dadou_utils_ros"))

# didier_web (catalogue PUR : web_catalog.py, stdlib seule) — lot L1c : le test
# test_buttons_vs_catalogue compare BUTTONS_LAYOUT au catalogue que le robot
# publie, construit par la MÊME fonction depuis data/json (L1e-4b)
# (package didier_web : packages/ du mono-dépôt depuis L1e-1).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "didier_web"))
