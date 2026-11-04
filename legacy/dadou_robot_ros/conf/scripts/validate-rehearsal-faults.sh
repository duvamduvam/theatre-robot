#!/bin/bash
# V-R2 — vérification REJOUABLE du régisseur de pannes (étude §11.5), DANS le
# conteneur sim : monde `rue`, chaîne roues + rehearsal.launch.py (scénario
# demo, autostart false) déjà lancés, route OFF. Sortie : table + code retour.
#
# T1 départ + start    : téléportation, route on, speed 1, « start » au régisseur
# T2 chien de garde    : pendant la panne zero1 (t=50..58), on GÈLE le régisseur
#                        (SIGSTOP) -> le relais doit retomber en passant < 1 s
#                        -> Didier repart (cmd_vel_follow non nul) ; puis SIGCONT
# T3 reboot            : après « reboot » (kill route_driver), le launch le
#                        respawne et le régisseur renvoie route on -> journal
#                        route_reenable, et un route_driver vivant
# T4 couverture        : chaque id du scénario a fault_start ET fault_stop au
#                        journal (aucun fault_error), et scenario_end présent
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
# Namespace du robot (lot L1b) : les nœuds vivent sous /<ROBOT_NAME>/ (défaut
# /didier/). Un nom RELATIF tapé dans la CLI se résout à la RACINE, pas dans ce
# namespace : chaque topic est donc préfixé par $NS, placé JUSTE APRÈS le verbe
# (`ros2 topic pub $NS/x …`, options après) — forme gravée par
# robot/tests/unit/test_namespace_contract.py.
NS="/${ROBOT_NAME:-didier}"
JDIR=/home/ros2_ws/log/rehearsal
# num <topic préfixé $NS/…> <champ>
num() { for i in 1 2 3; do v=$(timeout 4 ros2 topic echo $1 --once --field "$2" 2>/dev/null | grep -E -m1 '^-?[0-9]'); [ -n "$v" ] && { echo "$v"; return; }; sleep 1; done; echo "NaN"; }
# P <topic RELATIF au robot (route, rehearsal/cmd…)> <msg> : préfixé ici.
P() { timeout 15 ros2 topic pub $NS/$1 robot_interfaces/msg/StringTime "{msg: \"$2\"}" -1 >/dev/null 2>&1; }
ok=0; ko=0
# PRÉCONDITIONS (vérifiées avant de dérouler : un processus absent donnerait un
# fault_error légitime du régisseur, mais ce serait le banc qui est faux, pas
# le code — vécu le 2026-10-07 : sim lancée sans FACE=true -> « visage_fige » KO).
for proc in face_sim route_driver fault_relay director twist_deadman; do
  pgrep -f "/$proc\$|/$proc " >/dev/null || { echo "PRÉCONDITION : processus « $proc » absent (sim avec FACE=true ? chaîne roues ? rehearsal.launch.py ?)"; exit 2; }
done
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }
J() { ls -t $JDIR/*_demo.jsonl 2>/dev/null | head -1; }
has() { grep -q "\"type\": \"$1\"" "$(J)" 2>/dev/null; }
hasid() { grep "\"type\": \"$1\"" "$(J)" 2>/dev/null | grep -q "\"id\": \"$2\""; }

echo "=== T1 départ + start $(date +%T) ==="
P route off; P route restart
timeout 10 gz service -s /world/stage/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
  --req 'name: "dadou_robot", position: {x: 0, y: 0, z: 0.3}, orientation: {w: 1}' >/dev/null 2>&1
sleep 2; P route_speed 1.0; P route on; T0=$(date +%s); P rehearsal/cmd start; sleep 3
verdict "$(has scenario_start && echo 1 || echo 0)" "journal : scenario_start"

echo "=== T2 chien de garde (attente de zero1, t≈50 s) $(date +%T) ==="
for i in $(seq 1 70); do hasid fault_start zero1 && break; sleep 1; done
sleep 1.5; c0=$(num $NS/cmd_vel_follow linear.x); echo "  cmd_vel_follow pendant zero : $c0"
pkill -STOP -f "[d]irector$|[d]irector "; echo "  régisseur gelé $(date +%T.%3N)"
sleep 2.5; c1=$(num $NS/cmd_vel_follow linear.x); echo "  cmd_vel_follow 2,5 s après gel : $c1"
pkill -CONT -f "[d]irector$|[d]irector "
verdict "$(python3 -c "print(1 if '$c0'!='NaN' and abs(float('$c0'))<1e-6 else 0)")" "zero1 : cmd_vel_follow nul pendant la panne"
verdict "$(python3 -c "print(1 if '$c1'!='NaN' and abs(float('$c1'))>1e-3 else 0)")" "régisseur gelé -> relais passant -> Didier repart"

echo "=== T3 reboot (t≈70 s) $(date +%T) ==="
for i in $(seq 1 40); do has route_reenable && break; sleep 1; done
verdict "$(has route_reenable && echo 1 || echo 0)" "journal : route_reenable après kill"
verdict "$(pgrep -f '/route_driver$|/route_driver ' >/dev/null && echo 1 || echo 0)" "route_driver respawné et vivant"

echo "=== T4 couverture (fin du scénario, t=170 s) $(date +%T) ==="
for i in $(seq 1 150); do has scenario_end && break; sleep 1; done
verdict "$(has scenario_end && echo 1 || echo 0)" "journal : scenario_end"
manq=""; for id in batterie freeze1 visage_fige zero1 lubie reboot acoups liaison retard; do
  hasid fault_start $id && hasid fault_stop $id || manq="$manq $id"; done
echo "  ids sans start+stop :${manq:- aucun}"
verdict "$([ -z "$manq" ] && echo 1 || echo 0)" "chaque panne a fault_start et fault_stop"
verdict "$(has fault_error && echo 0 || echo 1)" "aucun fault_error"
echo "  journal : $(J)"
echo "=== V-R2 : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
