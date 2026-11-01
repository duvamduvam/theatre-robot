#!/bin/bash
# V-R1 — vérification REJOUABLE du cheminement de Didier dans la rue simulée
# (étude docs/etude-repetition-simulee.md §11.5). À exécuter DANS le conteneur
# sim (domaine 43), monde `rue`, chaîne roues (drive.launch.py) ET
# rehearsal.launch.py déjà lancés, route OFF. Sortie : une table + code retour
# (0 = tous les seuils tenus). Rien ici ne peut atteindre le vrai robot.
#
# T1 départ      : route on, speed 1.0 -> x progresse (> 2 m en 20 s)
# T2 POI         : au moins « lampadaire_1 » enter puis exit dans le journal
# T3 télécommande: cmd_vel_remote (prio 100) à zéro pendant 3 s -> /cmd_vel
#                  nul alors que la route est ON (la télécommande écrase)
# T4 route off   : /cmd_vel nul < 700 ms (un zéro franc puis le deadman)
# T5 arrivée     : x >= 59 et « route : finished » (budget 240 s à 0,4 m/s)
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
LOG=${REHEARSAL_LOG:-/tmp/rehearsal.log}
START=$(grep -c "" "$LOG")   # on ne lit que les lignes écrites après le début de la passe
J() { tail -n +$((START+1)) "$LOG"; }
# Lectures ROBUSTES : `ros2 topic echo --once` peut rendre un avertissement de
# découverte (« does not appear to be published yet ») ou rien du tout juste
# après un (re)démarrage — on ne garde qu'un NOMBRE, avec 3 tentatives (vécu
# le 2026-10-08 : deux faux KO pour un avertissement et une chaîne vide).
num() { for i in 1 2 3; do v=$(timeout 4 ros2 topic echo --once "$1" --field "$2" 2>/dev/null | grep -E -m1 '^-?[0-9]'); [ -n "$v" ] && { echo "$v"; return; }; sleep 1; done; echo "NaN"; }
X() { num /ground_truth/odom pose.pose.position.x; }
CMD() { num /cmd_vel linear.x; }
R() { timeout 15 ros2 topic pub -1 route robot_interfaces/msg/StringTime "{msg: \"$1\"}" >/dev/null 2>&1; }
S() { timeout 15 ros2 topic pub -1 route_speed robot_interfaces/msg/StringTime "{msg: \"$1\"}" >/dev/null 2>&1; }
ok=0; ko=0
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }

echo "=== T1 départ $(date +%T) ==="
R off; R restart
# Didier au départ : téléportation gz (vérité terrain : le cheminement la voit
# immédiatement ; /odom du DiffDrive, lui, ne la verrait pas — cf. xacro).
timeout 10 gz service -s /world/stage/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
  --req 'name: "dadou_robot", position: {x: 0, y: 0, z: 0.3}, orientation: {w: 1}' >/dev/null 2>&1
sleep 2; S 1.0; x0=$(X); R on; sleep 20; x1=$(X)
echo "  x0=$x0 x1=$x1"
verdict "$(python3 -c "print(1 if '$x0'!='NaN' and '$x1'!='NaN' and float('$x1')-float('$x0')>2.0 else 0)")" "x progresse de plus de 2 m en 20 s"

echo "=== T3 télécommande écrase (prio 100) $(date +%T) ==="
timeout 8 ros2 topic pub -r 10 cmd_vel_remote geometry_msgs/msg/Twist "{}" >/dev/null 2>&1 &
sleep 2; c=$(CMD); wait
echo "  /cmd_vel linear.x pendant remote=0 : $c"
verdict "$(python3 -c "print(1 if '$c'!='NaN' and abs(float('$c'))<1e-6 else 0)")" "/cmd_vel nul sous la télécommande"

echo "=== T2 + T5 arrivée (budget 240 s) $(date +%T) ==="
for i in $(seq 1 48); do J | grep -q "route : finished" && break; sleep 5; done
xf=$(X); echo "  x final = $xf"
verdict "$(J | grep -q 'POI enter : lampadaire_1' && J | grep -q 'POI exit : lampadaire_1' && echo 1 || echo 0)" "POI lampadaire_1 enter puis exit"
verdict "$(python3 -c "print(1 if '$xf'!='NaN' and float('$xf')>=59.0 else 0)")" "x >= 59 (hangar)"
verdict "$(J | grep -q 'route : finished' && echo 1 || echo 0)" "journal : route : finished"

echo "=== T4 route off -> zéro $(date +%T) ==="
R restart; R on; sleep 6; R off; sleep 0.7; c=$(CMD)
echo "  /cmd_vel linear.x 700 ms après off : $c"
verdict "$(python3 -c "print(1 if '$c'!='NaN' and abs(float('$c'))<1e-6 else 0)")" "/cmd_vel nul < 700 ms après route off"

echo "=== V-R1 : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
