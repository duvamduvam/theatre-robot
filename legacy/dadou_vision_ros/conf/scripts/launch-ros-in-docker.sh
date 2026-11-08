#!/bin/bash

# ROS_DISTRO est fourni par l'image de base (humble, jazzy...) : ne pas coder la distro en dur.
source /opt/ros/${ROS_DISTRO}/setup.sh
cd /home/ros2_ws/

# Sentinelle dans un dossier bind-monté (didier_vision/change) : sa présence déclenche
# un colcon build, puis elle est supprimée. Recréez-la après une modif de code
# pour forcer un rebuild (cf. leçon du parc, dadou_robot_ros).
# Build aussi si install/ n'existe pas encore : premier démarrage d'un
# workspace vierge (cas du banc PC x86, dont le workspace colcon est un
# dossier local jetable — cf. conf/docker/x86/docker-compose-x86.yml). Sur le
# Pi ce cas ne se présente qu'à la première installation : même besoin.
CHANGE_FILE=/home/ros2_ws/src/didier_vision/change
if [ -f "$CHANGE_FILE" ] || [ ! -f /home/ros2_ws/install/setup.bash ]; then
    echo "CHANGE file or empty workspace. Running colcon build..."
    colcon build
    rm -f $CHANGE_FILE
else
    echo "$CHANGE_FILE file not found. Skipping colcon build."
fi

source /home/ros2_ws/install/setup.bash

# V1 : launch file unique (heartbeat vision_status + suivi de personne
# person_tracker), cf. packages/didier_vision/launch/vision.launch.py — remplace le
# `ros2 run didier_vision vision_status` de V0 (single node). Un seul launch,
# supervision propre de l'arrêt des deux nodes (SIGINT).
# CHAT (env du compose, défaut false) → chat_enabled : le node de
# conversation ne démarre que sur activation explicite (micro physique +
# budget LLM payant), même règle sur le Pi et sur le banc PC x86.
# CHAT_REFLEXION (env du compose, défaut absent = false) → reflection_enabled :
# UN SEUL interrupteur pour les deux moitiés du metteur en scène intérieur —
# chat_node le lit lui-même (vision_config.reflection_enabled_from_env) et ce
# script en déduit le lancement de reflection_node. Normalisé ici en
# true/false : IfCondition du launch n'accepte que ces deux mots, alors que la
# variable tolère 1/on/oui (une valeur invalide fera échouer chat_node, pas ce
# script).
case "$(echo "${CHAT_REFLEXION:-}" | tr '[:upper:]' '[:lower:]' | xargs)" in
    1|true|on|oui) REFLECTION_ENABLED=true ;;
    *) REFLECTION_ENABLED=false ;;
esac
# VISION_SIM_CAMERA_TOPIC (env du compose x86 SEULEMENT, jamais celui du Pi) →
# sim_camera_topic : propose la caméra Gazebo comme source d'images à chaud.
# Argument ajouté seulement si non vide : absent = option indisponible (robot).
SIM_CAMERA_ARG=()
if [ -n "$(echo "${VISION_SIM_CAMERA_TOPIC:-}" | xargs)" ]; then
    SIM_CAMERA_ARG=("sim_camera_topic:=$(echo "${VISION_SIM_CAMERA_TOPIC}" | xargs)")
fi
ros2 launch didier_vision vision.launch.py chat_enabled:=${CHAT:-false} reflection_enabled:=${REFLECTION_ENABLED} "${SIM_CAMERA_ARG[@]}"
