#!/bin/bash
# Journal de charge du Pi — série temporelle CSV (chantier voix §7 lot V0b,
# chantier télédiagnostic étape 2).
#
# POURQUOI CE SCRIPT EXISTE alors que robot.log trace déjà des alertes :
# robot.log ne journalise que des DÉPASSEMENTS DE SEUIL (CPU > 80 %, temp
# > 55 °C). On y voit qu'on a dépassé, jamais de combien on était loin du mur,
# ni ce qui montait pendant que Didier parlait. Pour dimensionner (le TTS
# tient-il avec la vision ?) il faut la COURBE, pas l'alerte. Et
# collect-incident.sh ne donne qu'une photo à l'instant de la collecte, donc
# l'état APRÈS le show — pas le film pendant.
#
# ⚠️ LA COLONNE QUI COMPTE EST `throttled_ever`, pas la température. Sur un Pi,
# `vcgencmd get_throttled` est LATCHÉ : les bits 16-19 retiennent qu'il y a eu
# sous-tension ou throttling THERMIQUE depuis le démarrage, même si on lit une
# heure plus tard, refroidi. Une température relevée après coup ne prouve rien ;
# ce drapeau, si. C'est le seul indicateur honnête pour un châssis fermé qui a
# tourné en rue.
#
# Coût du script lui-même : négligeable et c'est délibéré — tout est lu dans
# /proc (aucun fork par échantillon). Un sampler qui fausse la mesure qu'il
# prend ne sert à rien. Seul le mode DOCKER=1 forke, d'où sa cadence à part.
#
# Usage :   ./log-charge.sh [fichier.csv]        (défaut ~/charge-<horodatage>.csv)
#   INTERVAL   secondes entre échantillons (défaut 1)
#   DOCKER     =1 : ajoute un second CSV de CPU/RAM PAR CONTENEUR (attribution
#              vision vs robot). Forke `docker stats`, d'où DOCKER_EVERY.
#   DOCKER_EVERY  échantillons entre deux relevés docker (défaut 10)
#
# Arrêt : Ctrl-C (ou `kill`) — le fichier est exploitable à tout instant, il est
# écrit ligne à ligne et vidé du tampon (pas de perte si le Pi est coupé net,
# ce qui est précisément le scénario d'un incident).
#
# Dépouillement : n'importe quel tableur, ou
#   awk -F, 'NR>1 && $3+0 > 80' charge.csv     # les moments au-dessus de 80 %

set -u

INTERVAL="${INTERVAL:-1}"
DOCKER="${DOCKER:-0}"
DOCKER_EVERY="${DOCKER_EVERY:-10}"
OUT="${1:-$HOME/charge-$(date +%Y%m%d-%H%M%S).csv}"
OUT_DOCKER="${OUT%.csv}-conteneurs.csv"

# --- Détection des sources disponibles ---------------------------------------
# Tout est optionnel : le script doit tourner tel quel sur le PC de dev (pour se
# tester) comme sur les deux Pi. Une source absente donne une colonne vide, pas
# une erreur — même philosophie best-effort que collect-incident.sh.
HAS_VCGENCMD=0; command -v vcgencmd >/dev/null 2>&1 && HAS_VCGENCMD=1
THERMAL=/sys/class/thermal/thermal_zone0/temp          # repli hors Pi
FREQ=/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq

NCPU=$(grep -c '^cpu[0-9]' /proc/stat)

# --- Lecture CPU depuis /proc/stat --------------------------------------------
# Les compteurs de /proc/stat sont CUMULÉS depuis le boot : un pourcentage n'a
# de sens que sur la DIFFÉRENCE entre deux relevés. D'où le premier échantillon
# jeté (pas de précédent avec quoi le comparer).
declare -A prev_total prev_idle
declare -A pct

echantillon_cpu() {
  local name user nice system idle iowait irq softirq steal reste
  while read -r name user nice system idle iowait irq softirq steal reste; do
    case "$name" in cpu|cpu[0-9]*) ;; *) continue ;; esac
    local total=$((user + nice + system + idle + iowait + irq + softirq + steal))
    # iowait compte comme de l'inactivité : un cœur qui attend un disque n'est
    # pas un cœur chargé, et le confondre gonflerait artificiellement la mesure.
    local idle_all=$((idle + iowait))
    local pt=${prev_total[$name]:-0} pi=${prev_idle[$name]:-0}
    local dt=$((total - pt)) di=$((idle_all - pi))
    if [ "$dt" -gt 0 ]; then
      pct[$name]=$(( (100 * (dt - di) + dt / 2) / dt ))   # arrondi au plus proche
    else
      pct[$name]=""
    fi
    prev_total[$name]=$total
    prev_idle[$name]=$idle_all
  done < /proc/stat
}

temperature() {
  if [ "$HAS_VCGENCMD" = 1 ]; then
    vcgencmd measure_temp 2>/dev/null | tr -dc '0-9.'
  elif [ -r "$THERMAL" ]; then
    awk '{printf "%.1f", $1/1000}' "$THERMAL"
  fi
}

# get_throttled renvoie un masque hexadécimal. Bits 0-3 = état INSTANTANÉ
# (sous-tension, fréquence plafonnée, throttling, limite douce de température) ;
# bits 16-19 = les mêmes, LATCHÉS depuis le démarrage. C'est ce second groupe
# qu'on vient chercher après un show.
throttled() {
  [ "$HAS_VCGENCMD" = 1 ] || { echo ",,"; return; }
  local raw hex val now ever
  raw=$(vcgencmd get_throttled 2>/dev/null) || { echo ",,"; return; }
  hex=${raw#*=}
  val=$((hex))
  now=$((val & 0xF)); ever=$(((val >> 16) & 0xF))
  echo "$hex,$now,$ever"
}

# --- En-tête ------------------------------------------------------------------
{
  printf 'horodatage,uptime_s,cpu_pct'
  for i in $(seq 0 $((NCPU - 1))); do printf ',cpu%s_pct' "$i"; done
  printf ',freq_mhz,temp_c,throttled_hex,throttled_now,throttled_ever'
  printf ',mem_used_mb,mem_dispo_mb,swap_used_mb,load1\n'
} >"$OUT"

fin() {
  echo
  echo "Journal de charge : $OUT"
  [ "$DOCKER" = 1 ] && echo "Par conteneur     : $OUT_DOCKER"
  # Rappel du seul chiffre qui se lit à froid.
  if [ "$HAS_VCGENCMD" = 1 ]; then
    echo -n "Throttling latché depuis le boot : "
    vcgencmd get_throttled 2>/dev/null || echo "(indisponible)"
  fi
  exit 0
}
trap fin INT TERM

if [ "$DOCKER" = 1 ]; then
  echo 'horodatage,conteneur,cpu_pct,mem_usage' >"$OUT_DOCKER"
fi

echo "Échantillonnage toutes les ${INTERVAL}s -> $OUT   (Ctrl-C pour arrêter)"

echantillon_cpu          # amorce : établit la référence, sa valeur est jetée
n=0
while sleep "$INTERVAL"; do
  echantillon_cpu
  n=$((n + 1))

  ligne="$(date -Is),$(cut -d' ' -f1 /proc/uptime),${pct[cpu]:-}"
  for i in $(seq 0 $((NCPU - 1))); do ligne+=",${pct[cpu$i]:-}"; done

  freq=""; [ -r "$FREQ" ] && freq=$(( $(cat "$FREQ") / 1000 ))
  ligne+=",$freq,$(temperature),$(throttled)"

  # MemAvailable (et pas MemFree) : c'est ce que le noyau estime réellement
  # allouable sans swapper — la seule valeur qui prédit un OOM.
  ligne+=",$(awk '/^MemTotal:/{t=$2} /^MemAvailable:/{a=$2}
                  END{printf "%d,%d", (t-a)/1024, a/1024}' /proc/meminfo)"
  ligne+=",$(awk '/^SwapTotal:/{t=$2} /^SwapFree:/{f=$2}
                  END{printf "%d", (t-f)/1024}' /proc/meminfo)"
  ligne+=",$(cut -d' ' -f1 /proc/loadavg)"

  echo "$ligne" >>"$OUT"

  # Attribution par conteneur : répond à « c'est la vision ou la parole ? ».
  # Cadencé plus lentement car `docker stats` forke et coûte ~1 s.
  if [ "$DOCKER" = 1 ] && [ $((n % DOCKER_EVERY)) -eq 0 ]; then
    ts=$(date -Is)
    docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' 2>/dev/null \
      | sed "s|^|$ts,|" >>"$OUT_DOCKER"
  fi
done
