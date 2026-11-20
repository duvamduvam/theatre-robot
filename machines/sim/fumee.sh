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
#   --forcer-verrou     (avec la fumée forcée ou --et-dodo) passe outre ~/tmp/sim-occupee.
#
# Verrou « sim occupée » (18/11) : ~/tmp/sim-occupee (une ligne « <qui> <heure> ») est posé par
# les agents et par David pendant LEUR sim. Présent et daté de moins de 6 h (mtime du fichier ;
# le contenu n'a pas de jour et ne sert qu'à l'affichage) : --si-due reporte, la fumée forcée
# REFUSE (code 2) sauf --forcer-verrou. Plus vieux : ignoré (noté au journal), jamais effacé —
# ce n'est pas le nôtre. La fumée qui démarre pose « fumee <heure> » si le fichier est absent
# (une fumée lancée à la main n'est pas didier-fumee.service : sans cela, un agent ne la verrait
# qu'une fois ses conteneurs nés) et le retire à la fin ; un « fumee … » trouvé au départ est un
# reste (crash, PC éteint) puisque le flock est à nous : retiré.
#
# Une fumée est DUE si un commit touchant un chemin TESTÉ (liste gravée CHEMINS_TESTES en
# tête de fumee_page.py : packages/, data/, deploy/, machines/ — la doc n'en est pas) est
# entré dans main après le sha de la dernière
# page VERTE, OU si 7 jours se sont écoulés sans fumée verte. Après un ROUGE sur un « sha de
# code » (dernier commit touchant un chemin testé) : UNE relance de confirmation, puis plus
# rien sur ce code tant qu'aucun commit de code n'arrive (« bloquée » ; le rappel > 2 jours
# reste). La décision lit les resultat.json (fumee_page.py), jamais le HTML.
#
# Sim multi-conteneurs depuis L2b (spec L2, décision 20) : machines/sim/docker-compose.yml, quatre
# conteneurs (monde, robot, vision, telecommande). Les épreuves tournent dans `monde`, qui partage
# son espace de processus avec les trois autres ; le robot y lance son VRAI bringup (chaîne roues
# comprise, elle tourne dès le démarrage).
#
# Ordre (décision 3), arrêt au PREMIER rouge bloquant (les suivantes : « non lancée ») :
#   images (reconstruites seulement si un chemin de CHEMINS_IMAGES a changé depuis la dernière verte)
#   -> sim headless + colcon ×4 + nœuds attendus -> sonde RTF 20 s (rouge si < 0,8 : le reste
#   n'est pas fiable) -> validate-namespace -> validate-catalogue -> animation parle
#   -> validate-data-edit (L1d) -> validate-machines (L2b)
#   -> régisseur (monde) + regard (robot), validate-rehearsal-chantiers (V-R3)
#   -> sim relancée, validate-jeu-a1 (A1)
#   -> sim relancée, validate-objets (OBJ, lot O1 : tableau des objets, épreuves 1, 2, 4 de l'étude)
#   -> sim relancée AVEC LA TÊTE (surcouche docker-compose.tete.yml : chat_node, clé Anthropic),
#      validate-conversation (CONV, 16/11) — FACULTATIVE : sans clé, « non lancée », jamais rouge.
#                                                 ≈ 55-60 min.
#
# Garde-fous :
#   - domaine ROS 43 : en littéral dans le compose, revérifié dans CHACUN des quatre conteneurs
#     (42 = vrai robot, jamais) ;
#   - un conteneur de la sim déjà présent (l'un des quatre) = la
#     sim de quelqu'un : on reporte (ou on refuse en forcé), on ne la tue JAMAIS ; la sim lancée
#     ici est arrêtée quoi qu'il arrive (trap EXIT), après copie des journaux ;
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
#   FUMEE_SORTIE       dossier des pages VERSIONNÉES : HTML, index, historique.jsonl
#                      (défaut : $FUMEE_DEPOT/docs/fumee)
#   FUMEE_BRUT         journaux BRUTS, LOCAUX (défaut : ~/tmp/didier-fumee) — jamais dans git
#                      ni sur Nextcloud (décision du 16/11) ; vert purgé à 30 j, rouge gardé
#                      tant que son dossier n'a pas le marqueur TRAITE
#   DIDIER_SIM_JOURNAUX journaux de la sim, montés par le compose (défaut :
#                      ~/tmp/didier-sim) — créé ici avant le démarrage
#   FUMEE_COMMIT       1 (défaut) = commit de docs/fumee ; 0 = pas de commit (essais)
#                      — le commit n'a de toute façon lieu que si FUMEE_SORTIE est le défaut
#   FUMEE_RTF_MIN      seuil du facteur temps réel (défaut 0,8) ; tout autre = « essai provoqué »
#   FUMEE_CHARGE_MAX   load average 1 min au-dessus duquel --si-due reporte
#                      (défaut : nb de cœurs × 0,5 — le RTF reste le vrai juge)
#   FUMEE_ETAT         journal + verrou (défaut ~/.local/state/didier-fumee)
#   FUMEE_VERROU_ATTENTE  secondes qu'une fumée forcée attend le verrou avant de refuser (défaut 60)
#   FUMEE_SIM_OCCUPEE  verrou « sim occupée » des agents et de David (défaut ~/tmp/sim-occupee)
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
ATTENDU_MACHINES=5      # validate-machines.sh (L2b : M1-M4, M6 ; 10 en L2c)
ATTENDU_CHANTIERS=21    # validate-rehearsal-chantiers.sh (V-R3)
ATTENDU_A1=14           # validate-jeu-a1.sh (A1)
ATTENDU_OBJETS=13       # validate-objets.sh (OBJ, lot O1 : E1a-e, E2a-e, E4a-c)
ATTENDU_CONVERSATION=19 # validate-conversation.sh (CONV : P1, T0, A1-A3, B1-B5, C1-C3, D1-D6)
RTF_MIN_DEFAUT=0.8
PEREMPTION_SIM_OCCUPEE_S=21600   # 6 h : au-delà, un ~/tmp/sim-occupee oublié ne bloque plus

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAGE_PY="$ICI/fumee_page.py"
DEPOT="${FUMEE_DEPOT:-/home/dadou/Nextcloud/dev/didier/python/theatre-robot}"
SORTIE_DEFAUT="$DEPOT/docs/fumee"
SORTIE="${FUMEE_SORTIE:-$SORTIE_DEFAUT}"
RTF_MIN="${FUMEE_RTF_MIN:-$RTF_MIN_DEFAUT}"
ETAT="${FUMEE_ETAT:-$HOME/.local/state/didier-fumee}"
JOURNAL="$ETAT/journal.log"
BRUT="${FUMEE_BRUT:-$HOME/tmp/didier-fumee}"
SIM_OCCUPEE="${FUMEE_SIM_OCCUPEE:-$HOME/tmp/sim-occupee}"
VERROU_SIM_A_NOUS=0   # 1 si CETTE fumée a posé « fumee <heure> » (seule à pouvoir le retirer)
# Journaux de la sim HORS du dépôt et de Nextcloud (16/11) : MÊME expression que le compose
# (gravé par test_compose_sim.py) ; créés ici par l'utilisateur (sinon Docker les crée root).
JOURNAUX_SIM="${DIDIER_SIM_JOURNAUX:-$HOME/tmp/didier-sim}"
# L2b : la sim multi-conteneurs (projet compose didier-sim). Un service = un conteneur = une image
# locale, jamais poussée.
DOCKER_DIR="$DEPOT/machines/sim"
COMPOSE=docker-compose.yml
# Surcouche de la tête (épreuve CONV seulement, 16/11) : monte les deux secrets de la tête en
# lecture seule. Posée par phase_conversation, vide sinon (la base ne monte AUCUN secret).
COMPOSE_TETE=docker-compose.tete.yml
SURCOUCHES=()
# Les deux fichiers que la surcouche monte (source unique, hors dépôt) ; leur PRÉSENCE seule est
# testée (grep -q, aucune valeur lue ni affichée).
SECRET_OPENROUTER="$HOME/.config/didier/vision-conf-secret"
SECRET_ANTHROPIC="$HOME/.config/didier/secrets.env"
SERVICES=(monde robot vision telecommande)
CONTENEURS=(didier-sim-monde didier-sim-robot didier-sim-vision didier-sim-telecommande)
IMAGES=(didier-sim/monde:local didier-sim/robot:local didier-sim/vision:local didier-sim/telecommande:local)
# Chemins (relatifs au dépôt, git diff) dont un changement depuis la dernière verte reconstruit les
# images (décision 20) : la sim, les Dockerfiles et listes de paquets du robot et de la vision, la
# conf de la télécommande legacy (son Dockerfile y vit).
CHEMINS_IMAGES=(machines/sim machines/robot/docker machines/vision/docker
                machines/robot/packages-docker.txt machines/robot/requirements.txt
                machines/vision/packages-docker.txt machines/vision/requirements.txt
                legacy/dadou_control_ros/conf)
# Démarrage (décision 20) : colcon ×4 + nœuds attendus du robot et de la vision, 600 s au plus.
DELAI_DEMARRAGE=600
NB_COEURS="$(nproc)"
# Cœurs réservés (08/11) : sous un pic de charge le RTF tombait à 0,76 ; sim seule sur 4 cœurs
# rapides réservés = 0,987 (mesuré). Pendant la fumée SEULEMENT : tout est rendu à la fin.
COEURS="${FUMEE_COEURS-8-15}"
COEURS_PY="$ICI/coeurs_reserves.py"
MAINTIEN_PID=""
CHARGE="$(cut -d' ' -f1 /proc/loadavg)"
CHARGE_MAX="${FUMEE_CHARGE_MAX:-$(awk -v n="$NB_COEURS" 'BEGIN { printf "%.1f", n * 0.5 }')}"

MODE=force
FORCER_VERROU=0
for arg in "$@"; do
  case "$arg" in
    --si-due) MODE=si-due ;;
    --et-dodo) MODE=et-dodo ;;
    --forcer-verrou) FORCER_VERROU=1 ;;
    -h|--aide|--help) sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "fumee.sh : argument inconnu « $arg » (--si-due | --et-dodo | --forcer-verrou | --aide)" >&2; exit 2 ;;
  esac
done
# La minuterie ne passe jamais outre la sim de quelqu'un : la combinaison est une erreur.
if [ "$MODE" = si-due ] && [ "$FORCER_VERROU" = 1 ]; then
  echo "fumee.sh : --forcer-verrou ne vaut que pour une fumée lancée à la main, pas avec --si-due" >&2; exit 2
fi

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
  elif [ "$MODE" = force ]; then
    # Fumée lancée à la main ou ENCHAÎNÉE après une autre (16/11) : un verrou en cours de
    # libération se libère en quelques secondes — on l'attend 60 s, puis on REFUSE en le disant
    # (code 2). Avant : sortie muette en 0, la seconde de deux fumées enchaînées « passait » sans
    # rien faire (verrou gardé ≤ 15 s par le `sleep` de la boucle des cœurs, corrigé plus bas).
    flock -w "${FUMEE_VERROU_ATTENTE:-60}" 9 || { dit "REFUS : une autre fumée tient le verrou ($ETAT/verrou) depuis plus de ${FUMEE_VERROU_ATTENTE:-60} s"
                       journal "refus : verrou tenu par une autre fumée (mode $MODE)"; exit 2; }
  else
    exit 0   # minuterie : silence, la place est prise (le prochain passage réessaiera)
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

# --- Verrou « sim occupée » des agents et de David (voir l'en-tête) ----------------
if [ -f "$SIM_OCCUPEE" ]; then
  QUI="$(head -n 1 "$SIM_OCCUPEE" 2>/dev/null | tr -cd '[:print:]' | cut -c1-80 || true)"
  AGE_S=$(( $(date +%s) - $(stat -c %Y "$SIM_OCCUPEE" 2>/dev/null || date +%s) ))
  if [[ "$QUI" == "fumee "* ]]; then
    # Le flock est à nous : aucune autre fumée ne tourne, ce « fumee … » est un reste.
    rm -f -- "$SIM_OCCUPEE"
    journal "reste retiré : verrou $SIM_OCCUPEE « $QUI » d'une fumée finie (âge ${AGE_S} s)"
  elif [ "$AGE_S" -ge "$PEREMPTION_SIM_OCCUPEE_S" ]; then
    journal "verrou $SIM_OCCUPEE « $QUI » PÉRIMÉ (âge ${AGE_S} s ≥ ${PEREMPTION_SIM_OCCUPEE_S} s) : ignoré, pas effacé"
  elif [ "$MODE" = si-due ]; then
    reporter "sim réservée par « $QUI » ($SIM_OCCUPEE, âge ${AGE_S} s)"
  elif [ "$FORCER_VERROU" = 1 ]; then
    journal "verrou $SIM_OCCUPEE « $QUI » outrepassé (--forcer-verrou, mode $MODE)"
    dit "verrou « $QUI » outrepassé (--forcer-verrou)"
    NOTES_VERROU="verrou « sim occupée » de « $QUI » outrepassé (--forcer-verrou)"
  else
    journal "refus : sim réservée par « $QUI » ($SIM_OCCUPEE, mode $MODE)"
    dit "REFUS : la sim est réservée par « $QUI » ($SIM_OCCUPEE, posé il y a $((AGE_S / 60)) min). Attends qu'il le retire, ou relance avec --forcer-verrou si tu sais que cette sim est finie."
    exit 2
  fi
fi

# --- Un conteneur sim déjà là est celui de quelqu'un : jamais touché --------------
# Les quatre de la sim multi-conteneurs. Liste lue une fois, sans --filter (un nom exact par ligne).
EXISTANTS="$(docker ps -a --format '{{.Names}}' 2>/dev/null || true)"
for nom_c in "${CONTENEURS[@]}"; do
  grep -qx -- "$nom_c" <<<"$EXISTANTS" || continue
  ETAT_C="$(docker inspect -f '{{.State.Status}}' "$nom_c" 2>/dev/null || echo inconnu)"
  # Un conteneur ARRÊTÉ (exited/dead/created) ne fait tourner la sim de personne : c'est un reste
  # (vécu le 08/11 : PC éteint au bouton à 02:32 pendant une fumée → conteneur exited, et la
  # minuterie a reporté toute la matinée). On le retire (docker rm SANS -f : refuse s'il tourne)
  # et on continue. Seul un conteneur vivant (running/paused/restarting) reste intouchable.
  case "$ETAT_C" in
    exited|dead|created)
      if docker rm "$nom_c" >/dev/null 2>&1; then
        journal "reste retiré : conteneur $nom_c arrêté ($ETAT_C)"
        continue
      fi ;;
  esac
  if [ "$MODE" = si-due ]; then reporter "conteneur $nom_c déjà présent ($ETAT_C), pas touché"; fi
  journal "refus : conteneur $nom_c déjà présent ($ETAT_C)"
  dit "REFUS : le conteneur $nom_c existe déjà ($ETAT_C). C'est une sim à toi : arrête-la toi-même (cd machines/sim && docker compose down) puis relance. Je ne la touche pas."
  exit 2
done

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
[ ! -e "$BRUT/$ID" ] || ID="$(date +%Y-%m-%d-%H%M%S)"
JDIR="$BRUT/$ID"
JSONL="$TMP/epreuves.jsonl"
mkdir -p "$JDIR"
ESSAI=0
{ [ "${FUMEE_ESSAI:-0}" = 1 ] || [ "$RTF_MIN" != "$RTF_MIN_DEFAUT" ]; } && ESSAI=1
[ "$BRANCHE" = main ] || NOTES+=("le checkout testé est sur la branche $BRANCHE, pas sur main")
[ -z "${NOTES_VERROU:-}" ] || NOTES+=("$NOTES_VERROU")
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

# Commande dans le conteneur d'un SERVICE (monde, robot, vision, telecommande), avec l'environnement
# ROS (le $ROS_DISTRO s'évalue DANS le conteneur). Les épreuves et les sondes tournent dans `monde`.
conteneur_de() { echo "didier-sim-$1"; }
ros_dans() { docker exec "$(conteneur_de "$1")" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && '"$2"; }
ros_detache() { docker exec -d "$(conteneur_de "$1")" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && '"$2"; }
python_ros() { docker exec -i "$(conteneur_de monde)" bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && python3 -'; }

# Sous `pipefail`, JAMAIS `docker logs … | grep -q` ni `docker ps … | grep -q` : grep -q sort au
# premier motif trouvé, l'écrivain meurt de SIGPIPE (141) dès que la sortie dépasse un tampon, et la
# pipeline ÉCHOUE alors que le motif est là. Vécu le 16/11 23:30 : chat_node (micro absent en sim)
# gonfle le journal vision (350 Ko en 10 min), son « Summary » n'est plus jamais compté (colcon
# 3/4 pendant 600 s) et CONV tombe rouge sans avoir tourné ; le même tube masquait un ÉCHEC de
# colcon. Reproduit : 0/20 avec le vrai docker logs, 20/20 via un fichier. On capture d'abord.
conteneur_vivant() { # conteneur_vivant <nom> : 0 si ce conteneur EXACT est en marche
  local noms; noms="$(docker ps --format '{{.Names}}' 2>/dev/null || true)"
  grep -qx -- "$1" <<<"$noms"
}

etat_conteneur() { # etat_conteneur <nom> : « exited, code 137, fin … » ou « absent » (diagnostic)
  docker inspect -f '{{.State.Status}}, code {{.State.ExitCode}}, fin {{.State.FinishedAt}}' "$1" 2>/dev/null || echo absent
}

etat_colcon() { # etat_colcon <conteneur> -> fini | echec | en_cours ; journal copié dans $TMP/docker-<c>.log
  local f="$TMP/docker-$1.log"
  docker logs "$1" >"$f" 2>&1 || true
  if grep -qE 'Failed +<<<|packages? failed' "$f"; then echo echec
  elif grep -qE 'Summary: [0-9]+ packages? finished' "$f"; then echo fini
  else echo en_cours; fi
}

attendre_processus() { # attendre_processus <motif> <présent|absent> <secondes>
  # pgrep depuis `monde` : robot, vision et télécommande partagent son espace de processus.
  local motif=$1 voulu=$2 delai=$3 t0=$SECONDS present
  while [ $((SECONDS - t0)) -lt "$delai" ]; do
    if docker exec "$(conteneur_de monde)" pgrep -f "$motif" >/dev/null 2>&1; then present=présent; else present=absent; fi
    [ "$present" = "$voulu" ] && return 0
    sleep 2
  done
  return 1
}

recolter() { # recolter <nom> : copie hors conteneurs AVANT leur arrêt (les journaux meurent avec eux)
  conteneur_vivant "$(conteneur_de monde)" || { NOTES+=("journaux des conteneurs non récoltés ($1) : monde n'est plus en marche ($(etat_conteneur "$(conteneur_de monde)"))"); return 0; }
  local d="$TMP/recolte-$1" s; mkdir -p "$d/tmp"
  for s in "${SERVICES[@]}"; do
    docker logs "$(conteneur_de "$s")" >"$d/$s-docker.log" 2>&1 || true
  done
  # log/ est partagé par monde et robot (robot.log, rehearsal/, jeu/, tickets/) ; vision et
  # télécommande ont le leur.
  docker cp "$(conteneur_de monde):/home/ros2_ws/log" "$d/ros2_ws-log" >/dev/null 2>&1 || true
  docker cp "$(conteneur_de vision):/home/ros2_ws/log" "$d/vision-log" >/dev/null 2>&1 || true
  docker cp "$(conteneur_de telecommande):/home/ros2_ws/log" "$d/telecommande-log" >/dev/null 2>&1 || true
  # Les captures des épreuves sont sous log/ (copié ci-dessus, et en entier par copier_captures).
  docker exec "$(conteneur_de monde)" bash -c 'cd /tmp && tar -cf - validate-*.log 2>/dev/null' \
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
  (cd "$DOCKER_DIR" && docker compose -f "$COMPOSE" "${SURCOUCHES[@]}" down -t 20) >/dev/null 2>&1 || true
  local c
  for c in "${CONTENEURS[@]}"; do   # seulement les nôtres : SIM_A_NOUS=1
    docker rm -f "$c" >/dev/null 2>&1 || true
  done
  SIM_A_NOUS=0
}

epingler_sim() { # la sim sur les cœurs réservés, et le reste du PC poussé ailleurs (une fois)
  [ -n "$COEURS" ] || return 0
  local c sims=()
  for c in "${CONTENEURS[@]}"; do
    docker update --cpuset-cpus "$COEURS" "$c" >/dev/null 2>&1 \
      || { NOTES+=("cœurs réservés : épinglage de $c sur $COEURS refusé par docker"); return 0; }
    sims+=(--sim "$c")
  done
  [ -z "$MAINTIEN_PID" ] || return 0
  # Reliquat d'une fumée tuée (état encore présent) : on rend d'abord, on réserve ensuite.
  python3 "$COEURS_PY" liberer --etat "$ETAT/coeurs.json" >/dev/null 2>&1 || true
  dit "$(python3 "$COEURS_PY" reserver --coeurs "$COEURS" --etat "$ETAT/coeurs.json" "${sims[@]}" 2>&1 || true)"
  # Les processus lancés PENDANT la fumée (un nouvel onglet, un build) héritent de leur parent,
  # déjà poussé ; ceux qui naîtraient ailleurs sont rattrapés par cette passe toutes les 15 s.
  # `9>&-` : la boucle et ses fils (sleep, python) ne gardent PAS le descripteur du verrou —
  # sinon le `sleep 15` orphelin du kill le tenait encore jusqu'à 15 s après la fin (16/11 : la
  # seconde de deux fumées enchaînées sortait sans rien faire).
  ( while sleep 15; do
      python3 "$COEURS_PY" maintenir --coeurs "$COEURS" --etat "$ETAT/coeurs.json" "${sims[@]}" >/dev/null 2>&1 || true
    done ) 9>&- &
  MAINTIEN_PID=$!
}

liberer_coeurs() { # idempotent : rend affinités et cpusets d'origine (aussi sous trap EXIT)
  if [ -n "$MAINTIEN_PID" ]; then
    # La boucle PUIS ses fils, par PID (relevés avant : orphelins, ils ne seraient plus ses fils).
    # Un `maintenir` survivant repousserait les processus de David APRÈS la libération.
    local enfants; enfants="$(pgrep -P "$MAINTIEN_PID" 2>/dev/null || true)"
    kill "$MAINTIEN_PID" 2>/dev/null || true
    [ -z "$enfants" ] || kill $enfants 2>/dev/null || true
    wait "$MAINTIEN_PID" 2>/dev/null || true
  fi
  MAINTIEN_PID=""
  [ -f "$ETAT/coeurs.json" ] || return 0
  dit "$(python3 "$COEURS_PY" liberer --etat "$ETAT/coeurs.json" 2>&1 || true)"
}

noeuds_attendus_vus() { # 0 si les noeuds_attendus des machine.yml robot ET vision sont vus depuis monde
  python_ros <<'PY' >>"$TMP/demarrage.log" 2>&1
# Nœuds attendus lus dans les machine.yml (montés en lecture seule dans monde), graphe vu en rclpy
# (la CLI ros2 perd des messages sur ce PC) ; ≥ 5 s de découverte (3 s comptent trop peu, L2a).
import sys, time
import rclpy, yaml
voulus = set()
for m in ("robot", "vision"):
    with open("/home/ros2_ws/machines/%s/machine.yml" % m, encoding="utf-8") as f:
        voulus |= set(yaml.safe_load(f)["noeuds_attendus"])
rclpy.init()
n = rclpy.create_node("fumee_noeuds")
debut = time.monotonic()
while time.monotonic() - debut < 8:
    rclpy.spin_once(n, timeout_sec=0.2)
vus = {(ns.rstrip("/") + "/" + nom) for nom, ns in n.get_node_names_and_namespaces()}
manque = sorted(voulus - vus)
print("nœuds attendus : %d/%d%s" % (len(voulus) - len(manque), len(voulus), (" — manquent : " + " ".join(manque)) if manque else ""))
sys.exit(1 if manque else 0)
PY
}

demarrer_sim() { # demarrer_sim : lance la sim headless (monde chantiers) puis attend colcon ×4, pont, nœuds
  dit "démarrage de la sim (4 conteneurs, headless, domaine 43, colcon ×4 ≈ 2-4 min)"
  # SIM_A_NOUS avant le `up` : même un échec en cours de route laisse des conteneurs À NOUS,
  # que terminer() doit retirer (on a vérifié plus haut qu'aucun conteneur homonyme n'existait).
  SIM_A_NOUS=1
  # Le domaine n'est PAS passé ici : le compose pose ROS_DOMAIN_ID=43 en littéral et ne le lit
  # jamais dans l'environnement de l'appelant ; on le revérifie dans chaque conteneur ci-dessous.
  mkdir -p "$JOURNAUX_SIM"/log "$JOURNAUX_SIM"/log-vision "$JOURNAUX_SIM"/log-telecommande
  (cd "$DOCKER_DIR" && env ROBOT_NAME=didier HEADLESS=true WORLD=chantiers DIDIER_SIM_JOURNAUX="$JOURNAUX_SIM" \
      REHEARSAL=true FACE=true WEB_DRIVE=false DATA_EDIT=true \
      docker compose -f "$COMPOSE" "${SURCOUCHES[@]}" up -d) >>"$TMP/demarrage.log" 2>&1 || return 1
  epingler_sim
  local c s domaine
  for c in "${CONTENEURS[@]}"; do
    domaine="$(docker exec "$c" printenv ROS_DOMAIN_ID 2>/dev/null || echo ?)"
    if [ "$domaine" != 43 ]; then echo "ROS_DOMAIN_ID=$domaine dans $c : REFUS (ROS_DOMAIN_ID=43 exigé)" >>"$TMP/demarrage.log"; return 1; fi
  done
  echo "domaine 43 lu dans les ${#CONTENEURS[@]} conteneurs" >>"$TMP/demarrage.log"
  # Prêt = colcon fini sans échec dans les 4, le pont gz lancé, Gazebo vivant, puis les nœuds
  # attendus du robot et de la vision vus depuis monde.
  local t0=$SECONDS colcon_ok pont=0 en_cours etat
  while [ $((SECONDS - t0)) -lt "$DELAI_DEMARRAGE" ]; do
    colcon_ok=0 en_cours=""
    for s in "${SERVICES[@]}"; do
      c="$(conteneur_de "$s")"
      conteneur_vivant "$c" || { echo "le conteneur $c s'est arrêté ($(etat_conteneur "$c"))" >>"$TMP/demarrage.log"; docker logs "$c" 2>&1 | tail -40 >>"$TMP/demarrage.log"; return 1; }
      etat="$(etat_colcon "$c")"
      if [ "$etat" = echec ]; then
        echo "colcon build a échoué dans $c" >>"$TMP/demarrage.log"; cat "$TMP/docker-$c.log" >>"$TMP/demarrage.log"; return 1
      fi
      if [ "$etat" = fini ]; then colcon_ok=$((colcon_ok + 1)); else en_cours+=" $s"; fi
    done
    if [ "$pont" = 0 ] && docker exec "$(conteneur_de monde)" pgrep -f parameter_bridge >/dev/null 2>&1; then
      sleep 15   # laisse le monde se charger avant de mesurer quoi que ce soit
      # Le pont vit sans Gazebo : sans ce contrôle, un moteur de rendu mort (autorité X,
      # GPU) ne se verrait qu'au RTF, sous une cause trompeuse.
      if ! docker exec "$(conteneur_de monde)" pgrep -f "gz sim" >/dev/null 2>&1; then
        # L'état du conteneur dit si c'est Gazebo qui est mort ou TOUTE la sim (17/11 00:39 : PC
        # éteint au bouton pendant la relance A1 — démon docker arrêté, rouge lu « Gazebo mort »).
        { echo "Gazebo (gz sim) absent au démarrage — conteneur monde : $(etat_conteneur "$(conteneur_de monde)") — extrait de son journal :"
          docker logs "$(conteneur_de monde)" 2>&1 | grep -E "process has died|Segmentation|Authorization required|Unable to create the rendering" | tail -5 | cut -c1-300
        } >>"$TMP/demarrage.log"
        return 1
      fi
      pont=1
      echo "pont gz et Gazebo vivants après $((SECONDS - t0)) s" >>"$TMP/demarrage.log"
    fi
    if [ "$pont" = 1 ] && [ "$colcon_ok" = "${#SERVICES[@]}" ] && noeuds_attendus_vus; then
      echo "colcon fini dans les ${#SERVICES[@]} conteneurs, nœuds attendus vus après $((SECONDS - t0)) s" >>"$TMP/demarrage.log"
      return 0
    fi
    sleep 5
  done
  echo "sim incomplète après $DELAI_DEMARRAGE s (pont gz : $pont, colcon fini : ${colcon_ok:-0}/${#SERVICES[@]}${en_cours:+, pas fini :$en_cours})" >>"$TMP/demarrage.log"; return 1
}

copier_captures() { # copier_captures <id> <dossier dans monde> -> $JDIR/captures-<id>/ (gros fichiers gzippés)
  local d="$JDIR/captures-$1"
  docker exec "$(conteneur_de monde)" test -d "$2" 2>/dev/null || return 0
  docker cp "$(conteneur_de monde):$2" "$d" >/dev/null 2>&1 || { NOTES+=("captures de $1 non copiées ($2)"); return 0; }
  find "$d" -type f -size +64k \( -name '*.jsonl' -o -name '*.json' \) -exec gzip -9 {} + 2>/dev/null || true
}

lancer_validation() { # lancer_validation <id> <script> <attendu> <motif de la ligne finale> <délai s>
  local id=$1 script=$2 attendu=$3 motif=$4 delai=$5 log="$TMP/$1.log" t0=$SECONDS rc=0 ligne ok ko detail=""
  dit "épreuve $id : $script (attendu $attendu OK, ≤ $((delai / 60)) min)"
  # Captures de l'épreuve (captures.sh, A1) dans un dossier à elle sous log/, copiées ensuite dans
  # les journaux de la fumée : un rouge reste diagnosticable après coup (lot fiabilité, 16/11).
  local cap="/home/ros2_ws/log/captures/fumee-$ID-$id"
  timeout -k 15 "$((delai + 60))" docker exec -e CAPTURE_DIR="$cap" "$(conteneur_de monde)" \
    timeout -k 10 "$delai" bash "/home/ros2_ws/$script" >"$log" 2>&1 || rc=$?
  copier_captures "$id" "$cap"
  ligne="$(grep -E "$motif" "$log" | tail -1 || true)"
  ok="$(sed -nE 's/.* ([0-9]+) OK, ([0-9]+) KO.*/\1/p' <<<"$ligne")"
  ko="$(sed -nE 's/.* ([0-9]+) OK, ([0-9]+) KO.*/\2/p' <<<"$ligne")"
  local statut=""
  if [ -z "$ok" ] && grep -qi "mesure invalide" "$log"; then
    ok=0; ko=0; statut=rouge; detail="MESURE INVALIDE (code $rc) : l'enregistreur des captures est mort pendant l'épreuve — défaut du banc, pas de Didier ; voir captures-$id/"
  elif [ -z "$ok" ]; then
    ok=0; ko=0; statut=rouge; detail="aucun compteur lu en fin de script (code $rc) : précondition, délai dépassé ou crash — voir le journal"
  elif [ "$rc" != 0 ] && [ "$ok" = "$attendu" ] && [ "$ko" = 0 ]; then
    statut=rouge; detail="compteur conforme mais code de retour $rc"
  fi
  epreuve "$id" ${statut:+--statut "$statut"} --ok "$ok" --attendu "$attendu" --ko "$ko" \
    --duree "$((SECONDS - t0))" --journal "$id.log" ${detail:+--detail "$detail"}
  [ "$ok" = "$attendu" ] && [ "$ko" = 0 ] && [ "$rc" = 0 ]
}

lancer_corps() { # lancer_corps <scénario chantiers|jeu-a1> <jeu:=true|''> : régisseur + regard
  # L2b : la chaîne roues n'est plus lancée ici — elle fait partie du vrai bringup du conteneur
  # robot (robot_app.launch.py use_sim_time:=true) et tourne dès le démarrage. La répétition vit
  # dans monde, le regard (didier_core) dans robot.
  local scenario=$1 jeu=$2
  attendre_processus "lib/didier_rehearsal/director" absent 30 || true
  attendre_processus "/twist_deadman( |$)" présent 30 || return 1
  ros_detache monde "ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=$scenario $jeu"
  ros_detache robot 'ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier'
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
# L2b : `animation` a plusieurs abonnés (animations_node, web_bridge_node) dans des conteneurs
# distincts ; « au moins un apparié » ne disait plus qu'animations_node l'était (vu le 14/11 :
# ETATS=[""], rien reçu au journal du robot). On attend qu'il soit dans le graphe ET que tous
# les abonnés vus soient appariés ; puis, comme pour toute commande idempotente (operations.md,
# piège de la CLI), on vérifie PAR L'EFFET : sans « parle » en 5 s, on renvoie (3 envois au plus).
def abonnes():
    return [i.node_name for i in n.get_subscriptions_info_by_topic(NS + '/animation')]
limite = time.monotonic() + 40
while time.monotonic() < limite and (not etats or 'animations_node' not in abonnes()
                                     or pub.get_subscription_count() < len(abonnes())):
    rclpy.spin_once(n, timeout_sec=0.2)
print('ABONNES=%s apparies=%d' % (json.dumps(sorted(abonnes())), pub.get_subscription_count()))
m = StringTime(); m.msg = json.dumps('parle'); m.time = 3000; m.anim = False
for envoi in range(1, 4):
    pub.publish(m)
    fin_envoi = time.monotonic() + 5
    while time.monotonic() < fin_envoi and 'parle' not in etats:
        rclpy.spin_once(n, timeout_sec=0.2)
    if 'parle' in etats:
        break
print('ENVOIS=%d' % envoi)
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
  local t0=$SECONDS raison="" ref image
  ref="$(python3 "$PAGE_PY" dernier-vert --sortie "$SORTIE")"
  for image in "${IMAGES[@]}"; do
    docker image inspect "$image" >/dev/null 2>&1 || { raison="image $image absente"; break; }
  done
  if [ -n "$raison" ]; then :
  elif [ -z "$ref" ]; then raison="aucune fumée verte de référence"
  elif ! git -C "$DEPOT" cat-file -e "$ref^{commit}" 2>/dev/null; then raison="sha de référence $ref inconnu"
  elif ! git -C "$DEPOT" diff --quiet "$ref" -- "${CHEMINS_IMAGES[@]}"; then raison="sim, Dockerfile ou liste de paquets modifiés depuis ${ref:0:7}"
  fi
  if [ -z "$raison" ]; then
    epreuve image --statut vert --detail "inchangées depuis la dernière fumée verte (${ref:0:7}), non reconstruites" --duree 0
    return 0
  fi
  dit "reconstruction des ${#IMAGES[@]} images de la sim ($raison, cache : 1-5 min ; à froid ≈ 15 min)"
  IMAGE_RECONSTRUITE=1
  if construire_images; then
    epreuve image --statut vert --detail "reconstruite : $raison" --duree "$((SECONDS - t0))" --journal image.log
  elif panne_reseau_build "$TMP/image.log"; then
    # Ni le code ni Didier : le registre (Docker Hub) était injoignable, même après un essai de plus.
    epreuve image --statut rouge --detail "PANNE RÉSEAU : registre Docker injoignable pendant la reconstruction ($raison) — défaut de l'environnement, pas de Didier ; relancer plus tard" \
      --duree "$((SECONDS - t0))" --journal image.log
    return 1
  else
    epreuve image --statut rouge --detail "la reconstruction a échoué ($raison)" --duree "$((SECONDS - t0))" --journal image.log
    return 1
  fi
}

# panne_reseau_build <journal> : 0 si l'échec du build vient du RÉSEAU (registre ou DNS injoignable),
# pas du Dockerfile. Vécu le 18/11 10:36 : « lookup registry-1.docker.io … i/o timeout » sur le
# FROM ros:jazzy-ros-base (buildx résout les métadonnées de l'image de base même en cache) : la
# fumée rougissait en 11 s sans avoir rien testé.
panne_reseau_build() {
  grep -qiE 'lookup [^ ]+ on [^ ]+: .*(i/o timeout|no such host|server misbehaving)|dial tcp: .*(i/o timeout|connection refused|network is unreachable)|TLS handshake timeout|temporary failure in name resolution|failed to do request: (Head|Get) "https://[^"]*(docker\.io|docker\.com)' "$1"
}

# construire_images : reconstruit ; si l'échec vient du réseau, UN essai de plus après
# ${FUMEE_ATTENTE_RESEAU:-60} s (une coupure DNS de quelques secondes ne doit pas rougir la fumée).
construire_images() {
  (cd "$DOCKER_DIR" && docker compose -f "$COMPOSE" build) >"$TMP/image.log" 2>&1 && return 0
  panne_reseau_build "$TMP/image.log" || return 1
  dit "registre Docker injoignable : nouvel essai dans ${FUMEE_ATTENTE_RESEAU:-60} s"
  sleep "${FUMEE_ATTENTE_RESEAU:-60}"
  echo "=== nouvel essai après panne réseau ===" >>"$TMP/image.log"
  (cd "$DOCKER_DIR" && docker compose -f "$COMPOSE" build) >>"$TMP/image.log" 2>&1
}

phase_demarrage() {
  local t0=$SECONDS
  if demarrer_sim; then
    epreuve demarrage --statut vert --detail "${#CONTENEURS[@]} conteneurs, domaine 43 dans chacun, colcon ×${#SERVICES[@]}, nœuds attendus, monde chantiers, headless" \
      --duree "$((SECONDS - t0))" --journal demarrage.log
  else
    epreuve demarrage --statut rouge --detail "la sim n'a pas démarré proprement (domaine, colcon, conteneur, pont gz ou nœuds attendus)" \
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
    grep -q 'messages=0' "$TMP/rtf.log" && cause="aucun message sur /clock en 120 s : Gazebo ne publie rien (voir monde-docker.log dans le .tar.gz)"
    epreuve rtf --statut rouge --obtenu "$RTF" --detail "$cause" --duree "$((SECONDS - t0))" --journal rtf.log
    return 1
  fi
}

phase_simples() {
  # À ce stade la sim tourne avec le vrai bringup du robot (chaîne roues et pont web compris) ;
  # la répétition est lancée par les scripts eux-mêmes s'il la leur faut.
  lancer_validation namespace validate-namespace.sh "$ATTENDU_NAMESPACE" 'validate-namespace' 300 || return 1
  lancer_validation catalogue validate-catalogue.sh "$ATTENDU_CATALOGUE" 'validate-catalogue' 180 || return 1
  local t0=$SECONDS sortie ok
  dit "épreuve parle (animation_state \"\" -> \"parle\" -> \"\")"
  sortie="$(jouer_parle 2>&1 || true)"; printf '%s\n' "$sortie" >"$TMP/parle.log"
  ok="$(sed -nE 's/^PARLE ([0-9]+) OK.*/\1/p' <<<"$sortie" | tail -1)"; ok="${ok:-0}"
  epreuve parle --ok "$ok" --attendu "$ATTENDU_PARLE" --ko "$((ATTENDU_PARLE - ok))" \
    --detail "$(grep '^ETATS=' <<<"$sortie" | tail -1)" --duree "$((SECONDS - t0))" --journal parle.log
  [ "$ok" = "$ATTENDU_PARLE" ] || return 1
  # Édition à travers le robot (L1d) : la chaîne roues tourne déjà (l'épreuve 7 mesure la tenue de
  # cmd_vel) ; restaure ce qu'elle écrit dans data/.
  lancer_validation edition validate-data-edit.sh "$ATTENDU_EDITION" 'validate-data-edit' 300
}

phase_machines() {
  # L2b (décision 21) : les machines de la sim sont toutes là et se parlent, vues depuis monde.
  lancer_validation machines validate-machines.sh "$ATTENDU_MACHINES" 'validate-machines' 180
}

phase_chantiers() {
  PHASE_COURANTE=chantiers
  lancer_corps chantiers '' || { epreuve chantiers --statut rouge --detail "chaîne roues absente, ou régisseur (monde) / regard (robot) non démarrés"; return 1; }
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
  lancer_corps jeu-a1 'jeu:=true' || { epreuve a1 --statut rouge --detail "chaîne roues absente, ou régisseur jeu (monde) / regard (robot) non démarrés"; return 1; }
  lancer_validation a1 validate-jeu-a1.sh "$ATTENDU_A1" '=== A1' 1500
}

phase_objets() {
  # OBJ (lot O1, 18/11) : sim NEUVE (les téléportations et dix gestes ne doivent ni hériter de
  # l'état d'A1 ni en laisser à CONV). Zéro jeton : le pilote joue la bouche.
  recolter a1; arreter_sim
  PHASE_COURANTE=objets
  local t0=$SECONDS
  if ! demarrer_sim; then
    epreuve objets --statut rouge --detail "la sim relancée n'a pas démarré (voir demarrage.log)" --duree "$((SECONDS - t0))" --journal demarrage.log
    return 1
  fi
  lancer_corps jeu-a1 'jeu:=true' || { epreuve objets --statut rouge --detail "chaîne roues absente, ou régisseur jeu (monde) / regard (robot) non démarrés"; return 1; }
  lancer_validation objets validate-objets.sh "$ATTENDU_OBJETS" '=== OBJ' 900
}

phase_conversation() {
  # CONV (16/11) : la tête tourne SEULEMENT pour cette épreuve — sim relancée avec la surcouche
  # docker-compose.tete.yml (chat_node sans micro ni son, clé Anthropic). Coût ≈ 0,003 $ (Haiku).
  # FACULTATIVE : sans clé Anthropic (ou sans le secret OpenRouter, exigé par chat_node au
  # démarrage), elle n'est pas lancée et ne rougit JAMAIS la fumée.
  recolter objets; arreter_sim
  PHASE_COURANTE=conversation
  if ! grep -q '^ANTHROPIC_API_KEY=.' "$SECRET_ANTHROPIC" 2>/dev/null || [ ! -f "$SECRET_OPENROUTER" ]; then
    epreuve conversation --statut non_lance --facultative --duree 0 \
      --detail "non lancée (pas de clé) : ANTHROPIC_API_KEY absente de ${SECRET_ANTHROPIC/#$HOME/\~} ou ${SECRET_OPENROUTER/#$HOME/\~} manquant"
    return 0
  fi
  SURCOUCHES=(-f "$COMPOSE_TETE")
  local t0=$SECONDS
  if ! demarrer_sim; then
    epreuve conversation --statut rouge --detail "la sim relancée avec la tête n'a pas démarré (voir demarrage.log)" --duree "$((SECONDS - t0))" --journal demarrage.log
    return 1
  fi
  lancer_corps jeu-a1 'jeu:=true' || { epreuve conversation --statut rouge --detail "chaîne roues absente, ou régisseur jeu (monde) / regard (robot) non démarrés"; return 1; }
  lancer_validation conversation validate-conversation.sh "$ATTENDU_CONVERSATION" '=== CONV' 600
  local rc=$? bascules
  # Bascules de secours Anthropic -> OpenRouter pendant l'épreuve (journal de chat_node) : dites
  # sur la page, sans rien changer au verdict (la parole ne s'est pas bloquée).
  bascules="$(docker logs "$(conteneur_de vision)" 2>&1 | grep -c 'bascule de secours' || true)"
  [ "${bascules:-0}" = 0 ] || NOTES+=("conversation : $bascules bascule(s) de secours Anthropic → OpenRouter (journal de chat_node)")
  return "$rc"
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
            -m "Page docs/fumee/$PAGE et une ligne de docs/fumee/historique.jsonl ; journaux bruts LOCAUX ($ID, hors git). Commit automatique de fumee.sh (lot F), docs/fumee seulement." \
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
    # PC en cours d'extinction (bouton, menu) : lecture SEULE de l'état de systemd. Le 17/11 à
    # 00:39, David a éteint le PC pendant la relance A1 ; le rouge se lisait « Gazebo mort ».
    [ "$(systemctl is-system-running 2>/dev/null || true)" != stopping ] \
      || NOTES+=("le PC s'éteignait à la fin de la fumée (systemd « stopping ») : le rouge de la dernière épreuve vient de l'extinction, pas de Didier")
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
    local args=() n
    for n in "${NOTES[@]}"; do args+=(--note "$n"); done
    PAGE="$(python3 "$PAGE_PY" finaliser --jsonl "$JSONL" --sortie "$SORTIE" --id "$ID" \
      --brut "$BRUT" --brut-affiche "${BRUT/#$HOME/\~}" \
      --meta "sha=$SHA" --meta "sha_complet=$SHA_COMPLET" --meta "sale=$SALE" --meta "branche=$BRANCHE" \
      --meta "mode=$MODE" --meta "raison=$RAISON" --meta "debut=$DEBUT_ISO" --meta "fin=$(date -Iseconds)" \
      --meta "duree_s=$((SECONDS - DEBUT_S))" --meta "rtf=${RTF}" --meta "rtf_min=$RTF_MIN" \
      --meta "charge_1min=$CHARGE" --meta "nb_coeurs=$NB_COEURS" --meta "essai=$ESSAI" \
      --meta "image_reconstruite=$IMAGE_RECONSTRUITE" --meta "coeurs_reserves=${COEURS:-aucun}" "${args[@]}")"
    VERDICT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "$JDIR/resultat.json")"
    dit "fumée $VERDICT — page $SORTIE/$PAGE, brut $JDIR"
    # Purge du brut LOCAL : vertes de plus de 30 jours ; un rouge reste tant qu'il n'est pas TRAITE.
    python3 "$PAGE_PY" purger --brut "$BRUT" | while read -r l; do journal "$l"; done
    journal "fin fumée $ID : $VERDICT, page $PAGE, RTF ${RTF:-n/a}, $((SECONDS - DEBUT_S)) s"
    commit_pages
    command -v notify-send >/dev/null && [ "$MODE" = si-due ] \
      && notify-send "Didier : fumée $VERDICT" "Page docs/fumee/$PAGE (sha $SHA)" || true
    [ "$VERDICT" = vert ] && rc=0 || rc=1
  fi
  arreter_sim   # idempotent ; couvre le cas « reporté » après démarrage de la sim (RTF trop bas)
  liberer_coeurs
  liberer_verrou_sim
  # Reporté : pas de page, donc pas de dossier de journaux résiduel.
  [ "$ENGAGEE" = 1 ] || [ -z "$JDIR" ] || rm -rf "$JDIR"
  [ "$ENGAGEE" = 1 ] || rmdir "$SORTIE" 2>/dev/null
  [ -z "$TMP" ] || rm -rf "$TMP"
  exit "$rc"
}
trap terminer EXIT
trap 'exit 143' INT TERM   # le trap EXIT ci-dessus fait le ménage

poser_verrou_sim() { # « fumee <heure> » si le fichier est absent (jamais par-dessus celui d'un autre)
  [ -e "$SIM_OCCUPEE" ] && return 0
  mkdir -p "$(dirname "$SIM_OCCUPEE")"
  # noclobber : si quelqu'un le pose dans la même seconde, le sien gagne et on n'y touche pas.
  if ( set -C; echo "fumee $(date +%H:%M)" >"$SIM_OCCUPEE" ) 2>/dev/null; then
    VERROU_SIM_A_NOUS=1
    VERROU_SIM_CONTENU="$(cat "$SIM_OCCUPEE")"
  fi
}
liberer_verrou_sim() { # idempotent ; ne retire que NOTRE ligne, intacte
  [ "$VERROU_SIM_A_NOUS" = 1 ] || return 0
  VERROU_SIM_A_NOUS=0
  [ "$(cat "$SIM_OCCUPEE" 2>/dev/null)" = "${VERROU_SIM_CONTENU:-}" ] && rm -f -- "$SIM_OCCUPEE"
  return 0
}

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
  phase_machines || return 0
  phase_chantiers || return 0
  phase_a1 || return 0
  phase_objets || return 0
  phase_conversation || return 0
}

if [ "$SAUTER_FUMEE" = 1 ]; then
  # --et-dodo qui a attendu une fumée de la minuterie : elle est faite, il ne reste qu'à éteindre.
  ENGAGEE=0; TERMINE=0
  dodo
  exit 0
fi

poser_verrou_sim
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
