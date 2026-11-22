#!/bin/bash
# Entrée du conteneur `monde` de la sim multi-conteneurs (spec L2, décision 18) : vérifie le
# domaine 43, construit SES packages, lance monde.launch.py (gz, pont, matériel simulé). Le robot,
# la vision et la télécommande ont chacun leur conteneur (machines/sim/docker-compose.yml).
set -e
# Garde 43 AVANT tout (42 = le vrai Didier) : le compose pose 43 en littéral, on le revérifie.
if [ "${ROS_DOMAIN_ID:-}" != 43 ]; then
    echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, le monde de la sim ne tourne qu'en 43"
    exit 2
fi
source /opt/ros/${ROS_DISTRO}/setup.sh
# Ports SHM Fast DDS morts laissés dans /dev/shm de l'hôte (ipc: host) par une sim précédente :
# AVANT le moindre nœud (18/11, machines/sim/menage-shm.sh, monté avec machines/ en lecture seule).
bash /home/ros2_ws/machines/sim/menage-shm.sh
cd /home/ros2_ws/

# build/ et install/ ne sont pas persistés (décision 11) : colcon à chaque `up`, jamais d'install
# périmé. La liste = les packages copiés par monde/Dockerfile (didier_core : bibliothèque de la
# répétition et du jeu, aucun de ses nœuds n'est lancé ici ; didier_corps_sur : relancé par les
# épreuves CS seulement, A0-4).
colcon build --packages-select theatre_contrats theatre_interfaces dadou_utils_ros didier_core \
    didier_description didier_sim didier_rehearsal didier_jeu didier_corps_sur
source /home/ros2_ws/install/setup.bash

# Audios privés (14/11) : medias/audios/ est le dossier privé du PC monté en lecture seule
# (compose). Absent sur le PC, Docker le crée VIDE : la sim démarre quand même, mais l'écrivain
# des données (conteneur robot) refuserait toute séquence à audio. Le dire ici, en tête du journal.
python3 -m theatre_contrats.donnees verifier-audios /home/ros2_ws/src/robot /home/ros2_ws/src/robot/medias/audios \
    || echo "AVERTISSEMENT audios privés : dossier monté non conforme au manifeste (DIDIER_MEDIAS_PRIVES, docs/operations.md)"

exec ros2 launch didier_sim monde.launch.py world:=${WORLD:-stage} headless:=${HEADLESS:-false}
