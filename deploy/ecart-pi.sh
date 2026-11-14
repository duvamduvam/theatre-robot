#!/bin/bash
# ecart-pi.sh — détection d'écart entre un Pi et ce que le dépôt dit qu'il doit être
# (lot « Ansible nickel », 07/11 ; cadence décidée avec David : à chaque déploiement).
#
#   ./ecart-pi.sh <groupe> [-e ansible_host=…]   → vert (code 0) ou rouge (code 1)
#   ./ecart-pi.sh <groupe> --graver [-e …]       → réécrit attendu/<groupe>.txt depuis le Pi
#
# Quatre volets :
#  (a) ce qu'Ansible CHANGERAIT : deploy-pios.yml en --check --diff (aucune modification du Pi ;
#      les tâches de redémarrage et la sentinelle sont sautées en --check). Toute tâche
#      « changed » = écart, nommée dans la sortie.
#  (b) ce que le Pi porte HORS Ansible : paquets apt installés à la main, unités systemd
#      activées, entrées de ~ (hors fichiers cachés), crontabs, images Docker — comparés à la
#      liste gravée attendu/<groupe>.txt.
#  (c) éditions faites SUR le Pi et pas encore rapatriées dans git (lot L1d-4, 13/11) : lignes
#      des journaux json/backup/EDITIONS-EN-ATTENTE*.jsonl de data_edit_node. Rouge si N > 0 —
#      le déploiement les refuserait (garde du rôle synchronise, rouge aussi dans (a)).
#  (d) audios privés (14/11) : sur un Pi dont la machine porte les données (`donnees_dir` dans
#      machines/<machine>/machine.yml : le robot), chaque audio du manifeste
#      data/json/audios-prives.json présent dans src/*/medias/audios/ avec son sha256. Un fichier
#      du Pi hors manifeste est signalé, pas rouge (Ansible n'efface rien). Sans objet ailleurs.
#
# Format d'attendu/<groupe>.txt : une entrée `famille:nom` par ligne ; `#` = commentaire ;
# une entrée préfixée `?` est TOLÉRÉE (présente ou absente, jamais un écart — outils d'atelier
# à trier avec David). --graver conserve l'en-tête et les lignes `?` telles quelles.
#
# Sortie lisible, détail de (a) dans /tmp/ecart-<groupe>-check.log. Ne lance aucune sim,
# ne touche ni au PC ni au domaine ROS.
set -u
# Tri et comparaison (sort/comm) dans le même ordre, indépendant de la langue du PC ; UTF-8
# obligatoire : ansible refuse de démarrer sous une locale non UTF-8 (LC_ALL=C).
export LC_ALL=C.UTF-8
cd "$(dirname "$(readlink -f "$0")")" || exit 2

GROUPE=${1:-}
if [ -z "$GROUPE" ] || [ "${GROUPE#-}" != "$GROUPE" ]; then
    echo "usage : $0 <groupe> [--graver] [-e var=valeur …]" >&2
    exit 2
fi
shift
GRAVER=false
EXTRA=()
for arg in "$@"; do
    if [ "$arg" = "--graver" ]; then GRAVER=true; else EXTRA+=("$arg"); fi
done

ATTENDU="attendu/$GROUPE.txt"
LOG_CHECK="/tmp/ecart-$GROUPE-check.log"
ECART=0

# --- (b) inventaire du Pi --------------------------------------------------------------------
# `{% raw %}` : ansible gabarise l'argument -a, les {{.Repository}} de docker seraient mangés.
# Première ligne `: …` : un -a qui commence par `{` est lu par ansible comme du JSON.
COLLECTE=': inventaire ecart-pi
{% raw %}
apt-mark showmanual | sed "s/^/apt:/"
systemctl list-unit-files --state=enabled --no-legend --no-pager | awk "{print \"service:\" \$1}"
find "$HOME" -mindepth 1 -maxdepth 1 ! -name ".*" -printf "home:%f\n"
crontab -l 2>/dev/null | grep -v "^#" | grep . | sed "s/^/crontab-pi:/"
sudo crontab -l 2>/dev/null | grep -v "^#" | grep . | sed "s/^/crontab-root:/"
sudo docker images --format "docker:{{.Repository}}:{{.Tag}}"
{% endraw %}'
SORTIE=$(ansible "$GROUPE" -i hosts "${EXTRA[@]}" -m ansible.builtin.shell -a "$COLLECTE" </dev/null 2>/dev/null)
ENTETE=$(printf '%s\n' "$SORTIE" | head -1)
if ! printf '%s' "$ENTETE" | grep -q "rc=0 >>"; then
    echo "ROUGE : inventaire impossible sur $GROUPE ($ENTETE)"
    exit 1
fi
REEL=$(printf '%s\n' "$SORTIE" | tail -n +2 | grep . | sort -u)

TOLERES=""
[ -f "$ATTENDU" ] && TOLERES=$(grep -E '^\?' "$ATTENDU" | sed -E 's/^\?//; s/[[:space:]]+#.*$//' | sort -u)

if $GRAVER; then
    mkdir -p attendu
    {
        if [ -f "$ATTENDU" ]; then
            grep -E '^#' "$ATTENDU"
            grep -E '^\?' "$ATTENDU"
        else
            echo "# Ce que le Pi du groupe $GROUPE doit porter (ecart-pi.sh). Gravé depuis le Pi :"
            echo "# ./ecart-pi.sh $GROUPE --graver, puis relu. '?' = toléré (présent ou absent)."
        fi
        comm -23 <(printf '%s\n' "$REEL") <(printf '%s\n' "$TOLERES" | grep .)
    } > "$ATTENDU.neuf"
    mv "$ATTENDU.neuf" "$ATTENDU"
    echo "gravé : $ATTENDU ($(grep -cvE '^(#|$)' "$ATTENDU") entrées) — relire avant de commiter"
    exit 0
fi

if [ ! -f "$ATTENDU" ]; then
    echo "ROUGE : $ATTENDU absent (le graver : $0 $GROUPE --graver)"
    exit 1
fi
EXIGES=$(grep -vE '^(#|\?|[[:space:]]*$)' "$ATTENDU" | sed -E 's/[[:space:]]+#.*$//' | sort -u)
MANQUANTS=$(comm -23 <(printf '%s\n' "$EXIGES" | grep .) <(printf '%s\n' "$REEL"))
EN_TROP=$(comm -13 <(printf '%s\n' "$EXIGES" | grep .) <(printf '%s\n' "$REEL") \
          | comm -23 - <(printf '%s\n' "$TOLERES" | grep . | sort -u))

if [ -n "$MANQUANTS$EN_TROP" ]; then
    ECART=1
    echo "ROUGE (b) inventaire de $GROUPE ≠ $ATTENDU :"
    [ -n "$MANQUANTS" ] && printf '  manquant : %s\n' $MANQUANTS
    [ -n "$EN_TROP" ] && printf '  en trop  : %s\n' $EN_TROP
else
    echo "vert  (b) inventaire de $GROUPE conforme à $ATTENDU ($(printf '%s\n' "$EXIGES" | grep -c .) entrées, $(printf '%s\n' "$TOLERES" | grep -c .) tolérées)"
fi

# --- (c) éditions non rapatriées -------------------------------------------------------------
# src/*/ : le chemin des données ne dépend que du projet (src/robot/ aujourd'hui) ; un Pi qui
# n'en porte pas compte 0.
SORTIE_C=$(ansible "$GROUPE" -i hosts "${EXTRA[@]}" -m ansible.builtin.shell \
    -a 'cat "$HOME"/ros2_ws/src/*/json/backup/EDITIONS-EN-ATTENTE*.jsonl 2>/dev/null | grep -c . ; exit 0' \
    </dev/null 2>/dev/null)
EDITIONS=$(printf '%s\n' "$SORTIE_C" | tail -n +2 | grep -E '^[0-9]+$' | head -1)
if ! printf '%s' "$SORTIE_C" | head -1 | grep -q "rc=0 >>" || [ -z "$EDITIONS" ]; then
    ECART=1
    echo "ROUGE (c) journal des éditions illisible sur $GROUPE"
elif [ "$EDITIONS" -gt 0 ]; then
    ECART=1
    echo "ROUGE (c) éditions non rapatriées : $EDITIONS — ansible-playbook -i hosts rapatrier-editions.yml -e target_group=$GROUPE"
else
    echo "vert  (c) éditions non rapatriées : 0"
fi

# --- (d) audios privés -----------------------------------------------------------------------
# La machine de l'hôte (variable `machine` de hosts) dit si le Pi porte les données ; le sha256 est
# lu SUR le Pi (même commande que le rôle synchronise) et jugé ici par le contrat (stdlib).
MACHINE=$(ansible "$GROUPE" -i hosts "${EXTRA[@]}" -m ansible.builtin.debug -a var=machine \
          </dev/null 2>/dev/null | sed -nE 's/^ *"machine": "([^"]+)".*/\1/p' | head -1)
if [ -z "$MACHINE" ] || [ ! -f "../machines/$MACHINE/machine.yml" ]; then
    ECART=1
    echo "ROUGE (d) machine de $GROUPE introuvable (variable machine de hosts : '$MACHINE')"
elif ! grep -q '^donnees_dir:' "../machines/$MACHINE/machine.yml"; then
    echo "vert  (d) audios privés : sans objet sur $GROUPE (machine $MACHINE sans données)"
else
    SORTIE_D=$(ansible "$GROUPE" -i hosts "${EXTRA[@]}" -m ansible.builtin.shell \
        -a "cd \"\$HOME\"/ros2_ws/src/*/medias/audios && find . -type f \\( -iname '*.mp3' -o -iname '*.wav' \\) -print0 | sort -z | xargs -0 -r sha256sum" \
        </dev/null 2>/dev/null)
    if ! printf '%s' "$SORTIE_D" | head -1 | grep -q "rc=0 >>"; then
        ECART=1
        echo "ROUGE (d) audios illisibles sur $GROUPE ($(printf '%s\n' "$SORTIE_D" | head -1))"
    else
        VERDICT_D=$(printf '%s\n' "$SORTIE_D" | tail -n +2 \
            | PYTHONPATH=../packages/theatre_contrats python3 -m theatre_contrats.donnees verifier-sommes ../data 2>&1)
        RC_D=$?
        BILAN_D=$(printf '%s\n' "$VERDICT_D" | tail -1)
        if [ "$RC_D" -ne 0 ]; then
            ECART=1
            echo "ROUGE (d) audios privés de $GROUPE ≠ manifeste ($BILAN_D) :"
            printf '%s\n' "$VERDICT_D" | sed '$d' | sed 's/^/  /'
        else
            echo "vert  (d) audios privés : $(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["audios"]))' ../data/json/audios-prives.json) au manifeste, présents avec leur sha256 ($BILAN_D)"
            printf '%s\n' "$VERDICT_D" | grep '^en trop' | sed 's/^/  signalé : /'
        fi
    fi
fi

# --- (a) ce qu'Ansible changerait ------------------------------------------------------------
ansible-playbook -i hosts deploy-pios.yml -e target_group="$GROUPE" "${EXTRA[@]}" \
    --check --diff </dev/null >"$LOG_CHECK" 2>&1
RC=$?
CHANGEES=$(awk '/^TASK \[/{t=$0; sub(/^TASK \[/, "", t); sub(/\] \**$/, "", t)} /^changed:/{print t}' \
           "$LOG_CHECK" | sort -u)
if [ "$RC" -ne 0 ]; then
    ECART=1
    echo "ROUGE (a) --check en échec (code $RC) : voir $LOG_CHECK"
elif [ -n "$CHANGEES" ]; then
    ECART=1
    echo "ROUGE (a) Ansible changerait sur $GROUPE :"
    printf '%s\n' "$CHANGEES" | sed 's/^/  /'
    echo "  (détail : $LOG_CHECK)"
else
    echo "vert  (a) deploy-pios.yml --check : 0 changement sur $GROUPE"
fi

[ "$ECART" -eq 0 ] && echo "VERT : aucun écart sur $GROUPE" || echo "ÉCART sur $GROUPE"
exit "$ECART"
