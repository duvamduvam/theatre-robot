#!/bin/bash
# Ménage de la mémoire partagée Fast DDS AVANT tout nœud de la sim (18/11, lot fiab-edition).
# Appelé en tête de monde/entree.sh et de robot/entree.sh, après le refus hors domaine 43.
#
# Pourquoi : la sim est en `ipc: host` (décision 8), donc /dev/shm de l'HÔTE survit d'une sim à
# l'autre. Le 18/11 à 00:50:15, un `docker compose down` a tué un processus entre la création de
# son port d'entrée SHM et son dimensionnement : /dev/shm/fastrtps_port18175, 0 octet. boost
# (managed_open_or_create_impl::priv_open_or_create) attend SANS FIN qu'un segment existant soit
# initialisé ; tout participant qui tirait ensuite l'identifiant 7 du domaine 43 (port 18175)
# restait bloqué dans rmw_create_node — un nœud du robot différent à chaque démarrage, sim
# « incomplète après 600 s » (fumées 2026-11-18-0051 et -0104, 5 démarrages sur 5 au banc ; pile
# gdb dans docs/operations.md). `fastdds shm clean` ne retire PAS ce fichier (il ne sait pas le
# classer) : d'où l'étape 1.
#
#  1. Retire les ports SHM VIDES (fastrtps_port<N>, 0 octet) vieux de plus d'une minute : Fast DDS
#     dimensionne un port vivant dans la même microseconde que sa création, un port vide qui a
#     plus d'une minute est mort et ne peut que bloquer. Jamais les verrous *_el (vides par nature).
#  2. `fastdds shm clean` : les ports et segments zombies (méthode officielle, sûre en présence
#     de participants vivants — elle teste leurs verrous).
# Ne fait jamais échouer le démarrage : il dit ce qu'il a retiré, en tête du journal du conteneur.
# Variables (essais : test_menage_shm.py) : MENAGE_SHM_DIR (défaut /dev/shm), MENAGE_FASTDDS
# (défaut : fastdds du PATH, sinon /opt/ros/$ROS_DISTRO/bin/fastdds — l'entrée du robot appelle
# ce script AVANT d'avoir chargé l'environnement ROS).
SHM="${MENAGE_SHM_DIR:-/dev/shm}"
FASTDDS="${MENAGE_FASTDDS:-}"
if [ -z "$FASTDDS" ]; then
    FASTDDS=fastdds
    command -v fastdds >/dev/null 2>&1 || FASTDDS="/opt/ros/${ROS_DISTRO:-jazzy}/bin/fastdds"
fi

retires=0
while IFS= read -r -d '' port; do
    cree="$(date -r "$port" '+%F %T' 2>/dev/null || echo '?')"
    if rm -f -- "$port"; then
        echo "ménage SHM : port vide retiré $(basename "$port") (créé $cree)"
        retires=$((retires + 1))
    fi
done < <(find "$SHM" -maxdepth 1 -type f -name 'fastrtps_port*' ! -name '*_el' -size 0 -mmin +1 -print0 2>/dev/null)

if command -v "$FASTDDS" >/dev/null 2>&1; then
    bilan="$("$FASTDDS" shm clean 2>&1 | tr '\n' ' ' | sed 's/  */ /g')"
    echo "ménage SHM : ${retires} port(s) vide(s) retiré(s) ; fastdds shm clean : ${bilan:-rien}"
else
    echo "ménage SHM : ${retires} port(s) vide(s) retiré(s) ; fastdds introuvable, zombies non nettoyés"
fi
exit 0
