import os
import sys

# La racine du dépôt donne accès au package controller/ et, via le symlink
# dadou_utils_ros -> ../dadou_utils_ros, à la lib partagée.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
