#!/bin/bash
# L1c — preuve REJOUABLE que le robot PUBLIE son catalogue et son sha en
# simulation (spec theatre-robot/docs/spec-L1-contrats-donnees.md, L1c
# décision 8), DANS le conteneur sim (domaine 43). Exige :
#   1. `$NS/catalogue` : JSON à 6 clés, toutes NON vides ;
#   2. `$NS/deploy_sha` : "dev" (la sim n'a pas de conf/DEPLOY_SHA) ;
#   3. une séquence temporaire déposée sous json/sequences/tmp-l1c/ apparaît
#      dans le catalogue republié en <= $DELAI s ;
#   4. sa suppression la fait disparaître en <= $DELAI s.
# Sortie 0 = OK ; 1 = KO ; 2 = banc faux (hors sim, nœud absent).
# Le dossier temporaire est supprimé en sortant, quoi qu'il arrive : json/ est
# monté depuis l'arbre de travail du PC, un résidu serait versionné par erreur.
# Rien ici ne peut atteindre le vrai robot : refus hors domaine 43.
source /opt/ros/${ROS_DISTRO}/setup.sh
source /home/ros2_ws/install/setup.bash
# La CLI ne suit PAS le namespace du robot : chaque topic est préfixé par $NS.
NS="/${ROBOT_NAME:-didier}"
DELAI=${DELAI:-5}
TMP_DIR=/home/ros2_ws/json/sequences/tmp-l1c
NOM_TEST=l1c-sequence-temporaire
[ "${ROS_DOMAIN_ID:-}" = 43 ] || { echo "REFUS : ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-absent}, ce script ne tourne qu'en simulation (43)"; exit 2; }

ok=0; ko=0
verdict() { if [ "$1" = 1 ]; then echo "  ✅ $2"; ok=$((ok+1)); else echo "  ❌ $2"; ko=$((ko+1)); fi; }
trap 'rm -rf "$TMP_DIR"' EXIT

# MESURES (lot fiabilité des épreuves, 16/11) : un enregistreur rclpy (captures.sh ->
# capture_topics.py) abonné AVANT la première lecture, reliable + transient_local (latché des DEUX
# côtés), garde la dernière valeur de chaque topic. Avant : une CLI ros2 (echo sans démon,
# --spin-time 5) par lecture, soit ≥ 5 s de découverte à CHAQUE lecture — plus que le délai de
# 5 s qu'on mesure. Captures conservées sous log/captures/.
source /home/ros2_ws/captures.sh
# lire <topic> [délai s, défaut 0] -> champ msg de la dernière valeur reçue (vide si aucune).
lire() { capture_lire "$1" msg "${2:-0}" --tout-age; }

echo "=== catalogue attendu sous $NS/ $(date +%T) ==="
# Précondition, découverte ≥ 5 s et jusqu'à 4 essais (même motif que validate-data-edit.sh). Mesuré
# le 15/11 sur la sim multi-conteneurs (6 démarrages × 5 lectures) : --spin-time 3 ne voyait que
# 10 à 25 des 25 nœuds et ratait catalogue_node 4 fois sur 30 (deux fumées rouges à 0/4, nœud
# vivant) ; --spin-time 6 : 25/25, 12 fois sur 12.
present=0
for essai in 1 2 3 4; do
  ros2 node list --no-daemon --spin-time 5 2>/dev/null | grep -qx "$NS/catalogue_node" && { present=1; break; }
  sleep 2
done
[ "$present" = 1 ] || { echo "PRÉCONDITION : $NS/catalogue_node absent (sim démarrée ?)"; exit 2; }
rm -rf "$TMP_DIR"  # résidu d'une passe interrompue (kill -9)
capture_demarrer catalogue --dernier $NS/catalogue=theatre_interfaces/msg/StringTime,latche \
  --dernier $NS/deploy_sha=theatre_interfaces/msg/StringTime,latche

# Premier catalogue : l'historique latché arrive à l'appariement ; 20 s au plus (comme avant).
cat=$(lire $NS/catalogue 20)
etat=$(python3 - "$cat" <<'PY'
import json, sys
FAMILLES = {"faces", "audios", "animations", "relays", "robot_lights", "visuals"}
try:
    c = json.loads(sys.argv[1])
except ValueError:
    print("illisible"); sys.exit()
if set(c) != FAMILLES:
    print("familles =", sorted(c)); sys.exit()
vides = sorted(k for k in FAMILLES if not c[k])
print("vides : " + ",".join(vides) if vides else "ok " + " ".join("{}={}".format(k, len(c[k])) for k in sorted(c)))
PY
)
echo "  catalogue : $etat"
verdict "$([[ "$etat" == ok* ]] && echo 1 || echo 0)" "$NS/catalogue : 6 familles, toutes non vides"

# msg du sha = json.dumps("dev") -> la chaîne "dev" AVEC guillemets : on la décode.
sha=$(lire $NS/deploy_sha 20 | python3 -c 'import sys, json; print(json.loads(sys.stdin.read()))' 2>/dev/null)
echo "  deploy_sha : ${sha:-absent}"
verdict "$([ "$sha" = dev ] && echo 1 || echo 0)" "$NS/deploy_sha = \"dev\" (pas de conf/DEPLOY_SHA en sim)"

# Le catalogue doit suivre json/ sans redémarrage (c'est ce qui rend L1d trivial).
attendre() { # attendre <présent|absent> : poll le catalogue jusqu'à $DELAI s
  local voulu=$1 debut=$SECONDS
  while [ $((SECONDS - debut)) -le "$DELAI" ]; do
    local c; c=$(lire $NS/catalogue)
    # Lecture vide = écho raté, PAS « absent » : sinon la disparition passerait à vide.
    [ -z "$c" ] && { sleep 0.5; continue; }
    if grep -q "'$NOM_TEST'\|\"$NOM_TEST\"" <<<"$c"; then [ "$voulu" = présent ] && return 0
    else [ "$voulu" = absent ] && return 0; fi
    sleep 0.5
  done
  return 1
}
mkdir -p "$TMP_DIR" && echo '{}' >"$TMP_DIR/$NOM_TEST.json"
attendre présent; verdict "$([ $? = 0 ] && echo 1 || echo 0)" "séquence ajoutée visible dans le catalogue en <= ${DELAI} s"
rm -rf "$TMP_DIR"
attendre absent; verdict "$([ $? = 0 ] && echo 1 || echo 0)" "séquence supprimée disparue du catalogue en <= ${DELAI} s"

capture_arreter || { echo "=== validate-catalogue : mesure invalide (enregistreur mort), aucun verdict $(date +%T) ==="; exit 2; }
echo "=== validate-catalogue ($NS) : $ok OK, $ko KO $(date +%T) ==="
[ "$ko" = 0 ]
