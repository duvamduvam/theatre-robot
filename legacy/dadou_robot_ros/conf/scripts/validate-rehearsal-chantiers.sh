#!/bin/bash
# V-R3 technique — vérification REJOUABLE de la séance « Chantiers » (étude
# §13.8), DANS le conteneur sim : monde `chantiers`, chaîne roues +
# rehearsal.launch.py route:=chantiers scenario:=chantiers (autostart false)
# déjà lancés, route OFF. Sans la tête (chat_node) : on vérifie que le
# régisseur PUBLIE ce que chat_node consommera (chat_instruction,
# rehearsal/chat_fault), pas la conversation elle-même. Sortie : table + code
# retour. Durée ≈ 15 min (scénario 900 s ; l'arrivée est plus tôt, on attend la fin).
#
# T1 départ + start   : téléportation à l'origine, route on, speed 1, « start »
# T2 lubies           : la première lubie TIRÉE (journal scenario_loaded) a son
#                       fault_start ; pendant la lubie cmd_vel_follow est nul
#                       (route_speed 0) ; on joue la FERMETURE TÉLÉCOMMANDE
#                       (route_speed 1.0 = le fader) -> Didier repart ; chaque
#                       lubie publie sa consigne puis "" (chat_instruction)
# T3 pannes chat      : chaque panne `chat` a publié son JSON (op) puis « pass »
# T4 arrivée + POI    : ≥ 25 poi_enter au journal, dans l'ordre du YAML ;
#                       arrivée au pied de la Titan (x ≥ seuil gravé)
# T5 couverture       : les 20 bugs sont tous sortis de `pending` (done/skipped,
#                       jamais error) ; lubies non tirées = `undrawn` ;
#                       scenario_end présent
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
# Namespace du robot (lot L1b) : les nœuds vivent sous /<ROBOT_NAME>/ (défaut
# /didier/). Un nom RELATIF tapé dans la CLI se résout à la RACINE, pas dans ce
# namespace : chaque topic est donc préfixé par $NS, placé JUSTE APRÈS le verbe
# (`ros2 topic pub $NS/x …`, options après) — forme gravée par
# robot/tests/unit/test_namespace_contract.py.
NS="/${ROBOT_NAME:-didier}"
JDIR=/home/ros2_ws/log/rehearsal
ROUTE_YAML=/home/ros2_ws/src/robot_rehearsal/config/chantiers.yaml
SCEN_YAML=/home/ros2_ws/src/robot_rehearsal/config/scenarios/chantiers.yaml
CAP=/tmp/vr3-capture; mkdir -p $CAP
# TYPE EXPLICITE sur chaque `ros2 topic echo` (06/11) : sans lui, le CLI interroge
# d'abord le graphe (daemon) pour deviner le type ; s'il ne voit pas encore l'éditeur il
# sort aussitôt (« does not appear to be published yet ») et la capture reste VIDE —
# 3 KO sur 4 le 06/11 venaient de là. Avec le type, il s'abonne tout de suite et reçoit
# dès que DDS a apparié (mesuré : premier message en 0,8 s).
# num <topic préfixé $NS/…> <champ> [type, défaut Odometry]
num() { for i in 1 2 3; do v=$(timeout 4 ros2 topic echo $1 ${3:-nav_msgs/msg/Odometry} --once --field "$2" 2>/dev/null | grep -E -m1 '^-?[0-9]'); [ -n "$v" ] && { echo "$v"; return; }; sleep 1; done; echo "NaN"; }
# SALVE de 5 s (10 envois à 2 Hz) et pas `-1` : sur le PC de dev, un CLI ros2
# fraîchement lancé met 2 à 4 s à être découvert (erreurs multicast
# IP_ADD_MEMBERSHIP, ~50 conteneurs) — un message unique, et même une salve
# de 1 s, partent dans le vide (vécu le 14/10 : `route on` et `start` perdus,
# Didier immobile 4 min). Toutes les commandes envoyées ici sont idempotentes
# (on/off/restart/vitesse/start) : les doublons ne font que des warnings.
# P <topic RELATIF au robot (route, route_speed, rehearsal/cmd)> <msg> : préfixé ici.
P() { timeout 20 ros2 topic pub $NS/$1 robot_interfaces/msg/StringTime "{msg: \"$2\"}" -t 10 -r 2 >/dev/null 2>&1; }
# --qos-reliability reliable OBLIGATOIRE avec transient_local : un lecteur best-effort (défaut
# du CLI quand le type est donné) ne reçoit PAS l'historique latché — mesuré le 06/11 (vide
# sans, « on » avec ; rclpy reliable : 2,6 s).
# Route en BOUCLE FERMÉE : on renvoie `on`/`off` jusqu'à ce que l'état latché
# route_state le confirme (même logique que la relance du régisseur après kill).
ROUTE() { for i in 1 2; do P route "$1"; st=$(timeout 6 ros2 topic echo $NS/route_state robot_interfaces/msg/StringTime --once --field msg --qos-durability transient_local --qos-reliability reliable 2>/dev/null | head -1); [ "$st" = "$1" ] && return 0; done; echo "  ⚠️ route_state ≠ $1 après 2 salves (dernier : ${st:-aucun})"; return 1; }
ok=0; ko=0
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }
J() { ls -t $JDIR/*_chantiers.jsonl 2>/dev/null | head -1; }
has() { grep -q "\"type\": \"$1\"" "$(J)" 2>/dev/null; }
hasid() { grep "\"type\": \"$1\"" "$(J)" 2>/dev/null | grep -q "\"id\": \"$2\""; }

# PRÉCONDITIONS : le bon monde (la Titan grise existe), les processus que le
# scénario met en pause (un absent = fault_error légitime mais banc faux).
for proc in face_sim leds_sim_node servos_sim_node animations_node gaze_follower route_driver fault_relay director twist_deadman; do
  pgrep -f "/$proc\$|/$proc " >/dev/null || { echo "PRÉCONDITION : processus « $proc » absent (sim avec FACE=true ANIMATIONS=true ? gaze_follower lancé ? chaîne roues ? rehearsal.launch.py route:=chantiers scenario:=chantiers ?)"; exit 2; }
done
timeout 10 gz model --list 2>/dev/null | grep -q titan_grise || { echo "PRÉCONDITION : modèle titan_grise absent (WORLD=chantiers ?)"; exit 2; }
# Le scénario chargé ne se lit PAS sur la ligne de commande (launch passe un
# --params-file temporaire) : on le lit au nom du journal, qui porte le PID du
# régisseur VIVANT (<horodatage>_<pid>_<scénario>.jsonl, cf. director_node).
jpid=$(basename "$(J)" 2>/dev/null | cut -d_ -f3)
[ -n "$jpid" ] && kill -0 "$jpid" 2>/dev/null || { echo "PRÉCONDITION : aucun régisseur vivant avec le scénario chantiers (rehearsal.launch.py route:=chantiers scenario:=chantiers ?)"; exit 2; }

# Captures des topics que chat_node consommera : fichiers relus à la fin.
timeout 1000 ros2 topic echo $NS/chat_instruction robot_interfaces/msg/StringTime --field msg > $CAP/instruction.txt 2>/dev/null &
timeout 1000 ros2 topic echo $NS/rehearsal/chat_fault robot_interfaces/msg/StringTime --field msg > $CAP/chat_fault.txt 2>/dev/null &
timeout 1000 ros2 topic echo $NS/route_speed robot_interfaces/msg/StringTime --field msg > $CAP/route_speed.txt 2>/dev/null &
sleep 2

echo "=== T1 départ + start $(date +%T) ==="
ROUTE off; P route restart
timeout 10 gz service -s /world/stage/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
  --req 'name: "dadou_robot", position: {x: 0, y: 0, z: 0.3}, orientation: {w: 1}' >/dev/null 2>&1
# START AVANT route on : un POI franchi avant le start est ignoré (front « enter »,
# pas un niveau) — Didier entre dans le rayon des Nefs à 0,5 m du départ.
sleep 2; P route_speed 1.0; P rehearsal/cmd start; T0=$(date +%s); ROUTE on; sleep 3
# Verdict PAR L'EFFET (Didier avance), pas par l'état : sur le PC de dev, la
# découverte DDS du CLI ros2 est capricieuse (erreurs multicast
# IP_ADD_MEMBERSHIP, ~50 conteneurs) — `ros2 topic echo $NS/route_state` peut ne
# rien voir alors que les nodes, eux, se parlent (vécu le 14/10).
# Seuil BAS (0,3 m) : le premier POI (les Nefs, rayon 4 m à 2 m du tracé) est
# franchi à ~0,5 m du départ et, s'il est tiré, sa lubie ARRÊTE Didier là
# (vécu au run 5 du 14/10 : x = 0,69 m, verdict faux avec un seuil à 1 m).
# T2 vérifie ensuite l'arrêt et la reprise ; ici on ne juge que « il est parti ».
sleep 6; x1=$(num $NS/ground_truth/odom pose.pose.position.x); echo "  x après 9 s : $x1"
verdict "$(python3 -c "print(1 if '$x1'!='NaN' and float('$x1') > 0.3 else 0)")" "route on : Didier est parti (x > 0,3 m après 9 s)"
verdict "$(has scenario_start && echo 1 || echo 0)" "journal : scenario_start"
# Les lubies tirées (celles qui sont DANS la timeline), dans l'ordre du YAML.
# Lubies tirées, DANS L'ORDRE DE LA MARCHE (la timeline du journal est triée
# par (poi, id) : alphabétique — « bollard » y vient avant « nefs »).
drawn=$(python3 - "$(J)" "$ROUTE_YAML" <<'EOF'
import json, sys, yaml
order = [p["name"] for p in yaml.safe_load(open(sys.argv[2]))["pois"]]
for line in open(sys.argv[1], encoding="utf-8"):
    ev = json.loads(line)
    if ev.get("type") == "scenario_loaded":
        lub = [f for f in ev["payload"]["timeline"] if f["type"] == "lubie"]
        lub.sort(key=lambda f: order.index(f["trigger_poi"]) if f["trigger_poi"] in order else 99)
        print(" ".join(f["id"] for f in lub))
        break
EOF
)
undrawn=$(python3 -c "
import json,sys
for line in open('$(J)', encoding='utf-8'):
    ev=json.loads(line)
    if ev.get('type')=='scenario_loaded': print(' '.join(ev['payload'].get('undrawn', []))); break")
echo "  lubies tirées   : $drawn"
echo "  lubies écartées : $undrawn"
verdict "$([ -n "$drawn" ] && echo 1 || echo 0)" "au moins une lubie tirée avec la graine du fichier"

echo "=== T2 première lubie : arrêt, fermeture au fader, consigne posée puis levée $(date +%T) ==="
first=$(echo $drawn | cut -d' ' -f1)
for i in $(seq 1 400); do hasid fault_start $first && break; sleep 1; done
verdict "$(hasid fault_start $first && echo 1 || echo 0)" "fault_start de la première lubie tirée ($first)"
sleep 2.5; c0=$(num $NS/cmd_vel_follow linear.x geometry_msgs/msg/Twist); echo "  cmd_vel_follow pendant la lubie : $c0"
verdict "$(python3 -c "print(1 if '$c0'!='NaN' and abs(float('$c0'))<1e-6 else 0)")" "lubie : Didier s'arrête (route_speed 0 -> consigne nulle)"
# La fermeture « télécommande » : David BOUGE le fader (revue du 14/10 : une
# valeur externe qui diffère de > 0,05 de celle d'avant la lubie la termine
# tout de suite — ici 1.0 -> 0.6 ; renvoyer 1.0 ne fermerait rien).
P route_speed 0.6
sleep 2.5; c1=$(num $NS/cmd_vel_follow linear.x geometry_msgs/msg/Twist); echo "  cmd_vel_follow après le fader : $c1"
verdict "$(python3 -c "print(1 if '$c1'!='NaN' and abs(float('$c1'))>1e-3 else 0)")" "fermeture au fader : Didier repart avant la fin de la lubie"
for i in $(seq 1 20); do hasid fault_stop $first && break; sleep 1; done
verdict "$(hasid fault_stop $first && echo 1 || echo 0)" "fault_stop de la première lubie"
verdict "$(grep '"type": "fault_stop"' "$(J)" | grep "\"id\": \"$first\"" | grep -q '"closed_by": "fader"' && echo 1 || echo 0)" "fermée par le fader (journal closed_by: fader), pas à l'échéance"
# Dès maintenant, chaque lubie suivante est fermée au fader en < 6 s : on
# ALTERNE 0.9 / 1.0 (une valeur ÉGALE à celle d'avant la lubie ne ferme pas)
# — la vérification ne doit pas durer 12 fois 60 s (David fermerait aussi).
( while true; do sleep 3; P route_speed 0.9; sleep 3; P route_speed 1.0; done ) & FADER=$!

echo "=== T4 arrivée + POI (attente de « finished » ou 540 s) $(date +%T) ==="
XEND=$(python3 -c "
import yaml; r=yaml.safe_load(open('$ROUTE_YAML')); print(r['waypoints'][-1][0])")
# Arrivée = x du DERNIER waypoint − 3 m (le quai est en biais : x croît aussi
# le long du quai, c'est bien x qui mesure la progression jusqu'à la Titan).
# On JOUE DAVID sur un point : après « reboot_sans_reprise » (kill sans
# relance — c'est le bug : Didier ne repart PAS), c'est lui qui relance
# (route on à la page / télécommande). Sans ça, Didier reste planté et le
# 2e reboot ne relance pas non plus (politique : jamais contre une route
# OFF) — vécu au run 6 du 14/10 : x = 131 m pendant 6 min, Titan jamais
# atteinte. Borne par HORLOGE (le CLI peut mettre 2 s par lecture).
relance=0
while [ $(( $(date +%s) - T0 )) -lt 880 ]; do
  if [ $relance = 0 ] && hasid fault_start reboot_sans_reprise; then
    sleep 8; P route on; relance=1   # respawn 5 s, puis David relance
    echo "  reboot_sans_reprise vu -> « route on » renvoyé (David relance) $(date +%T)"
  fi
  xi=$(timeout 2 ros2 topic echo $NS/ground_truth/odom nav_msgs/msg/Odometry --once --field pose.pose.position.x 2>/dev/null | grep -E -m1 '^-?[0-9]')
  python3 -c "import sys; sys.exit(0 if float('${xi:-nan}') >= float('$XEND') - 3.0 else 1)" 2>/dev/null && break
  sleep 1
done
x=$(num $NS/ground_truth/odom pose.pose.position.x); echo "  x final : $x ($(( $(date +%s) - T0 )) s) ; relance jouée : $relance"
verdict "$(python3 -c "print(1 if '$x'!='NaN' and float('$x') >= float('$XEND') - 3.0 else 0)")" "arrivée au pied de la Titan grise (x ≥ dernier waypoint − 3 m = $XEND − 3)"
order=$(python3 - "$(J)" "$ROUTE_YAML" <<'EOF'
import json, sys, yaml
names = [p["name"] for p in yaml.safe_load(open(sys.argv[2]))["pois"]]
seen = []
for line in open(sys.argv[1], encoding="utf-8"):
    ev = json.loads(line)
    if ev.get("type") == "poi_enter":
        seen.append(ev["payload"]["poi"])
idx = [names.index(n) for n in seen if n in names]
print(len(seen), 1 if idx == sorted(idx) else 0)
EOF
)
n_poi=$(echo $order | cut -d' ' -f1); ordered=$(echo $order | cut -d' ' -f2)
echo "  poi_enter : $n_poi, ordonnés : $ordered"
verdict "$([ "$n_poi" -ge 25 ] && echo 1 || echo 0)" "≥ 25 POI atteints"
verdict "$ordered" "POI dans l'ordre du YAML"

echo "=== T5 fin de scénario + couverture (attente scenario_end) $(date +%T) ==="
for i in $(seq 1 920); do has scenario_end && break; sleep 1; done
kill $FADER 2>/dev/null
verdict "$(has scenario_end && echo 1 || echo 0)" "journal : scenario_end"
bugs=$(python3 -c "
import yaml; s=yaml.safe_load(open('$SCEN_YAML')); print(' '.join(f['id'] for f in s['faults'] if f['type']!='lubie'))")
nb=$(echo $bugs | wc -w); echo "  bugs du scénario : $nb"
verdict "$([ "$nb" = 20 ] && echo 1 || echo 0)" "20 bugs déclarés"
pend=""; for id in $bugs; do hasid fault_start $id || hasid fault_skip $id || pend="$pend $id"; done
echo "  bugs jamais partis ni sautés :${pend:- aucun}"
verdict "$([ -z "$pend" ] && echo 1 || echo 0)" "chaque bug a fault_start ou fault_skip (plus aucun pending)"
verdict "$(has fault_error && echo 0 || echo 1)" "aucun fault_error"
# Statut final de chaque panne (payload de scenario_end) : done / skipped /
# error / pending. Une lubie dont le POI n'est jamais atteint n'a PAS de
# fault_skip au fil de l'eau : elle est « skipped » SEULEMENT ici.
status=$(python3 - "$(J)" <<'EOF'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    ev = json.loads(line)
    if ev.get("type") == "scenario_end":
        st = ev["payload"]["status"]
        print(" ".join(f"{k}={v}" for k, v in sorted(st.items())))
EOF
)
echo "  statuts : $(echo $status | tr ' ' '\n' | cut -d= -f2 | sort | uniq -c | tr '\n' ';')"
bad=$(echo $status | tr ' ' '\n' | grep -E "=(pending|error)$" | tr '\n' ' ')
echo "  pending/error :${bad:- aucun}"
verdict "$([ -n "$status" ] && [ -z "$bad" ] && echo 1 || echo 0)" "aucune panne ni lubie en pending/error à la fin (done ou skipped seulement)"
n_zero=$(grep -c '^0$' $CAP/route_speed.txt 2>/dev/null)
n_lubie_start=$(grep '"type": "fault_start"' "$(J)" | grep -c '"type": "lubie"')
echo "  route_speed = 0 publiés : $n_zero, lubies démarrées : $n_lubie_start"
verdict "$([ "$n_lubie_start" -ge 1 ] && [ "$n_zero" -ge "$n_lubie_start" ] && echo 1 || echo 0)" "chaque lubie démarrée a publié route_speed 0 (arrêt devant l'objet)"

echo "=== T3 (relu sur les captures) consignes et pannes chat $(date +%T) ==="
sleep 1
n_set=$(grep '^"' $CAP/instruction.txt 2>/dev/null | grep -vc '^""$')
n_clr=$(grep -c '^""$' $CAP/instruction.txt 2>/dev/null)
n_lubie_start=$(grep '"type": "fault_start"' "$(J)" | grep -c '"type": "lubie"')
echo "  chat_instruction : $n_set consignes posées, $n_clr levées ; lubies démarrées : $n_lubie_start"
verdict "$([ "$n_set" -ge 1 ] && [ "$n_set" = "$n_lubie_start" ] && echo 1 || echo 0)" "une consigne publiée par lubie démarrée"
verdict "$([ "$n_clr" = "$n_set" ] && echo 1 || echo 0)" "chaque consigne est levée (\"\")"
ops=$(grep -o '"op": "[a-z]*"' $CAP/chat_fault.txt 2>/dev/null | sort | uniq -c | tr '\n' ';')
echo "  rehearsal/chat_fault : $ops"
n_chat=$(grep '"type": "fault_start"' "$(J)" | grep -c '"type": "chat"')
n_pass=$(grep -c '"op": "pass"' $CAP/chat_fault.txt 2>/dev/null)
n_ops=$(grep -c '"op": "' $CAP/chat_fault.txt 2>/dev/null)
verdict "$([ "$n_chat" -ge 1 ] && [ $((n_ops - n_pass)) = "$n_chat" ] && echo 1 || echo 0)" "chaque panne chat démarrée a publié son op ($n_chat)"
verdict "$([ "$n_pass" -ge 1 ] && echo 1 || echo 0)" "au moins un « pass » publié (fin de panne chat)"
echo "  journal : $(J)"
echo "=== V-R3 : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
