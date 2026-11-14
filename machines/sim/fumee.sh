#!/bin/bash
# Lot F — FUMÉE NOCTURNE : rejoue toutes les épreuves de la sim sur le checkout de
# main et compare chaque compteur à une valeur GRAVÉE. Zéro token : ce script
# MESURE, il ne juge pas (spec theatre-robot/docs/spec-L1-contrats-donnees.md,
# « Lot F », décisions 1 à 6). Pourquoi : l'environnement bouge sans commit
# (paquets Gazebo, Docker, nombre de conteneurs — vécu le 06/11 : V-R3 de 21/21 à
# 18/21 sans régression du code) et chaque lot payait ≈ 1 h d'épreuves à la main.
#
# Usage :
#   fumee.sh --si-due   appelé par la minuterie systemd utilisateur (toutes les 30 min) :
#                       ne fait RIEN si aucune fumée n'est due ; si elle l'est mais que le
#                       PC est occupé (charge, RTF, sim de quelqu'un), note « reporté » et
#                       sort 0 — jamais de plage à réserver, le prochain essai réessaie.
#   fumee.sh            forcé, à la main : déroule même si pas due (le RTF reste juge).
#   fumee.sh --et-dodo  fumée forcée PUIS extinction du PC (à lancer en allant se coucher).
#                       Essai à blanc : FUMEE_DRY_POWEROFF=1 remplace le poweroff par un echo.
#
# Une fumée est DUE si un commit touchant un chemin TESTÉ (liste gravée CHEMINS_TESTES en
# tête de fumee_page.py : packages/, data/, deploy/, machines/ — la doc n'en est pas) est
# entré dans main après le sha de la dernière
# page VERTE, OU si 7 jours se sont écoulés sans fumée verte. Après un ROUGE sur un « sha de
# code » (dernier commit touchant un chemin testé) : UNE relance de confirmation, puis plus
# rien sur ce code tant qu'aucun commit de code n'arrive (« bloquée » ; le rappel > 2 jours
# reste). La décision lit les resultat.json (fumee_page.py), jamais le HTML.
#
# Ordre (décision 3), arrêt au PREMIER rouge bloquant (les suivantes : « non lancée ») :
#   image (reconstruite seulement si machines/sim/banc-robot a changé depuis la dernière verte)
#   -> sim headless + colcon -> sonde RTF 20 s (rouge si < 0,8 : le reste n'est pas fiable)
#   -> validate-namespace -> validate-catalogue -> animation parle -> validate-data-edit (L1d)
#   -> chaîne roues + régisseur + regard, validate-rehearsal-chantiers (V-R3)
#   -> sim relancée, validate-jeu-a1 (A1).        ≈ 40 min.
#
# Garde-fous :
#   - domaine ROS 43 FORCÉ et revérifié dans le conteneur (42 = vrai robot, jamais) ;
#   - un conteneur dadou-sim-container déjà présent = la sim de quelqu'un : on reporte (ou
#     on refuse en forcé), on ne la tue JAMAIS ; la sim lancée ici est arrêtée quoi qu'il
#     arrive (trap EXIT), après copie des journaux ;
#   - verrou flock : jamais deux fumées en même temps ;
#   - l'arbre de travail du dépôt n'est jamais modifié hors docs/fumee/ (le seul commit
#     est `git commit -- docs/fumee`, sans -a ni add .). Arbre sale : on teste quand même,
#     le sha porte « -dirty ». Exceptions connues : validate-catalogue.sh dépose puis
#     supprime une séquence temporaire dans json/sequences/tmp-l1c (monté depuis l'arbre) ;
#     validate-data-edit.sh (L1d) écrit par le robot dans data/ puis restaure tout ce qu'il
#     a touché (empreinte de json/ et medias/visuals/ identique, sinon code 1).
#
# Variables (toutes facultatives) :
#   FUMEE_DEPOT        checkout de main à tester (défaut : le dépôt de David)
#   FUMEE_SORTIE       dossier des pages (défaut : $FUMEE_DEPOT/docs/fumee)
#   FUMEE_COMMIT       1 (défaut) = commit de docs/fumee ; 0 = pas de commit (essais)
#                      — le commit n'a de toute façon lieu que si FUMEE_SORTIE est le défaut
#   FUMEE_RTF_MIN      seuil du facteur temps réel (défaut 0,8) ; tout autre = « essai provoqué »
#   FUMEE_CHARGE_MAX   load average 1 min au-dessus duquel --si-due reporte
#                      (défaut : nb de cœurs × 0,5 — le RTF reste le vrai juge)
#   FUMEE_ETAT         journal + verrou (défaut ~/.local/state/didier-fumee)
#   FUMEE_DRY_POWEROFF 1 = --et-dodo n'éteint pas, il l'affiche
#   FUMEE_DODO_DELAI   secondes entre la fin et le poweroff (défaut 20)
#   FUMEE_COEURS       CPU RÉSERVÉS à la sim pendant la fumée (défaut 8-15 = 4 cœurs rapides
#                      du PC de David) ; vide = pas de réservation. Voir coeurs_reserves.py.
# Codes de sortie : 0 vert ou reporté ou pas due ; 1 fumée ROUGE ; 2 refus/précondition.
set -euo pipefail

# --- Valeurs attendues, GRAVÉES (compteurs « N OK » des scripts de vérification) ----
# Les changer revient à changer le contrat : se fait dans un commit qui le dit.
ATTENDU_NAMESPACE=5     # validate-namespace.sh : sentinelles, topics, nœuds, twist_mux, bridge
ATTENDU_CATALOGUE=4     # validate-catalogue.sh : 6 familles, sha dev, ajout, suppression
ATTENDU_PARLE=3         # états vus dans l'ordre : "" -> "parle" -> ""
ATTENDU_EDITION=13      # validate-data-edit.sh (L1d : épreuves 1 à 12, 13 = porte sim depuis L1d-2)
ATTENDU_CHANTIERS=21    # validate-rehearsal-chantiers.sh (V-R3)
ATTENDU_A1=14           # validate-jeu-a1.sh (A1)
RTF_MIN_DEFAUT=0.8

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAGE_PY="$ICI/fumee_page.py"
DEPOT="${FUMEE_DEPOT:-/home/dadou/Nextcloud/dev/didier/python/theatre-robot}"
SORTIE_DEFAUT="$DEPOT/docs/fumee"
SORTIE="${FUMEE_SORTIE:-$SORTIE_DEFAUT}"
RTF_MIN="${FUMEE_RTF_MIN:-$RTF_MIN_DEFAUT}"
ETAT="${FUMEE_ETAT:-$HOME/.local/state/didier-fumee}"
JOURNAL="$ETAT/journal.log"
# L1e-4c (11/11) : le banc de la sim vit dans machines/sim/banc-robot/ (ex conf/docker/sim du robot).
DOCKER_DIR="$DEPOT/machines/sim/banc-robot"
CONTENEUR=dadou-sim-container
IMAGE=dadouuu/dadou-sim-x86:latest
CHEMIN_DOCKER_SIM="machines/sim/banc-robot"   # relatif au dépôt (git diff)
NB_COEURS="$(nproc)"
# Cœurs réservés (08/11) : sous un pic de charge le RTF tombait à 0,76 ; sim seule sur 4 cœurs
# rapides réservés = 0,987 (mesuré). Pendant la fumée SEULEMENT : tout est rendu à la fin.
COEURS="${FUMEE_COEURS-8-15}"
COEURS_PY="$ICI/coeurs_reserves.py"
MAINTIEN_PID=""
CHARGE="$(cut -d' ' -f1 /proc/loadavg)"
CHARGE_MAX="${FUMEE_CHARGE_MAX:-$(awk -v n="$NB_COEURS" 'BEGIN { printf "%.1f", n * 0.5 }')}"

MODE=force
for arg in "$@"; do
  case "$arg" in
    --si-due) MODE=si-due ;;
    --et-dodo) MODE=et-dodo ;;
    -h|--aide|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "fumee.sh : argument inconnu « $arg » (--si-due | --et-dodo | --aide)" >&2; exit 2 ;;
  esac
done

mkdir -p "$ETAT"
journal() { # une ligne datée dans ~/.local/state/didier-fumee/journal.log (borné à 2000 lignes)
  printf '%s %s\n' "$(date -Iseconds)" "$*" >>"$JOURNAL"
  if [ "$(wc -l <"$JOURNAL")" -gt 2000 ]; then tail -n 1500 "$JOURNAL" >"$JOURNAL.tmp" && mv "$JOURNAL.tmp" "$JOURNAL"; fi
}
dit() { echo "[fumée $(date +%T)] $*"; }

# --- Verrou : jamais deux fumées à la fois --------------------------------------
exec 9>"$ETAT/verrou"
SAUTER_FUMEE=0
if ! flock -n 9; then
  if [ "$MODE" = et-dodo ]; then
    # Une fumée tourne déjà (minuterie) : on l'attend au lieu de l'éteindre en plein vol,
    # puis on éteint sans en refaire une (elle vient de se terminer).
    dit "une fumée est en cours, j'attends sa fin (90 min max) avant d'éteindre"
    flock -w 5400 9 || { dit "la fumée en cours n'a pas fini en 90 min : je n'éteins PAS"; exit 2; }
    SAUTER_FUMEE=1
  else
    exit 0   # silence : la minuterie ou la main a déjà la place
  fi
fi

for cmd in docker git python3 flock; do
  command -v "$cmd" >/dev/null || { dit "outil manquant : $cmd"; exit 2; }
done
[ -d "$DEPOT/.git" ] || [ -f "$DEPOT/.git" ] || { dit "FUMEE_DEPOT n'est pas un dépôt git : $DEPOT"; exit 2; }

# --- État du dépôt testé ---------------------------------------------------------
BRANCHE="$(git -C "$DEPOT" rev-parse --abbrev-ref HEAD)"
SHA_COMPLET="$(git -C "$DEPOT" rev-parse HEAD)"
SHA_COURT="$(git -C "$DEPOT" rev-parse --short=7 HEAD)"
SALE=0
# Le statut exclut docs/fumee (nos propres pages) : seul le code de David compte.
[ -z "$(git -C "$DEPOT" status --porcelain -- . ':(exclude)docs/fumee')" ] || SALE=1
SHA="$SHA_COURT"; [ "$SALE" = 1 ] && SHA="$SHA_COURT-dirty"
ETAT_ARBRE_AVANT="$(git -C "$DEPOT" status --porcelain -- . ':(exclude)docs/fumee')"

# --- Variables d'état de l'exécution ----------------------------------------------
TMP=""; ID=""; JDIR=""; JSONL=""
ENGAGEE=0          # 1 dès qu'une page doit être écrite (sinon : reporté, pas de page)
SIM_A_NOUS=0       # 1 si CE script a lancé le conteneur (donc seul autorisé à l'arrêter)
TERMINE=0
PHASE_COURANTE=demarrage
IMAGE_RECONSTRUITE=0
RTF=""
NOTES=()
RAISON=""
DEBUT_S=$SECONDS
DEBUT_ISO="$(date -Iseconds)"
DEPUIS=""; RAPPEL=non

# --- Reporter : sortir proprement sans page -------------------------------------
rappel_si_besoin() { # rappel_si_besoin [bloquee]
  # Décision 2 : due depuis plus de 2 jours et toujours pas verte -> on prévient David
  # (notification + journal), au plus une fois toutes les 12 h pour ne pas harceler.
  # Deux causes : reportée (PC occupé) ou bloquée (rouge confirmé sur ce code, règle du 10/11).
  [ "$RAPPEL" = oui ] || return 0
  local marque="$ETAT/dernier-rappel" maintenant; maintenant="$(date +%s)"
  if [ -f "$marque" ] && [ $((maintenant - $(cat "$marque"))) -lt 43200 ]; then return 0; fi
  echo "$maintenant" >"$marque"
  if [ "${1:-}" = bloquee ]; then
    journal "RAPPEL : une fumée est due depuis ${DEPUIS:-plus de 2 jours} et reste $RAISON"
    command -v notify-send >/dev/null && notify-send "Didier : fumée rouge confirmée" \
      "Plus de relance automatique sur ce code tant qu'aucun commit de code n'arrive. Voir docs/fumee/." || true
    return 0
  fi
  journal "RAPPEL : une fumée est due depuis ${DEPUIS:-plus de 2 jours} et reste reportée (PC trop occupé)"
  command -v notify-send >/dev/null && notify-send "Didier : fumée en retard" \
    "Due depuis plus de 2 jours, toujours reportée. Lance fumee.sh --et-dodo en allant te coucher." || true
}
reporter() {
  journal "reporté : $1 (charge $CHARGE/$CHARGE_MAX, sha $SHA)"
  dit "reporté : $1"
  rappel_si_besoin
  ENGAGEE=0
  exit 0
}

# --- Décision : due ou non (mode minuterie) -------------------------------------
if [ "$MODE" = si-due ]; then
  set +e
  LIGNE="$(python3 "$PAGE_PY" due --sortie "$SORTIE" --depot "$DEPOT")"; RC=$?
  set -e
  case "$RC" in
    1) # pas due : on ne fait RIEN (30 min plus tard, même chose). Bloquée (rouge confirmé
       # sur ce code) : rien non plus, sauf le rappel « > 2 jours » (au plus 1 fois / 12 h).
       IFS=$'\t' read -r ETAT_DUE RAISON DEPUIS RAPPEL <<<"$LIGNE"
       [ "$ETAT_DUE" != bloquee ] || rappel_si_besoin bloquee
       exit 0 ;;
    0) ;;
    *) journal "ERREUR de la décision « due ? » (code $RC) : $LIGNE"; exit 2 ;;
  esac
  IFS=$'\t' read -r _ RAISON DEPUIS RAPPEL <<<"$LIGNE"
  RAISON="due : $RAISON"
else
  RAISON="lancée à la main ($MODE)"
fi

# --- Un conteneur sim déjà là est celui de quelqu'un : jamais touché --------------
if [ -n "$(docker ps -a --filter "name=^${CONTENEUR}\$" --format '{{.Names}}')" ]; then
  ETAT_C="$(docker inspect -f '{{.State.Status}}' "$CONTENEUR" 2>/dev/null || echo inconnu)"
  # Un conteneur ARRÊTÉ (exited/dead/created) ne fait tourner la sim de personne : c'est un reste
  # (vécu le 08/11 : PC éteint au bouton à 02:32 pendant une fumée → conteneur exited, et la
  # minuterie a reporté toute la matinée). On le retire (docker rm SANS -f : refuse s'il tourne)
  # et on continue. Seul un conteneur vivant (running/paused/restarting) reste intouchable.
  case "$ETAT_C" in
    exited|dead|created)
      if docker rm "$CONTENEUR" >/dev/null 2>&1; then
        journal "reste retiré : conteneur $CONTENEUR arrêté ($ETAT_C)"
        ETAT_C=retire
      fi ;;
  esac
fi
if [ "${ETAT_C:-}" != retire ] && [ -n "$(docker ps -a --filter "name=^${CONTENEUR}\$" --format '{{.Names}}')" ]; then
  ETAT_C="$(docker inspect -f '{{.State.Status}}' "$CONTENEUR" 2>/dev/null || echo inconnu)"
  if [ "$MODE" = si-due ]; then reporter "conteneur $CONTENEUR déjà présent ($ETAT_C), pas touché"; fi
  journal "refus : conteneur $CONTENEUR déjà présent ($ETAT_C)"
  dit "REFUS : le conteneur $CONTENEUR existe déjà ($ETAT_C). C'est une sim à toi : arrête-la toi-même (docker rm -f $CONTENEUR) puis relance. Je ne la touche pas."
  exit 2
fi

if [ "$MODE" = si-due ]; then
  # Une fumée sur autre chose que main ne dirait rien de main (et la décision « due ? »
  # compare à la branche main) : on attend que le checkout soit revenu sur main.
  [ "$BRANCHE" = main ] || reporter "le checkout $DEPOT est sur la branche $BRANCHE, pas sur main"
  if awk -v c="$CHARGE" -v m="$CHARGE_MAX" 'BEGIN { exit !(c > m) }'; then
    reporter "charge trop haute ($CHARGE > $CHARGE_MAX)"
  fi
  # Plages sans commit (11/11) : la fumée commite sa page dans main, donc elle ne démarre ni
  # dans une plage, ni dans l'heure qui la précède (≈ 35 min de sim). Fichier LOCAL, hors dépôt
  # (FUMEE_PLAGES, défaut ~/.config/didier/plages-sans-commit ; absent = aucune plage) ; une
  # ligne par plage « JOURS DEBUT FIN », jours ISO (1 = lundi) en « a-b » ou « a », heures
  # pleines, FIN exclue. FUMEE_MAINTENANT="<jour> <heure>" remplace l'horloge (tests).
  PLAGES="${FUMEE_PLAGES:-$HOME/.config/didier/plages-sans-commit}"
  if [ -r "$PLAGES" ]; then
    read -r JOUR_N HEURE_N <<<"${FUMEE_MAINTENANT:-$(date '+%u %H')}"
    if awk -v j="$JOUR_N" -v h="$((10#$HEURE_N))" '
        !/^[[:space:]]*#/ && NF >= 3 {
          n = split($1, r, "-"); a = r[1] + 0; b = (n > 1 ? r[2] : r[1]) + 0
          if (j >= a && j <= b && h >= $2 - 1 && h < $3 + 0) dedans = 1
        }
        END { exit !dedans }' "$PLAGES"; then
      reporter "plage sans commit ($PLAGES)"
    fi
  fi
fi

# =====================================================================================
# À partir d'ici une fumée a lieu : page, journaux, sim.
# =====================================================================================
ENGAGEE=1
TMP="$(mktemp -d "${TMPDIR:-/tmp}/didier-fumee.XXXXXX")"
ID="$(date +%Y-%m-%d-%H%M)"
[ ! -e "$SORTIE/journaux/$ID" ] || ID="$(date +%Y-%m-%d-%H%M%S)"
JDIR="$SORTIE/journaux/$ID"
JSONL="$TMP/epreuves.jsonl"
mkdir -p "$JDIR"
ESSAI=0
{ [ "${FUMEE_ESSAI:-0}" = 1 ] || [ "$RTF_MIN" != "$RTF_MIN_DEFAUT" ]; } && ESSAI=1
[ "$BRANCHE" = main ] || NOTES+=("le checkout testé est sur la branche $BRANCHE, pas sur main")
[ "$SALE" = 0 ] || NOTES+=("arbre de travail modifié au départ : le sha porte -dirty, ce qui a été testé n'est pas un commit")
dit "fumée $ID sur $SHA (branche $BRANCHE), mode $MODE, charge $CHARGE/$CHARGE_MAX"
journal "début fumée $ID sur $SHA (mode $MODE) — $RAISON"

# L'environnement graphique est monté par le compose MÊME en headless, et Gazebo en a
# besoin : avec une autorité X invalide, son moteur de rendu segfault à l'initialisation
# (vu le 07/11 : « Authorization required » puis exit 139, aucun /clock). Sous la minuterie
# systemd, DISPLAY/XAUTHORITY viennent de l'environnement du gestionnaire utilisateur
# (GNOME les y importe) ; à défaut on cherche l'autorité d'Xwayland de la session ouverte.
export DISPLAY="${DISPLAY:-:0}"
if [ -z "${XAUTHORITY:-}" ] || [ ! -f "$XAUTHORITY" ]; then
  # shellcheck disable=SC2012  # noms de fichiers sûrs (.mutter-Xwaylandauth.XXXXXX)
  XAUTH_SESSION="$(ls -t "/run/user/$(id -u)"/.mutter-Xwaylandauth.* 2>/dev/null | head -1 || true)"
  if [ -n "$XAUTH_SESSION" ]; then
    export XAUTHORITY="$XAUTH_SESSION"
  else
    # Sans fichier, Docker créerait un RÉPERTOIRE à ce chemin ; un fichier vide évite cela,
    # mais Gazebo ne démarrera sans doute pas (le démarrage sera alors rouge, avec la cause).
    : >"$ETAT/xauthority-vide"; export XAUTHORITY="$ETAT/xauthority-vide"
    NOTES+=("aucune autorité X de session trouvée : Gazebo risque de ne pas démarrer (session graphique fermée ?)")
  fi
fi

# ---------------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------------
epreuve() { python3 "$PAGE_PY" epreuve --jsonl "$JSONL" --id "$@"; }

# Commande dans le conteneur, avec l'environnement ROS (le $ROS_DISTRO s'évalue DANS le conteneur).
ros_dans() { docker exec "$CONTENEUR" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && '"$1"; }
ros_detache() { docker exec -d "$CONTENEUR" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && '"$1"; }
python_ros() { docker exec -i "$CONTENEUR" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && python3 -'; }

attendre_processus() { # attendre_processus <motif> <présent|absent> <secondes>
  local motif=$1 voulu=$2 delai=$3 t0=$SECONDS present
  while [ $((SECONDS - t0)) -lt "$delai" ]; do
    if docker exec "$CONTENEUR" pgrep -f "$motif" >/dev/null 2>&1; then present=présent; else present=absent; fi
    [ "$present" = "$voulu" ] && return 0
    sleep 2
  done
  return 1
}

recolter() { # recolter <nom> : copie hors conteneur AVANT son arrêt (les journaux meurent avec lui)
  docker ps --format '{{.Names}}' | grep -qx "$CONTENEUR" || return 0
  local d="$TMP/recolte-$1"; mkdir -p "$d/tmp"
  docker logs "$CONTENEUR" >"$d/sim-docker.log" 2>&1 || true
  docker cp "$CONTENEUR:/home/ros2_ws/log" "$d/ros2_ws-log" >/dev/null 2>&1 || true
  docker exec "$CONTENEUR" bash -c 'cd /tmp && tar -cf - vr3-capture vja1 validate-*.log 2>/dev/null' \
    | tar -xf - -C "$d/tmp" 2>/dev/null || true
  # Page légère : tout fichier > 1 Mo est réduit à ses 3000 dernières lignes.
  find "$d" -type f -size +1M | while read -r gros; do
    tail -n 3000 "$gros" >"$gros.tail" && mv "$gros.tail" "$gros"
    echo "tronqué (3000 dernières lignes) : ${gros#"$d"/}" >>"$d/TRONQUE.txt"
  done
  tar -czf "$JDIR/conteneur-$1.tar.gz" -C "$d" . 2>/dev/null || true
  rm -rf "$d"
}

arreter_sim() {
  [ "$SIM_A_NOUS" = 1 ] || return 0
  dit "arrêt de la sim"
  (cd "$DOCKER_DIR" && docker compose -f docker-compose-sim.yml down -t 20) >/dev/null 2>&1 || true
  docker rm -f "$CONTENEUR" >/dev/null 2>&1 || true   # seulement le nôtre : SIM_A_NOUS=1
  SIM_A_NOUS=0
}

epingler_sim() { # la sim sur les cœurs réservés, et le reste du PC poussé ailleurs (une fois)
  [ -n "$COEURS" ] || return 0
  docker update --cpuset-cpus "$COEURS" "$CONTENEUR" >/dev/null 2>&1 \
    || { NOTES+=("cœurs réservés : épinglage de la sim sur $COEURS refusé par docker"); return 0; }
  [ -z "$MAINTIEN_PID" ] || return 0
  # Reliquat d'une fumée tuée (état encore présent) : on rend d'abord, on réserve ensuite.
  python3 "$COEURS_PY" liberer --etat "$ETAT/coeurs.json" >/dev/null 2>&1 || true
  dit "$(python3 "$COEURS_PY" reserver --coeurs "$COEURS" --etat "$ETAT/coeurs.json" --sim "$CONTENEUR" 2>&1 || true)"
  # Les processus lancés PENDANT la fumée (un nouvel onglet, un build) héritent de leur parent,
  # déjà poussé ; ceux qui naîtraient ailleurs sont rattrapés par cette passe toutes les 15 s.
  ( while sleep 15; do
      python3 "$COEURS_PY" maintenir --coeurs "$COEURS" --etat "$ETAT/coeurs.json" --sim "$CONTENEUR" >/dev/null 2>&1 || true
    done ) &
  MAINTIEN_PID=$!
}

liberer_coeurs() { # idempotent : rend affinités et cpusets d'origine (aussi sous trap EXIT)
  [ -n "$MAINTIEN_PID" ] && kill "$MAINTIEN_PID" 2>/dev/null
  MAINTIEN_PID=""
  [ -f "$ETAT/coeurs.json" ] || return 0
  dit "$(python3 "$COEURS_PY" liberer --etat "$ETAT/coeurs.json" 2>&1 || true)"
}

demarrer_sim() { # demarrer_sim : lance la sim headless (monde chantiers) puis attend colcon + bridge
  dit "démarrage de la sim (headless, domaine 43, colcon ≈ 1 min)"
  # SIM_A_NOUS avant le `up` : même un échec en cours de route laisse un conteneur À NOUS,
  # que terminer() doit retirer (on a vérifié plus haut qu'aucun conteneur homonyme n'existait).
  SIM_A_NOUS=1
  # ROS_DOMAIN_ID forcé ICI : le compose le lirait dans l'environnement de l'appelant.
  (cd "$DOCKER_DIR" && env ROS_DOMAIN_ID=43 ROBOT_NAME=didier HEADLESS=true WORLD=chantiers \
      REHEARSAL=true FACE=true WEB=true ANIMATIONS=true WEB_DRIVE=false DATA_EDIT=true \
      docker compose -f docker-compose-sim.yml up -d) >>"$TMP/demarrage.log" 2>&1 || return 1
  epingler_sim
  local domaine; domaine="$(docker exec "$CONTENEUR" printenv ROS_DOMAIN_ID 2>/dev/null || echo ?)"
  if [ "$domaine" != 43 ]; then echo "ROS_DOMAIN_ID=$domaine dans le conteneur : REFUS (43 exigé)" >>"$TMP/demarrage.log"; return 1; fi
  # Prêt = colcon fini sans échec ET le bridge gz lancé (dernier maillon de sim.launch.py).
  local t0=$SECONDS
  while [ $((SECONDS - t0)) -lt 360 ]; do
    if docker logs "$CONTENEUR" 2>&1 | grep -qE 'Failed +<<<|packages? failed'; then
      echo "colcon build a échoué" >>"$TMP/demarrage.log"; docker logs "$CONTENEUR" >>"$TMP/demarrage.log" 2>&1; return 1
    fi
    if docker exec "$CONTENEUR" pgrep -f parameter_bridge >/dev/null 2>&1; then
      sleep 15   # laisse le monde se charger avant de mesurer quoi que ce soit
      # Le bridge vit sans Gazebo : sans ce contrôle, un moteur de rendu mort (autorité X,
      # GPU) ne se verrait qu'au RTF, sous une cause trompeuse.
      if ! docker exec "$CONTENEUR" pgrep -f "gz sim" >/dev/null 2>&1; then
        { echo "Gazebo (gz sim) est mort au démarrage — extrait du journal du conteneur :"
          docker logs "$CONTENEUR" 2>&1 | grep -E "process has died|Segmentation|Authorization required|Unable to create the rendering" | tail -5 | cut -c1-300
        } >>"$TMP/demarrage.log"
        return 1
      fi
      return 0
    fi
    docker ps --format '{{.Names}}' | grep -qx "$CONTENEUR" || { echo "le conteneur s'est arrêté" >>"$TMP/demarrage.log"; return 1; }
    sleep 3
  done
  echo "bridge gz absent après 360 s" >>"$TMP/demarrage.log"; return 1
}

rechauffer_cli() {
  # Le démon ros2 du conteneur naît avec un graphe VIDE au tout premier appel de la CLI.
  # validate-namespace.sh lit `topic info` (via le démon) : sur un conteneur neuf il voit
  # alors « 0 publisher » et rend 4 OK / 1 KO alors que le bridge est sain (vu le 07/11,
  # reproduit : même script relancé aussitôt = 5/5). On réchauffe donc le démon et on
  # lui laisse le temps de découvrir le graphe AVANT l'épreuve. (Défaut de ce script de
  # vérification, déclaré au rapport du lot F ; ici on ne touche pas aux scripts de test.)
  ros_dans 'ros2 daemon start >/dev/null 2>&1; ros2 node list --spin-time 8 >/dev/null 2>&1' || true
  sleep 5
}

lancer_validation() { # lancer_validation <id> <script> <attendu> <motif de la ligne finale> <délai s>
  local id=$1 script=$2 attendu=$3 motif=$4 delai=$5 log="$TMP/$1.log" t0=$SECONDS rc=0 ligne ok ko detail=""
  dit "épreuve $id : $script (attendu $attendu OK, ≤ $((delai / 60)) min)"
  timeout -k 15 "$((delai + 60))" docker exec "$CONTENEUR" timeout -k 10 "$delai" bash "/home/ros2_ws/$script" >"$log" 2>&1 || rc=$?
  ligne="$(grep -E "$motif" "$log" | tail -1 || true)"
  ok="$(sed -nE 's/.* ([0-9]+) OK, ([0-9]+) KO.*/\1/p' <<<"$ligne")"
  ko="$(sed -nE 's/.* ([0-9]+) OK, ([0-9]+) KO.*/\2/p' <<<"$ligne")"
  local statut=""
  if [ -z "$ok" ]; then
    ok=0; ko=0; statut=rouge; detail="aucun compteur lu en fin de script (code $rc) : précondition, délai dépassé ou crash — voir le journal"
  elif [ "$rc" != 0 ] && [ "$ok" = "$attendu" ] && [ "$ko" = 0 ]; then
    statut=rouge; detail="compteur conforme mais code de retour $rc"
  fi
  epreuve "$id" ${statut:+--statut "$statut"} --ok "$ok" --attendu "$attendu" --ko "$ko" \
    --duree "$((SECONDS - t0))" --journal "$id.log" ${detail:+--detail "$detail"}
  [ "$ok" = "$attendu" ] && [ "$ko" = 0 ] && [ "$rc" = 0 ]
}

lancer_corps() { # lancer_corps <scénario chantiers|jeu-a1> <jeu:=true|''> : chaîne roues + régisseur + regard
  local scenario=$1 jeu=$2
  attendre_processus "lib/didier_rehearsal/director" absent 30 || true
  ros_detache 'ros2 launch didier_drive drive.launch.py use_sim_time:=true'
  ros_detache "ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=$scenario $jeu"
  ros_detache 'ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier'
  attendre_processus "lib/didier_rehearsal/director" présent 60 || return 1
  attendre_processus "gaze_follower" présent 60 || return 1
  sleep 20   # les nœuds finissent de s'apparier avant que le script de vérification ne les sonde
}

# --- Épreuves écrites en rclpy (la CLI ros2 perd des messages sur ce PC : operations.md) --
sonde_rtf() {
  python_ros <<'PY'
# Facteur temps réel = temps simulé écoulé / temps mural écoulé, sur 20 s de /clock.
import sys, time
import rclpy
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock
rclpy.init()
n = rclpy.create_node('fumee_rtf')
ech = []
n.create_subscription(Clock, '/clock', lambda m: ech.append((time.monotonic(), m.clock.sec + m.clock.nanosec * 1e-9)),
                      qos_profile_sensor_data)
limite = time.monotonic() + 120          # attente du premier /clock
while not ech and time.monotonic() < limite:
    rclpy.spin_once(n, timeout_sec=0.5)
if not ech:
    print('RTF=0.000 messages=0'); sys.exit(0)
debut = time.monotonic()
while time.monotonic() - debut < 20:
    rclpy.spin_once(n, timeout_sec=0.5)
(w0, s0), (w1, s1) = ech[0], ech[-1]
print('RTF=%.3f messages=%d' % (((s1 - s0) / (w1 - w0)) if w1 > w0 else 0.0, len(ech)))
PY
}

jouer_parle() {
  python_ros <<'PY'
# Joue « parle » 3 s et relève animation_state (latché des DEUX côtés : TRANSIENT_LOCAL +
# reliable, sinon l'état de repos initial n'arrive pas). Attendu : "" -> "parle" -> "".
import json, os, sys, time
import rclpy
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from theatre_interfaces.msg import StringTime
NS = '/' + (os.environ.get('ROBOT_NAME') or 'didier')
rclpy.init()
n = rclpy.create_node('fumee_parle')
etats = []
def lu(m):
    try:
        e = json.loads(m.msg)
    except ValueError:
        e = '?' + m.msg
    if not etats or etats[-1] != e:      # « parle » est republié à chaque démarrage : on dédoublonne
        etats.append(e)
qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
n.create_subscription(StringTime, NS + '/animation_state', lu, qos)
pub = n.create_publisher(StringTime, NS + '/animation', 10)
limite = time.monotonic() + 40
while time.monotonic() < limite and (not etats or pub.get_subscription_count() < 1):
    rclpy.spin_once(n, timeout_sec=0.2)
m = StringTime(); m.msg = json.dumps('parle'); m.time = 3000; m.anim = False
pub.publish(m)
limite = time.monotonic() + 20
while time.monotonic() < limite and not (len(etats) >= 3 and etats[-1] == ''):
    rclpy.spin_once(n, timeout_sec=0.2)
attendu, trouves = ['', 'parle', ''], 0
for e in etats:
    if trouves < 3 and e == attendu[trouves]:
        trouves += 1
print('ETATS=%s' % json.dumps(etats))
print('PARLE %d OK' % trouves)
PY
}

# ---------------------------------------------------------------------------------
# Phases (retour 1 = rouge bloquant : les suivantes ne sont pas lancées)
# ---------------------------------------------------------------------------------
phase_image() {
  local t0=$SECONDS raison="" ref
  ref="$(python3 "$PAGE_PY" dernier-vert --sortie "$SORTIE")"
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then raison="image absente"
  elif [ -z "$ref" ]; then raison="aucune fumée verte de référence"
  elif ! git -C "$DEPOT" cat-file -e "$ref^{commit}" 2>/dev/null; then raison="sha de référence $ref inconnu"
  elif ! git -C "$DEPOT" diff --quiet "$ref" -- "$CHEMIN_DOCKER_SIM"; then raison="Dockerfile/compose sim modifié depuis ${ref:0:7}"
  fi
  if [ -z "$raison" ]; then
    epreuve image --statut vert --detail "inchangée depuis la dernière fumée verte (${ref:0:7}), non reconstruite" --duree 0
    return 0
  fi
  dit "reconstruction de l'image sim ($raison, 3-5 min)"
  IMAGE_RECONSTRUITE=1
  if (cd "$DOCKER_DIR" && docker compose -f docker-compose-sim.yml build) >"$TMP/image.log" 2>&1; then
    epreuve image --statut vert --detail "reconstruite : $raison" --duree "$((SECONDS - t0))" --journal image.log
  else
    epreuve image --statut rouge --detail "la reconstruction a échoué ($raison)" --duree "$((SECONDS - t0))" --journal image.log
    return 1
  fi
}

phase_demarrage() {
  local t0=$SECONDS
  if demarrer_sim; then
    epreuve demarrage --statut vert --detail "conteneur $CONTENEUR, domaine 43, monde chantiers, headless" \
      --duree "$((SECONDS - t0))" --journal demarrage.log
  else
    epreuve demarrage --statut rouge --detail "la sim n'a pas démarré proprement (colcon, conteneur ou bridge)" \
      --duree "$((SECONDS - t0))" --journal demarrage.log
    return 1
  fi
}

phase_rtf() {
  local t0=$SECONDS sortie
  dit "sonde RTF (20 s)"
  sortie="$(sonde_rtf 2>&1 || true)"; printf '%s\n' "$sortie" >"$TMP/rtf.log"
  RTF="$(sed -nE 's/.*RTF=([0-9.]+).*/\1/p' <<<"$sortie" | tail -1)"
  RTF="${RTF:-0.000}"
  dit "RTF = $RTF (seuil $RTF_MIN)"
  if awk -v r="$RTF" -v m="$RTF_MIN" 'BEGIN { exit !(r >= m) }'; then
    epreuve rtf --statut vert --obtenu "$RTF" --detail "seuil $RTF_MIN" --duree "$((SECONDS - t0))" --journal rtf.log
  else
    # Mode minuterie : un PC occupé n'est pas une panne -> reporté, aucune page.
    if [ "$MODE" = si-due ]; then reporter "RTF $RTF < $RTF_MIN (PC trop occupé pour une fumée fiable)"; fi
    local cause="RTF $RTF < $RTF_MIN : les épreuves suivantes ne seraient pas fiables, elles ne sont pas lancées"
    grep -q 'messages=0' "$TMP/rtf.log" && cause="aucun message sur /clock en 120 s : Gazebo ne publie rien (voir sim-docker.log dans le .tar.gz)"
    epreuve rtf --statut rouge --obtenu "$RTF" --detail "$cause" --duree "$((SECONDS - t0))" --journal rtf.log
    return 1
  fi
}

phase_simples() {
  # À ce stade la sim tourne seule (mais drive/rehearsal/web sont lancés par les scripts eux-mêmes).
  rechauffer_cli
  lancer_validation namespace validate-namespace.sh "$ATTENDU_NAMESPACE" 'validate-namespace' 300 || return 1
  lancer_validation catalogue validate-catalogue.sh "$ATTENDU_CATALOGUE" 'validate-catalogue' 180 || return 1
  local t0=$SECONDS sortie ok
  dit "épreuve parle (animation_state \"\" -> \"parle\" -> \"\")"
  sortie="$(jouer_parle 2>&1 || true)"; printf '%s\n' "$sortie" >"$TMP/parle.log"
  ok="$(sed -nE 's/^PARLE ([0-9]+) OK.*/\1/p' <<<"$sortie" | tail -1)"; ok="${ok:-0}"
  epreuve parle --ok "$ok" --attendu "$ATTENDU_PARLE" --ko "$((ATTENDU_PARLE - ok))" \
    --detail "$(grep '^ETATS=' <<<"$sortie" | tail -1)" --duree "$((SECONDS - t0))" --journal parle.log
  [ "$ok" = "$ATTENDU_PARLE" ] || return 1
  # Édition à travers le robot (L1d) : lance puis arrête elle-même la chaîne roues (l'épreuve 7
  # mesure la tenue de cmd_vel) ; restaure ce qu'elle écrit dans data/.
  lancer_validation edition validate-data-edit.sh "$ATTENDU_EDITION" 'validate-data-edit' 300
}

phase_chantiers() {
  PHASE_COURANTE=chantiers
  lancer_corps chantiers '' || { epreuve chantiers --statut rouge --detail "chaîne roues / régisseur / regard non démarrés dans le conteneur"; return 1; }
  lancer_validation chantiers validate-rehearsal-chantiers.sh "$ATTENDU_CHANTIERS" '=== V-R3' 1500
}

phase_a1() {
  recolter chantiers; arreter_sim
  PHASE_COURANTE=a1
  local t0=$SECONDS
  if ! demarrer_sim; then
    epreuve a1 --statut rouge --detail "la sim relancée n'a pas démarré (voir demarrage.log)" --duree "$((SECONDS - t0))" --journal demarrage.log
    return 1
  fi
  lancer_corps jeu-a1 'jeu:=true' || { epreuve a1 --statut rouge --detail "chaîne roues / régisseur jeu / regard non démarrés dans le conteneur"; return 1; }
  lancer_validation a1 validate-jeu-a1.sh "$ATTENDU_A1" '=== A1' 1500
}

# ---------------------------------------------------------------------------------
# Fin : journaux, page, commit, arrêt de la sim (idempotent, aussi sous trap EXIT)
# ---------------------------------------------------------------------------------
commit_pages() {
  [ "${FUMEE_COMMIT:-1}" = 1 ] && [ "$SORTIE" = "$SORTIE_DEFAUT" ] || return 0
  # Le commit est celui du checkout de main : sur une autre branche on ne commite pas dedans.
  [ "$BRANCHE" = main ] || { journal "page $PAGE écrite mais NON commitée : le checkout est sur $BRANCHE, pas sur main"; return 0; }
  # Le seul commit autorisé dans le checkout de David : pathspec docs/fumee, JAMAIS -a ni add .
  # (réessai : un commit de David en même temps tient index.lock quelques secondes).
  for _ in 1 2 3; do
    if git -C "$DEPOT" add -- docs/fumee \
       && git -C "$DEPOT" commit -q -m "Fumée nocturne $ID : $VERDICT sur $SHA (RTF ${RTF:-n/a})" \
            -m "Page docs/fumee/$PAGE, journaux dans docs/fumee/journaux/$ID/. Commit automatique de fumee.sh (lot F), docs/fumee seulement." \
            -- docs/fumee; then
      journal "page $PAGE commitée dans $BRANCHE"; return 0
    fi
    sleep 5
  done
  journal "ÉCHEC du commit de docs/fumee (3 essais) — la page est écrite mais non commitée"
  return 1
}

terminer() {
  local rc=$?
  [ "$TERMINE" = 0 ] || return "$rc"
  TERMINE=1
  trap - EXIT INT TERM
  set +e
  if [ "$ENGAGEE" = 1 ]; then
    recolter "$PHASE_COURANTE"   # AVANT l'arrêt : les journaux meurent avec le conteneur
    arreter_sim
    # L'arbre de travail ne doit pas avoir bougé (hors docs/fumee) — sinon on le dit sur la page.
    local apres; apres="$(git -C "$DEPOT" status --porcelain -- . ':(exclude)docs/fumee')"
    [ "$apres" = "$ETAT_ARBRE_AVANT" ] || NOTES+=("l'arbre de travail a changé PENDANT la fumée (résidu d'un script de vérification ?) : $(diff <(echo "$ETAT_ARBRE_AVANT") <(echo "$apres") | tr '\n' ' ' | cut -c1-300)")
    # Journaux des épreuves : copiés (les plus longs réduits à leurs 2000 dernières lignes).
    local f
    for f in "$TMP"/*.log; do
      [ -f "$f" ] || continue
      tail -n 2000 "$f" >"$JDIR/$(basename "$f")"
    done
    [ "$(du -sk "$JDIR" | cut -f1)" -le 8192 ] || NOTES+=("journaux volumineux : $(du -sh "$JDIR" | cut -f1)")
    local args=() n
    for n in "${NOTES[@]}"; do args+=(--note "$n"); done
    PAGE="$(python3 "$PAGE_PY" finaliser --jsonl "$JSONL" --sortie "$SORTIE" --id "$ID" \
      --meta "sha=$SHA" --meta "sha_complet=$SHA_COMPLET" --meta "sale=$SALE" --meta "branche=$BRANCHE" \
      --meta "mode=$MODE" --meta "raison=$RAISON" --meta "debut=$DEBUT_ISO" --meta "fin=$(date -Iseconds)" \
      --meta "duree_s=$((SECONDS - DEBUT_S))" --meta "rtf=${RTF}" --meta "rtf_min=$RTF_MIN" \
      --meta "charge_1min=$CHARGE" --meta "nb_coeurs=$NB_COEURS" --meta "essai=$ESSAI" \
      --meta "image_reconstruite=$IMAGE_RECONSTRUITE" --meta "coeurs_reserves=${COEURS:-aucun}" "${args[@]}")"
    VERDICT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "$JDIR/resultat.json")"
    dit "fumée $VERDICT — page $SORTIE/$PAGE"
    journal "fin fumée $ID : $VERDICT, page $PAGE, RTF ${RTF:-n/a}, $((SECONDS - DEBUT_S)) s"
    commit_pages
    command -v notify-send >/dev/null && [ "$MODE" = si-due ] \
      && notify-send "Didier : fumée $VERDICT" "Page docs/fumee/$PAGE (sha $SHA)" || true
    [ "$VERDICT" = vert ] && rc=0 || rc=1
  fi
  arreter_sim   # idempotent ; couvre le cas « reporté » après démarrage de la sim (RTF trop bas)
  liberer_coeurs
  # Reporté : pas de page, donc pas de dossier de journaux résiduel dans le dépôt.
  [ "$ENGAGEE" = 1 ] || [ -z "$JDIR" ] || rm -rf "$JDIR"
  [ "$ENGAGEE" = 1 ] || rmdir "$SORTIE/journaux" "$SORTIE" 2>/dev/null
  [ -z "$TMP" ] || rm -rf "$TMP"
  exit "$rc"
}
trap terminer EXIT
trap 'exit 143' INT TERM   # le trap EXIT ci-dessus fait le ménage

dodo() {
  local delai="${FUMEE_DODO_DELAI:-20}"
  journal "et-dodo : extinction du PC dans ${delai}s"
  if [ "${FUMEE_DRY_POWEROFF:-0}" = 1 ]; then
    echo "DRY-RUN (FUMEE_DRY_POWEROFF=1) : systemctl poweroff — NON exécuté"
    return 0
  fi
  # Garde-fou (vécu le 07/11 à 21:07 : un agent a lancé « --et-dodo » en croyant être à blanc,
  # sans FUMEE_DRY_POWEROFF, et le PC de David s'est éteint) : l'extinction n'est possible que
  # depuis un VRAI terminal. Un agent, une minuterie ou un script n'en ont pas → jamais d'extinction.
  if [ ! -t 0 ] || [ ! -t 1 ]; then
    dit "pas de terminal interactif : je n'éteins PAS (--et-dodo se lance à la main, dans un terminal)"
    journal "et-dodo : extinction REFUSÉE (pas de terminal interactif)"
    return 0
  fi
  dit "extinction dans ${delai}s (Ctrl-C pour annuler)"
  sleep "$delai"
  systemctl poweroff
}

# ---------------------------------------------------------------------------------
# Déroulé
# ---------------------------------------------------------------------------------
deroule() {
  phase_image || return 0
  phase_demarrage || return 0
  phase_rtf || return 0
  phase_simples || return 0
  phase_chantiers || return 0
  phase_a1 || return 0
}

if [ "$SAUTER_FUMEE" = 1 ]; then
  # --et-dodo qui a attendu une fumée de la minuterie : elle est faite, il ne reste qu'à éteindre.
  ENGAGEE=0; TERMINE=0
  dodo
  exit 0
fi

deroule

if [ "$MODE" = et-dodo ]; then
  # La page doit être écrite et commitée AVANT l'extinction : terminer() quitte, on l'appelle
  # donc dans un sous-shell qui garde le code de retour, puis on éteint.
  set +e
  ( terminer ); RC=$?
  set -e
  TERMINE=1; trap - EXIT
  dodo
  exit "$RC"
fi
