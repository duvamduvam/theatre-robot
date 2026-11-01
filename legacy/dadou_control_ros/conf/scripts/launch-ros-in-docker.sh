#!/bin/bash
# Entrypoint du conteneur console (équivalent du script côté robot).
# ROS_DISTRO est fourni par l'image de base (jazzy...) : ne pas coder la distro en dur.
source /opt/ros/${ROS_DISTRO}/setup.sh
cd /home/ros2_ws/

# Sentinelle de build : créer le fichier CHANGE dans controller/ (dossier
# bind-mounté par le compose — la racine du projet ne l'est pas, elle vient
# de l'image) déclenche un colcon build au (re)démarrage. Même convention
# que le robot (robot/change).
CHANGE_FILE=/home/ros2_ws/src/controller/controller/CHANGE
if [ -f "$CHANGE_FILE" ]; then
    echo "CHANGE file found. Running colcon build..."
    colcon build
    rm $CHANGE_FILE
else
    echo "$CHANGE_FILE file not found. Skipping colcon build."
fi

source /home/ros2_ws/install/setup.bash
ros2 run controller controller_node
