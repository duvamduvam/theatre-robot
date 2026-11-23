#!/bin/bash
# L1b — preuve REJOUABLE du namespace par robot en simulation (spec
# theatre-robot/docs/spec-L1-contrats-donnees.md, L1b décision 7), DANS le
# conteneur sim (domaine 43) démarré avec ROBOT_NAME=<nom> (défaut didier).
# Lance ce qui manque parmi : chaîne roues (drive.launch.py), répétition avec le
# sélecteur (rehearsal.launch.py jeu:=true), pont web (web.launch.py, port à
# part) ; attend $ATTENTE s ; puis exige :
#   - `ros2 topic list` : TOUT sous /<nom>/ sauf les 5 exceptions gravées
#     (/clock, /tf, /tf_static, /rosout, /parameter_events — même liste que
#     robot/tests/unit/test_namespace_contract.py) ;
#   - `ros2 node list` : TOUT sous /<nom>/ ;
#   - twist_mux a bien chargé sa config sous namespace (verrou e_stop 255 —
#     piège du params-file mesuré le 04/11, cf. drive.launch.py) ;
#   - le bridge relaie sous namespace (vérité terrain publiée, cou écouté).
# Sortie 0 = OK ; 1 = KO (liste des intrus affichée) ; 2 = banc faux.
# Ce qu'il a lancé, il l'arrête en sortant (SIGINT au groupe de processus).
# Rien ici ne peut atteindre le vrai robot : refus hors domaine 43.
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
# Namespace du robot (lot L1b) : la CLI ne le suit PAS (un nom relatif tapé ici
# se résout à la racine) — chaque topic est préfixé par $NS.
NS="/${ROBOT_NAME:-didier}"
ATTENTE=${ATTENTE:-10}
EXCEPTIONS="/clock /tf /tf_static /rosout /parameter_events"
[ "${ROS_DOMAIN_ID:-}" = 43 ] || { echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, ce script ne tourne qu'en simulation (43)"; exit 2; }

ok=0; ko=0
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }

# --- Lancement de ce qui manque ------------------------------------------------
LANCES=()
lance() { # lance <motif pgrep « déjà là »> <nom du journal> <commande…>
  local motif=$1 nom=$2; shift 2
  if pgrep -f "$motif" >/dev/null; then echo "  déjà présent : $nom"; return; fi
  # setsid : le PID devient chef de groupe -> on arrête le launch ET ses nœuds d'un coup.
  setsid "$@" >"/tmp/validate-namespace-$nom.log" 2>&1 &
  LANCES+=($!); echo "  lancé : $nom (pid $!, journal /tmp/validate-namespace-$nom.log)"
}
arreter() {
  for pid in "${LANCES[@]}"; do kill -INT -- "-$pid" 2>/dev/null; done
  for i in $(seq 1 20); do
    vivant=0; for pid in "${LANCES[@]}"; do kill -0 "$pid" 2>/dev/null && vivant=1; done
    [ $vivant = 0 ] && return; sleep 0.5
  done
  for pid in "${LANCES[@]}"; do kill -KILL -- "-$pid" 2>/dev/null; done
}
trap arreter EXIT

echo "=== namespace attendu : $NS/ (ROBOT_NAME=${ROBOT_NAME:-<absent>}) $(date +%T) ==="
pgrep -f "parameter_bridge" >/dev/null || { echo "PRÉCONDITION : bridge gz absent (sim démarrée ?)"; exit 2; }
lance "/twist_deadman( |$)" drive ros2 launch didier_drive drive.launch.py use_sim_time:=true
# Une séance déjà lancée (avec ou sans jeu) suffit : deux régisseurs se battraient.
lance "lib/didier_rehearsal/director" rehearsal \
  ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
# Port à part : celui de la sim (WEB=true, 8765) serait déjà pris.
lance "/web_bridge( |$)" web ros2 launch didier_web web.launch.py web_port:=${VALIDATE_WEB_PORT:-8775}
sleep "$ATTENTE"

# --- Lecture du graphe (sans démon : pas de topics périmés d'une passe précédente) --
# Sentinelles : sans elles, une liste vide passerait pour « aucun intrus ».
# A0-4 (20/11) : + le corps sûr (sortie filtrée, état latché) et le lidar simulé, sous namespace.
SENT_TOPICS="$NS/cmd_vel $NS/cmd_vel_mux $NS/e_stop $NS/route_state $NS/ground_truth/odom $NS/neck/position $NS/cmd_vel_follow_sur $NS/corps_sur/etat $NS/scan"
# data_edit_node (L1d) : toujours lancé par robot_app.launch.py (conteneur robot de la sim, L2b).
SENT_NODES="$NS/twist_mux $NS/twist_deadman $NS/wheels_bridge $NS/director $NS/route_driver $NS/web_bridge_node $NS/data_edit_node $NS/corps_sur"
pgrep -f "/jeu_node( |$)" >/dev/null && SENT_TOPICS="$SENT_TOPICS $NS/jeu/intention" && SENT_NODES="$SENT_NODES $NS/jeu_node"
# Noms ROS seuls : la CLI écrit les erreurs de Fast DDS sur STDOUT (fumée 2026-11-20-1025 :
# « [RTPS_TRANSPORT_SHM Error] Failed init_port fastrtps_port7015: open_and_lock_file failed »,
# un port SHM d'un participant mort, sans effet sur le graphe) ; lue comme un nom, cette ligne
# rendait « topics » ET « nœuds » rouges. Tout nom de topic ou de nœud commence par « / » :
# le reste est du BRUIT, compté à part et affiché (jamais un intrus, jamais caché).
# Comportement gravé : test_namespace_contract.py (test_noms_ros_*).
noms_ros() { grep -a '^/' | sort -u; }
bruit_cli() { grep -av '^/' | grep -a . ; }
for essai in 1 2 3 4; do
  brut_t=$(ros2 topic list --no-daemon --spin-time 5 2>/dev/null)
  brut_n=$(ros2 node list --no-daemon --spin-time 5 2>/dev/null)
  topics=$(noms_ros <<<"$brut_t"); nodes=$(noms_ros <<<"$brut_n")
  manque=""
  for t in $SENT_TOPICS; do grep -qx "$t" <<<"$topics" || manque="$manque $t"; done
  for n in $SENT_NODES; do grep -qx "$n" <<<"$nodes" || manque="$manque $n"; done
  [ -z "$manque" ] && break
  echo "  graphe incomplet (essai $essai) :$manque"; sleep 3
done
echo "  $(wc -l <<<"$topics") topics, $(wc -l <<<"$nodes") nœuds vus"
bruit=$( { bruit_cli <<<"$brut_t"; bruit_cli <<<"$brut_n"; } | sort -u)
[ -n "$bruit" ] && echo "  ⚠️ bruit de la CLI ignoré ($(wc -l <<<"$bruit") ligne(s), pas des noms ROS) : $(head -1 <<<"$bruit" | sed 's/\x1b\[[0-9;]*m//g')"
verdict "$([ -z "$manque" ] && echo 1 || echo 0)" "sentinelles présentes sous $NS/ (topics + nœuds)${manque:+ — manquent :$manque}"

intrus_t=""
while read -r t; do
  [ -z "$t" ] && continue
  case "$t" in "$NS"/*) continue ;; esac
  case " $EXCEPTIONS " in *" $t "*) continue ;; esac
  intrus_t="$intrus_t $t"
done <<<"$topics"
verdict "$([ -z "$intrus_t" ] && echo 1 || echo 0)" "tout topic sous $NS/ sauf {$EXCEPTIONS}${intrus_t:+ — INTRUS :$intrus_t}"

intrus_n=""
while read -r n; do
  [ -z "$n" ] && continue
  case "$n" in "$NS"/*) continue ;; esac
  intrus_n="$intrus_n $n"
done <<<"$nodes"
verdict "$([ -z "$intrus_n" ] && echo 1 || echo 0)" "tout nœud sous $NS/${intrus_n:+ — INTRUS :$intrus_n}"

# twist_mux namespacé : sa config doit être CHARGÉE (sinon mux sans entrées ni verrou).
# Sans démon + --timeout : au tout premier appel, le démon ros2 naît avec un
# graphe vide et répond « node not found » (vécu le 04/11 : faux KO).
# Reprises (fumée 2026-11-23-2319, 1re fois en 19 fumées) : `topics.remote.priority` lu
# « absent » alors que le journal du mux montrait remote à 100, la lecture précédente (e_stop)
# ayant réussi — raté isolé d'un appel. Trois essais, 2 s entre deux ; si tous échouent, la
# dernière erreur de la CLI va au journal (diagnostic) et le verdict reste KO.
pget() {
    local essai val err
    for essai in 1 2 3; do
        err=$(mktemp)
        val=$(timeout 20 ros2 param get $NS/twist_mux "$1" --no-daemon --timeout 10 2>"$err" | grep -oE '[0-9]+$' || true)
        if [ -n "$val" ]; then rm -f "$err"; echo "$val"; return 0; fi
        echo "  (param $1 : essai $essai sans valeur : $(head -c 200 "$err" | tr '\n' ' '))" >&2
        rm -f "$err"; sleep 2
    done
}
prio=$(pget locks.e_stop.priority); remote=$(pget topics.remote.priority)
echo "  $NS/twist_mux : locks.e_stop.priority=${prio:-absent}, topics.remote.priority=${remote:-absent}"
verdict "$([ "$prio" = 255 ] && [ "$remote" = 100 ] && echo 1 || echo 0)" "twist_mux a chargé twist_mux.yaml sous namespace (e_stop 255, remote 100)"

# Le bridge relaie sous namespace : gz -> ROS (vérité terrain) et ROS -> gz (cou).
# SANS démon et avec reprises, comme les sentinelles plus haut : par le démon, les fumées du
# 19/11 07:50 et 07:52 (PC démarré à 07:48) ont lu 0 publisher alors que le pont avait créé
# ground_truth/odom (journal du conteneur monde) et que la même image, 2 min plus tard, lisait 1 :
# vue partielle du démon, pas du pont (diag 19/11). Chaque lecture découvre le graphe elle-même.
compte() { # compte <topic> <Publisher|Subscription>
  timeout 20 ros2 topic info "$1" --no-daemon --spin-time 5 2>/dev/null | grep -oE "$2 count: [0-9]+" | grep -oE '[0-9]+$'
}
for essai in 1 2 3 4; do
  pub_odom=$(compte $NS/ground_truth/odom Publisher); sub_cou=$(compte $NS/neck/position Subscription)
  [ "${pub_odom:-0}" -ge 1 ] && [ "${sub_cou:-0}" -ge 1 ] && break
  echo "  bridge pas encore vu (essai $essai) : ${pub_odom:-0} publisher(s), ${sub_cou:-0} abonné(s)"; sleep 3
done
echo "  $NS/ground_truth/odom : ${pub_odom:-0} publisher(s) ; $NS/neck/position : ${sub_cou:-0} abonné(s)"
verdict "$([ "${pub_odom:-0}" -ge 1 ] && [ "${sub_cou:-0}" -ge 1 ] && echo 1 || echo 0)" "bridge gz namespacé (vérité terrain publiée, cou écouté)"

echo "=== validate-namespace ($NS) : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
