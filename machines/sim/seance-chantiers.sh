#!/usr/bin/env bash
# Séance « Chantiers » en UNE commande (15/11, demande de David : « go » et « parole on »
# retombaient parce que la régie et la tête n'étaient pas lancées par le compose).
# Lance : corps (monde + robot + télécommande), tête (vision, surcouche banc, chat ON),
# régie (rehearsal + sélecteur de jeu) et gaze_follower. SIM-ONLY (domaine 43).
# Ensuite, page scène http://localhost:8765/scene : Route ON, Séance → Démarrer.
#   machines/sim/seance-chantiers.sh          # lance
#   machines/sim/seance-chantiers.sh --stop   # éteint tout
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.banc.yml)
export HEADLESS=true WORLD=chantiers REHEARSAL=true FACE=true DATA_EDIT=true CHAT=true
# Journaux de la sim hors du dépôt et de Nextcloud (16/11) : même expression que le compose ;
# créés par l'utilisateur (sinon Docker les crée root).
export DIDIER_SIM_JOURNAUX="${DIDIER_SIM_JOURNAUX:-$HOME/tmp/didier-sim}"
mkdir -p "$DIDIER_SIM_JOURNAUX"/log "$DIDIER_SIM_JOURNAUX"/log-vision "$DIDIER_SIM_JOURNAUX"/log-telecommande

if [ "${1:-}" = "--stop" ]; then "${COMPOSE[@]}" down; exit 0; fi

# Micro + sortie de la tête choisis d'après ce qui est RÉELLEMENT branché (18/11 : le M50 codé
# en dur était éteint, PipeWire retombait en silence sur le micro du PC qui entendait Didier).
# AVANT le compose : la tête ouvre micro et sortie à son démarrage.
python3 banc-vision/audio_banc.py choisir auto --sans-redemarrer \
  || echo "⚠️ choix audio automatique en échec : asound-pc.conf inchangé"

"${COMPOSE[@]}" up -d
ros() { docker exec "$1" bash -c "source /opt/ros/\$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && $2"; }

# Attendre que colcon ait fini dans chaque conteneur (install/setup.bash présent) et que le
# corps tourne (route_driver est lancé par la régie, donc on guette un node du robot).
for c in didier-sim-monde didier-sim-robot didier-sim-vision; do
  echo -n "attente $c "
  for _ in $(seq 1 120); do docker exec "$c" test -f /home/ros2_ws/install/setup.bash 2>/dev/null && break; echo -n .; sleep 5; done; echo
done
echo -n "attente des nodes du robot "
for _ in $(seq 1 60); do ros didier-sim-monde "ros2 node list 2>/dev/null" | grep -q "/didier/" && break; echo -n .; sleep 5; done; echo

docker exec -d didier-sim-monde bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=chantiers jeu:=true > /tmp/rehearsal.log 2>&1'
docker exec -d didier-sim-robot bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier > /tmp/gaze.log 2>&1'
echo "Séance prête : http://localhost:8765/scene → Route ON, Séance → Démarrer (journal régie : docker exec didier-sim-monde tail -f /tmp/rehearsal.log)"
