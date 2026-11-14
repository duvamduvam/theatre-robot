#!/bin/bash

# ROS_DISTRO est fourni par l'image de base (humble, jazzy...) : ne pas coder la distro en dur.
source /opt/ros/${ROS_DISTRO}/setup.sh
cd /home/ros2_ws/

# Sentinelle de build (L1e-3c) : dans le package du cœur, GITIGNORÉE (packages/didier_core/change
# sur le PC) ; posée par Ansible (rôle synchronise, `sentinelle_build` de l'hôte) ou le Makefile.
# L2a (spec L2, décision 16) : build aussi si install/ est vide — workspace vierge (image lancée
# seule, sim multi-conteneurs dont build/ et install/ ne sont pas persistés, Pi dont le rôle
# conteneur a vidé build/ après un changement d'image) ; même condition que la vision.
CHANGE_FILE=/home/ros2_ws/src/didier_core/change
if [ -f "$CHANGE_FILE" ] || [ ! -f /home/ros2_ws/install/setup.bash ]; then
    echo "CHANGE file or empty workspace. Running colcon build..."
    colcon build
    rm -f "$CHANGE_FILE"
else
    echo "$CHANGE_FILE file not found. Skipping colcon build."
fi

source /home/ros2_ws/install/setup.bash
# L2a (décision 16) : `exec` (le launch remplace le shell, il reçoit lui-même le signal d'arrêt
# du conteneur) et "$@" — l'ENTRYPOINT du Dockerfile n'en passe aucun, donc sur le Pi le launch
# tourne sans argument comme avant ; seul le compose de la SIM (L2b) en passe, par son entrypoint.
exec ros2 launch didier_bringup robot_app.launch.py "$@"
