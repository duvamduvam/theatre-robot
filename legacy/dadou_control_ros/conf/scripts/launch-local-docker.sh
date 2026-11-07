#!/bin/bash
set -e

echo "[🛠] Initialisation de l'environnement ROS 2..."

# Vérifie que DISPLAY est bien défini
if [ -z "$DISPLAY" ]; then
  export DISPLAY=:0
  echo "[⚠️] DISPLAY non défini, utilisation de :0 par défaut"
fi

# Autorise l'accès X11 côté hôte si possible (optionnel si lancé manuellement)
if command -v xhost &> /dev/null; then
  echo "[🔓] Autorisation X11..."
  xhost +local:root
fi

# Setup ROS 2 et build du workspace
cd /home/ros2_ws/

# Sélectionne automatiquement la distro ROS disponible dans l'image
if [ -f /opt/ros/jazzy/setup.bash ]; then
  source /opt/ros/jazzy/setup.bash
elif [ -f /opt/ros/humble/setup.bash ]; then
  source /opt/ros/humble/setup.bash
else
  echo "[❌] Impossible de trouver setup.bash pour ROS 2 (jazzy ou humble)."
  exit 1
fi

echo "[🔧] Compilation du workspace ROS 2..."
colcon build

source /home/ros2_ws/install/setup.bash

# Exécution du nœud principal
echo "[🚀] Lancement du nœud controller_node..."
# Namespace du robot piloté (lot L1b) : la télécommande publie ses topics
# RELATIFS sous /<ROBOT_NAME>/ (défaut /didier/), comme les nœuds du robot —
# même variable des deux côtés (docker-compose), sinon le robot n'entend rien.
ros2 run controller controller_node --ros-args -r __ns:=/${ROBOT_NAME:-didier}
