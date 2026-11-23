#!/bin/bash
# Relancer le pilote du lidar (lot A0-6, spec A0 §9) — à lancer SUR LE PI (hôte), en ssh.
# Tue le processus sllidar_node du conteneur PAR SON PID (jamais pkill -f) ; le launch le
# relance de lui-même 5 s plus tard (respawn de lidar_node, robot_app.launch.py). Pendant ce
# temps le corps sûr se verrouille (capteur_perdu) : réarmer ensuite (rearmer-corps-sur.sh).
# Usage : ~/ros2_ws/src/robot/conf/scripts/relancer-lidar.sh
set -euo pipefail
CONTENEUR=dadou-robot-container
PID=$(sudo docker exec "$CONTENEUR" pgrep -x sllidar_node || true)
if [ -z "$PID" ]; then
    echo "sllidar_node ne tourne pas (lidar débranché ? lien /dev/didier-lidar : $(ls -l /dev/didier-lidar 2>&1))"
    exit 1
fi
sudo docker exec "$CONTENEUR" kill "$PID"
echo "sllidar_node (PID $PID) arrêté ; relance attendue dans 5 s"
sleep 8
NOUVEAU=$(sudo docker exec "$CONTENEUR" pgrep -x sllidar_node || true)
if [ -n "$NOUVEAU" ] && [ "$NOUVEAU" != "$PID" ]; then
    echo "OK : relancé (PID $NOUVEAU)"
else
    echo "ÉCHEC : pas de nouveau sllidar_node après 8 s" ; exit 1
fi
