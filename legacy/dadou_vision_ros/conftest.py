import os
import sys

# La racine du dépôt donne accès au package vision/ ; la lib partagée du parc
# (pas utilisée par les tests unit/ actuels, mais gardée pour parité avec les
# autres dépôts) vient de packages/dadou_utils_ros (voir plus bas).
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# theatre_contrats (packages/ du mono-dépôt theatre-robot, lot L1a) : le shim
# dadou_utils_ros/utils_static.py en ré-exporte le contrat — sans ce chemin,
# tout import de la lib échoue sur l'hôte (pas de colcon build en dev).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "theatre_contrats"))

# dadou_utils_ros (lib partagée, packages/ du mono-dépôt depuis L1e-3a : plus de
# symlink dans le dépôt) : son dossier porte le module du même nom.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "dadou_utils_ros"))
