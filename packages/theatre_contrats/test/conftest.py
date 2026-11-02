import os
import sys

# Le package s'importe depuis les sources (pas de colcon build sur l'hôte).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
