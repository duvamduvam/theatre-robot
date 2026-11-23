#!/bin/bash
# Réarmer le corps sûr du robot (lot A0-6, spec A0 §9) — à lancer SUR LE PI (hôte), en ssh.
# Publie UNE fois sur /<robot>/corps_sur/rearmer (std_msgs/Empty) dans le conteneur, après avoir
# vu l'abonné (-w 1 : sans lui, la CLI perd le message), puis lit le journal du nœud.
# Le nœud ne réarme que si AUCUNE cause n'est présente (lidar sain depuis sante_s, pas d'e_stop) : un refus est normal tant que la cause est là, il est écrit dans son journal
# (`sudo docker logs dadou-robot-container | grep réarmement`).
# Usage : ~/ros2_ws/src/robot/conf/scripts/rearmer-corps-sur.sh
set -euo pipefail
CONTENEUR=dadou-robot-container
# Namespace du robot (lot L1b) : même nom que le conteneur (ROBOT_NAME, défaut didier).
NS="/${ROBOT_NAME:-didier}"
sudo docker exec -e NS="$NS" "$CONTENEUR" bash -c '
    source /opt/ros/${ROS_DISTRO}/setup.sh && source /home/ros2_ws/install/setup.bash
    ros2 topic pub $NS/corps_sur/rearmer std_msgs/msg/Empty "{}" --once -w 1 >/dev/null
    echo "réarmement demandé sur $NS/corps_sur/rearmer ; dernières lignes du nœud :"
'
sleep 1
sudo docker logs --since 5s "$CONTENEUR" 2>&1 | grep -i "corps_sur" | tail -5 || true
