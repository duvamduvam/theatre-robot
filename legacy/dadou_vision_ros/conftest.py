import os
import sys

# La racine du dépôt donne accès au package vision/ et, via le symlink
# dadou_utils_ros -> ../dadou_utils_ros, à la lib partagée du parc (pas
# utilisée par les tests unit/ actuels, mais gardée pour parité avec les
# autres dépôts dadou_*_ros au cas où V1/V2 en aient besoin).
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# theatre_contrats (packages/ du mono-dépôt theatre-robot, lot L1a) : le shim
# dadou_utils_ros/utils_static.py en ré-exporte le contrat — sans ce chemin,
# tout import de la lib échoue sur l'hôte (pas de colcon build en dev).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "theatre_contrats"))
