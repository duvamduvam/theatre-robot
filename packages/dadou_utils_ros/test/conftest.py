import os
import sys

# Le package s'importe depuis les sources (pas de colcon build sur l'hôte) :
# sa racine (packages/dadou_utils_ros) porte le module dadou_utils_ros/.
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG)

# theatre_contrats (packages/ du mono-dépôt) : le shim utils_static.py en
# ré-exporte le contrat — sans ce chemin, tout import de la lib échoue sur
# l'hôte.
sys.path.insert(0, os.path.join(os.path.dirname(PKG), "theatre_contrats"))
