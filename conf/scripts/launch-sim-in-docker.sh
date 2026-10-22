#!/bin/bash
# Entrypoint du conteneur de simulation : build (rapide, peu de code)
# puis lancement de Gazebo + bridge.
source /opt/ros/${ROS_DISTRO}/setup.sh
cd /home/ros2_ws/

# "robot" : paquet ament_python du VRAI code robot (animations_node), rejoué
# en sim derrière le paramètre animations:=true (défaut false, cf. sim.launch.py).
# Toujours buildé ici (colcon build est rapide, pas de compilation C++) : ça
# évite un flag de build séparé pour un flag de lancement, et permet de
# basculer animations:=true à chaud sans rebuild.
colcon build --packages-select robot_description robot_sim robot_interfaces robot_drive robot_web robot_rehearsal robot
source /home/ros2_ws/install/setup.bash

ros2 launch robot_sim sim.launch.py world:=${WORLD:-stage} headless:=${HEADLESS:-false} animations:=${ANIMATIONS:-false} web:=${WEB:-false} web_port:=${WEB_PORT:-8765} web_drive:=${WEB_DRIVE:-false} rehearsal:=${REHEARSAL:-false} face:=${FACE:-false} face_port:=${FACE_PORT:-8766}
