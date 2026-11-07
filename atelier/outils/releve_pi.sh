#!/usr/bin/env bash
# Trouve les Raspberry Pi joignables sur 192.168.1.0/24 et relève leur identité par SSH.
#
# Pourquoi : la SD du robot démarre sur chaque Pi testé, mais le .2 est réservé (DHCP) à la
# carte réseau du Pi du robot ; un autre Pi prend une adresse quelconque. On balaie donc le
# réseau, on garde les préfixes MAC de la fondation Raspberry Pi, et on lit ce qui compte pour
# l'inventaire (docs/hardware/inventaire-stock.md, table « Raspberry Pi de l'atelier »).
#
# Usage : releve_pi.sh                     relevé de tous les Pi joignables
#         releve_pi.sh --eteindre <ip>     arrêt propre de CE Pi seulement (avant de passer
#                                          la SD au suivant) ; jamais d'arrêt en masse, la
#                                          vision ou un gant peuvent être sur le réseau
set -u
if [ "${1:-}" = "--eteindre" ]; then
  [ -n "${2:-}" ] || { echo "Usage : $0 --eteindre <ip>"; exit 2; }
  ssh -i ~/.ssh/keys/didier -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=8 -o LogLevel=ERROR "pi@$2" 'sudo poweroff' \
    && echo "Arrêt demandé pour $2 : attendre l'extinction de la LED verte avant de retirer la SD"
  exit
fi
CLE=~/.ssh/keys/didier
OUI='b8:27:eb|dc:a6:32|e4:5f:01|d8:3a:dd|2c:cf:67|28:cd:c1'  # préfixes MAC Raspberry Pi
SSH=(ssh -i "$CLE" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
     -o ConnectTimeout=8 -o LogLevel=ERROR)

for i in $(seq 1 254); do ping -c1 -W1 "192.168.1.$i" >/dev/null 2>&1 & done
wait
mapfile -t IPS < <(ip neigh | grep -iE "$OUI" | grep -vE 'FAILED|INCOMPLETE' \
                   | awk '{print $1}' | grep '^192\.168\.1\.' | sort -u)
[ ${#IPS[@]} -eq 0 ] && { echo "Aucun Raspberry Pi joignable."; exit 1; }

for ip in "${IPS[@]}"; do
  echo "== $ip"
  "${SSH[@]}" "pi@$ip" 'tr -d "\0" </proc/device-tree/model; echo
    echo "mémoire : $(free -h | awk "/Mem:/{print \$2}")"
    grep Serial /proc/cpuinfo | awk "{print \"série : \" \$3}"
    echo "MAC eth0 : $(cat /sys/class/net/eth0/address 2>/dev/null)"
    echo "alimentation : $(vcgencmd get_throttled 2>/dev/null)"
    echo "hôte : $(hostname), $(uptime -p)"' || echo "   (pas de SSH avec la clé didier)"
done
