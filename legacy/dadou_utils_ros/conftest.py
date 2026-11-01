import os
import sys

# Le dépôt entier est le package dadou_utils_ros (__init__.py à la racine) :
# son dossier parent doit être sur sys.path pour que l'import résolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
