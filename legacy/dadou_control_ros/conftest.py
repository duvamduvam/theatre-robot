import os
import sys

# La racine du dépôt donne accès au package controller/ et, via le symlink
# dadou_utils_ros -> ../dadou_utils_ros, à la lib partagée.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# theatre_contrats (packages/ du mono-dépôt theatre-robot, lot L1a) : le shim
# dadou_utils_ros/utils_static.py en ré-exporte le contrat — sans ce chemin,
# tout import de la lib échoue sur l'hôte (pas de colcon build en dev).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "theatre_contrats"))

# robot_web (catalogue PUR : web_catalog.py, stdlib seule) — lot L1c : le test
# test_buttons_vs_catalogue compare BUTTONS_LAYOUT au catalogue que le robot
# publie, construit par la MÊME fonction depuis legacy/dadou_robot_ros/json.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "dadou_robot_ros", "conf", "ros2_dependencies", "robot_web"))
