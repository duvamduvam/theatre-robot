import os
import sys

# Le dépôt entier est le package dadou_utils_ros (__init__.py à la racine) :
# son dossier parent doit être sur sys.path pour que l'import résolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# theatre_contrats (packages/ du mono-dépôt theatre-robot, lot L1a) : le shim
# dadou_utils_ros/utils_static.py en ré-exporte le contrat — sans ce chemin,
# tout import de la lib échoue sur l'hôte (pas de colcon build en dev).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "packages", "theatre_contrats"))
