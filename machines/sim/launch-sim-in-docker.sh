#!/bin/bash
# Entrypoint du conteneur de simulation : build (rapide, peu de code)
# puis lancement de Gazebo + bridge.
source /opt/ros/${ROS_DISTRO}/setup.sh
cd /home/ros2_ws/

# "didier_core" (ex-"robot", L1e-3c) : paquet ament_python du VRAI code robot (animations_node), rejoué
# en sim derrière le paramètre animations:=true (défaut false, cf. sim.launch.py).
# Toujours buildé ici (colcon build est rapide, pas de compilation C++) : ça
# évite un flag de build séparé pour un flag de lancement, et permet de
# basculer animations:=true à chaud sans rebuild.
# theatre_contrats (lot L1a) : OBLIGATOIRE dès qu'un node importe
# dadou_utils_ros.utils_static (shim) ou le codec StringTime commun.
# didier_jeu (lot A1) : sélecteur de jeu, SIM-ONLY ; dépend de didier_rehearsal
# (garde-fou 43, contrats) et de didier_core (journal) — colcon ordonne seul.
colcon build --packages-select theatre_contrats dadou_utils_ros didier_description didier_sim theatre_interfaces didier_drive didier_web didier_rehearsal didier_core didier_jeu
source /home/ros2_ws/install/setup.bash

# Audios privés (14/11) : medias/audios/ est le dossier privé du PC monté en lecture seule
# (compose). Absent sur le PC, Docker le crée VIDE : la sim démarre quand même, mais l'écrivain
# des données refuserait toute séquence à audio. Le dire ici, en tête du journal.
python3 -m theatre_contrats.donnees verifier-audios /home/ros2_ws/src/robot /home/ros2_ws/src/robot/medias/audios \
    || echo "AVERTISSEMENT audios privés : dossier monté non conforme au manifeste (DIDIER_MEDIAS_PRIVES, docs/operations.md)"

ros2 launch didier_sim sim.launch.py world:=${WORLD:-stage} headless:=${HEADLESS:-false} animations:=${ANIMATIONS:-false} web:=${WEB:-false} web_port:=${WEB_PORT:-8765} web_drive:=${WEB_DRIVE:-false} rehearsal:=${REHEARSAL:-false} face:=${FACE:-false} face_port:=${FACE_PORT:-8766} data_edit:=${DATA_EDIT:-false}
