#!/bin/bash
# Protocole de validation physique de la bascule cmd_vel (WHEELS_CMD_VEL_ENABLED).
# À exécuter DANS le conteneur robot, ROUES HORS SOL, caméra en face.
# Toutes les preuves (update_cmd, stopped, timings) tombent dans robot.log.
#
# T1 bouton "forward" (format télécommande)  -> roues avant ~3 s puis arrêt auto
# T2 slider vitesse 50% + "forward"          -> PWM à 25 (au lieu de 50)
# T3 e-stop verrouillé puis déverrouillé     -> aucune commande ne passe
# T4 (DERNIER, destructif) kill twist_deadman en plein mouvement
#    -> le deadman LOCAL de wheels_node doit couper < 1 s. Restart service après.
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash

# $1 = valeur JSON sur le fil (chaînes AVEC guillemets JSON : '"forward"'),
# $2 = nombre de publications à 10 Hz, $3 = anim (défaut false)
W() { ros2 topic pub -r 10 -t $2 /wheels robot_interfaces/msg/StringTime "{msg: '$1', time: 0, anim: ${3:-false}}" >/dev/null 2>&1; }

echo "=== T1 bouton forward (3 s) $(date +%T.%3N) ==="
W '"forward"' 30
sleep 3   # arrêt auto attendu : mux 0.5 s puis zéros du deadman

echo "=== T2 slider speed 50 puis forward $(date +%T.%3N) ==="
W '{"speed": 50}' 2
W '"forward"' 20
sleep 3

echo "=== T3 e-stop $(date +%T.%3N) ==="
ros2 topic pub --once /e_stop std_msgs/msg/Bool "{data: true}" >/dev/null 2>&1
sleep 1
W '[0.4, 0.4]' 20   # attendu : AUCUN update_cmd dans le log
ros2 topic pub --once /e_stop std_msgs/msg/Bool "{data: false}" >/dev/null 2>&1
sleep 1

echo "=== T4 kill twist_deadman en plein mouvement $(date +%T.%3N) ==="
W '[0.3, 0.3]' 80 &
sleep 3
pkill -f twist_deadman && echo "twist_deadman tué $(date +%T.%3N)"
# Attendu : dernier apply_twist + ~400 ms -> "wheels stopped" (deadman local)
wait
sleep 2
echo "=== PROTOCOLE TERMINÉ $(date +%T.%3N) — restaurer : systemctl restart robot.service ==="
