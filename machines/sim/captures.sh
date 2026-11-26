# Captures des épreuves de la sim (lot fiabilité des épreuves, 16/11) — à SOURCER par un
# validate-*.sh, après le setup ROS, dans le conteneur `monde`. Remplace les captures et les
# lectures ponctuelles faites avec la CLI ros2 (découverte lente, best-effort, pertes sous charge :
# operations.md § Épreuves) par UN enregistreur rclpy par épreuve (capture_topics.py), lancé et
# PRÊT (abonnements appariés) avant que l'épreuve ne touche à quoi que ce soit.
#
# Les captures SURVIVENT : écrites sous /home/ros2_ws/log/captures/ (= $DIDIER_SIM_JOURNAUX/log/
# captures/ du PC, défaut ~/tmp/didier/sim/), ou dans $CAPTURE_DIR quand la fumée le donne (elle les copie ensuite dans ses
# journaux, docs/fumee/journaux/<id>/captures-<épreuve>/).
#
#   capture_demarrer <épreuve> --journal /t=pkg/msg/T … --dernier /t=pkg/msg/T[,latche] …
#   capture_lire <topic> <champ> [délai s] [--tout-age] [--valeur V]  -> valeur reçue APRÈS l'appel
#   capture_extraire <topic> <champ>          -> une valeur par ligne (journal), comme `--field`
#   capture_arreter                           -> arrêt propre ; 1 si l'enregistreur était MORT
CAPTURE_PY=${CAPTURE_PY:-/home/ros2_ws/capture_topics.py}
CAP=""; CAP_PID=""

capture_demarrer() {
  local epreuve=$1; shift
  CAP="${CAPTURE_DIR:-/home/ros2_ws/log/captures/$epreuve-$(date +%Y%m%d-%H%M%S)}"
  mkdir -p "$CAP"
  python3 -u "$CAPTURE_PY" enregistrer --dossier "$CAP" "$@" >"$CAP/enregistreur.log" 2>&1 &
  CAP_PID=$!
  # Arrêt propre quoi qu'il arrive (fin normale, `timeout` de la fumée, Ctrl-C) : le journal est
  # vidé à chaque ligne, FIN prouve que rien n'est resté en mémoire. Le trap EXIT de l'épreuve
  # est GARDÉ (validate-catalogue efface ainsi son dossier temporaire de data/) : on s'y ajoute
  # en tête. Filet en plus : l'enregistreur s'arrête seul si ce shell disparaît.
  local ancien; ancien=$(trap -p EXIT)
  if [ -n "$ancien" ]; then
    eval "set -- $ancien"   # trap -- '<commande>' EXIT -> $3 = <commande>
    trap -- "capture_arreter; $3" EXIT
  else
    trap capture_arreter EXIT
  fi
  trap 'exit 143' TERM INT
  if ! python3 "$CAPTURE_PY" attendre-pret --dossier "$CAP" --pid "$CAP_PID" --delai 60; then
    echo "PRÉCONDITION : l'enregistreur des captures n'est pas prêt (abonnements non appariés) — $CAP"
    sed 's/^/    /' "$CAP/enregistreur.log" "$CAP/ECHEC" 2>/dev/null
    exit 2
  fi
  echo "  captures : $CAP (enregistreur prêt, $(date +%T))"
}

capture_arreter() {
  [ -n "$CAP_PID" ] || return 0
  local pid=$CAP_PID vivant=1
  CAP_PID=""
  kill -0 "$pid" 2>/dev/null || vivant=0
  kill -TERM "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  if [ "$vivant" = 0 ] || ! python3 "$CAPTURE_PY" verifier-fin --dossier "$CAP"; then
    echo "  ⚠️ MESURE INVALIDE : l'enregistreur des captures est mort en cours d'épreuve (voir $CAP/enregistreur.log)"
    return 1
  fi
}

capture_lire() { # capture_lire <topic> <champ> [délai s, défaut 12] [options de `lire`…]
  local topic=$1 chemin=$2 delai=${3:-12}
  shift; shift; [ $# -gt 0 ] && shift
  python3 "$CAPTURE_PY" lire --dossier "$CAP" --topic "$topic" --champ "$chemin" --delai "$delai" "$@"
}

capture_extraire() { # capture_extraire <topic> <champ>
  python3 "$CAPTURE_PY" extraire --dossier "$CAP" --topic "$1" --champ "$2"
}
