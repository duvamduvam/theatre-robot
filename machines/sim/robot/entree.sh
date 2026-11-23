#!/bin/bash
# Entrée du conteneur `robot` de la sim multi-conteneurs (spec L2, décisions 2 et 17) — fichier de
# la SIM, monté en lecture seule par machines/sim/docker-compose.yml ; l'image est celle du Pi
# (machines/robot/docker/Dockerfile) et son script de démarrage est le même que sur le Pi.
#
#  1. REFUS hors domaine 43 ;
#  2. en arrière-plan, dès que le bringup est lancé (donc colcon fini) : complement_sim.launch.py
#     (face_sim si FACE=true, validation_sim_node) ;
#  3. le VRAI bringup, par le script du Pi, avec les arguments de la sim. Ces arguments sont posés
#     ICI, jamais par une variable lue côté robot : sur le Pi, l'ENTRYPOINT n'en passe aucun.
#     use_sim_time:=true n'est pas déclaré par robot_app.launch.py : il atteint drive.launch.py,
#     qui le déclare (chaîne roues en horloge simulée, aucun de ses fichiers modifié).
#     exiger_validation_roues:=false (décision de David du 15/11) : la barrière de jeu est levée en
#     sim — il faut bien y jouer la piste roues qu'on vient y valider ; animations_node l'ignore
#     hors domaine 43.
#     corps_sur_config:=/home/ros2_ws/sim/corps_sur.yaml (lot A0-4) : la configuration du corps
#     sûr pour la SIM (machines/sim/robot/corps_sur.yaml, montée en lecture seule par le compose),
#     refusée par le nœud hors domaine 43 ; sur le Pi, drive.launch.py lit celle de la machine.
#     lidar_materiel:=false (lot A0-6) : pas de pilote du lidar réel en sim (aucun port série) ;
#     le `scan` vient du pont Gazebo pont_lidar.
if [ "${ROS_DOMAIN_ID:-}" != 43 ]; then
    echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, le robot simulé ne tourne qu'en 43"
    exit 2
fi
# Ports SHM Fast DDS morts laissés dans /dev/shm de l'hôte (ipc: host) par une sim précédente :
# AVANT le moindre nœud, sinon l'un d'eux reste bloqué dans rmw_create_node (18/11, menage-shm.sh).
bash /home/ros2_ws/sim/menage-shm.sh

(
    # Le bringup n'apparaît qu'après le colcon du script du Pi (≈ 1-2 min) ; 15 min au plus.
    for _ in $(seq 1 450); do
        pgrep -f "ros2 launch didier_bringup robot_app.launch.py" >/dev/null && break
        sleep 2
    done
    source /opt/ros/${ROS_DISTRO}/setup.sh
    source /home/ros2_ws/install/setup.bash
    exec ros2 launch didier_bringup complement_sim.launch.py face:=${FACE:-false} face_port:=${FACE_PORT:-8766}
) &

exec /bin/bash /home/ros2_ws/src/robot/conf/scripts/launch-ros-in-docker.sh \
    use_sim_time:=true \
    camera_topic:=camera/image_raw camera_compressed:=false \
    perception_topic:=camera/image_raw/compressed exterior_topic:=camera_ext/image_raw \
    web_port:=${WEB_PORT:-8765} web_drive:=${WEB_DRIVE:-false} rehearsal:=${REHEARSAL:-false} \
    exiger_validation_roues:=false corps_sur_config:=/home/ros2_ws/sim/corps_sur.yaml \
    lidar_materiel:=false
