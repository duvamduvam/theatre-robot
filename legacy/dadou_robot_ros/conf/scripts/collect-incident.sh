#!/bin/bash
# Collecteur d'incident (chantier télédiagnostic — docs/etude-telediagnostic.md §6, §9-1).
# Rassemble TOUTES les traces disponibles en un tarball horodaté : le format
# d'entrée standard d'une investigation, humaine ou agent IA (skill /diag).
#
# S'exécute sur le HOST du Pi robot, PAS dans le conteneur : c'est voulu — le
# diagnostic doit fonctionner même quand le conteneur est mort (c'est une des
# pannes à investiguer). Testable sur le PC de dev contre la simulation avec
# CONTAINER=dadou-sim-container LOG_DIR=<chemin des logs sim>.
#
# Usage : ./collect-incident.sh [répertoire_de_sortie]   (défaut ~/incidents)
#   CONTAINER  conteneur docker à inspecter (défaut dadou-robot-container)
#   LOG_DIR    dossier des logs applicatifs côté host (défaut ~/ros2_ws/log —
#              c'est le montage host de /home/ros2_ws/log du conteneur)
#
# Tout est best-effort : une section indisponible est NOTÉE dans son fichier,
# jamais bloquante (pas de set -e : on veut le maximum de traces, pas un
# collecteur qui meurt à la première commande absente).

set -u
CONTAINER="${CONTAINER:-dadou-robot-container}"
LOG_DIR="${LOG_DIR:-$HOME/ros2_ws/log}"
OUT_ROOT="${1:-$HOME/incidents}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_ROOT/incident-$STAMP"
mkdir -p "$OUT"

# Chaque section écrit un fichier ; l'échec y est tracé (et n'arrête rien).
run() { # $1 = fichier de sortie, le reste = commande
  local f="$OUT/$1"; shift
  { echo "\$ $*"; "$@"; } >"$f" 2>&1 || echo "(échec ou indisponible)" >>"$f"
}
# Exécution DANS le conteneur — la CLI ros2 exige le sourcing de l'environnement.
in_ros() {
  docker exec "$CONTAINER" bash -c \
    "source /opt/ros/\$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash 2>/dev/null; $*"
}

echo "Collecte d'incident -> $OUT"

# --- 1. Contexte machine ------------------------------------------------------
run meta.txt        bash -c "date; hostname; uptime; uname -a"
run memoire.txt     free -h
run disque.txt      df -h
run temperature.txt vcgencmd measure_temp          # Pi uniquement (absent ailleurs)
# ⚠️ Plus probant que la température : get_throttled est LATCHÉ (bits 16-19 =
# sous-tension / throttling survenus depuis le boot). Une température relevée
# après coup, robot refroidi, ne prouve rien ; ce masque, si — et c'est
# justement le cas d'une collecte faite APRÈS l'incident, donc toujours.
run throttling.txt  vcgencmd get_throttled
run processus.txt   bash -c "top -bn1 | head -30"
run reseau.txt      ip -br addr
run dmesg.txt       bash -c "dmesg | tail -100"    # OOM-kill, USB, sous-voltage Pi

# --- 2. Docker (supervision + stdout ROS) --------------------------------------
run docker-ps.txt      docker ps -a
run docker-inspect.txt docker inspect --format \
  'restarts={{.RestartCount}} status={{.State.Status}} oom={{.State.OOMKilled}} started={{.State.StartedAt}}' \
  "$CONTAINER"
# ⚠️ docker logs ≠ robot.log : le web_bridge (get_logger ROS) ne logge QU'ici.
run docker-logs.txt docker logs --tail 1000 "$CONTAINER"

# --- 3. Journal applicatif (robot.log, sur le host — survit au conteneur) ------
run robot-log-liste.txt bash -c "ls -lt '$LOG_DIR' 2>/dev/null | head -20"
run robot-log-tail.txt  tail -n 2000 "$LOG_DIR/robot.log"
# Marqueurs INCIDENT (écrits par le futur bouton START — étape 2 du chantier)
grep -n "INCIDENT" "$LOG_DIR/robot.log" >"$OUT/robot-log-marqueurs.txt" 2>/dev/null || true

# --- 4. Graphe ROS (via le conteneur, s'il est vivant) --------------------------
# node list peut revenir VIDE au premier appel (le daemon ros2 vient de naître,
# découverte du graphe pas finie — constaté en sim) : on retente une fois.
ros_nodes() {
  local out; out="$(in_ros 'ros2 node list')"
  [ -z "$out" ] && { sleep 5; out="$(in_ros 'ros2 node list')"; }
  printf '%s\n' "$out"
}
run ros-nodes.txt  ros_nodes
run ros-topics.txt in_ros "ros2 topic list"
for t in cmd_vel animation face audio; do
  run "ros-info-$t.txt" in_ros "ros2 topic info /$t"
done
# hz seulement sur cmd_vel : les topics de contenu sont événementiels (muets au
# repos, hz y bloquerait pour rien). cmd_vel bat à 20 Hz si la chaîne roues tourne.
run ros-hz-cmdvel.txt in_ros "timeout 6 ros2 topic hz /cmd_vel"

# --- 5. Empaquetage -------------------------------------------------------------
tar -czf "$OUT.tar.gz" -C "$OUT_ROOT" "incident-$STAMP"
echo "Tarball : $OUT.tar.gz"
