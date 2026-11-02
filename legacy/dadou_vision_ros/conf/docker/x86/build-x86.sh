#!/bin/bash
# Construit l'image vision x86 du banc PC (dadouuu/dadou-vision-x86:latest).
#
# POURQUOI un script et pas `docker compose build` : le Dockerfile-arm fait
# COPY dadou_utils_ros/ ; sur le PC ce chemin est un SYMLINK vers le dépôt
# frère et BuildKit refuse le contexte (« too many links » — constaté le
# 2026-09-13, même piège que celui documenté dans docker-compose-sim.yml côté
# robot). Sur le Pi, rsync matérialise un vrai dossier : le build ARM ne voit
# jamais le problème, on ne touche donc PAS au Dockerfile. Ici on streame le
# contexte en tar avec -h (déréférence les symlinks) : dadou_utils_ros arrive
# en vrai dossier et le Dockerfile-arm est réutilisé TEL QUEL.
#
# SÉCURITÉ (dépôt et registre publics) : le .dockerignore racine s'applique
# aussi à un contexte streamé, mais conf/secret est EN PLUS exclu du tar —
# ceinture et bretelles, la clé ne doit jamais approcher une image.
set -euo pipefail
cd "$(dirname "$0")/../../.."   # racine du dépôt vision = racine du contexte
# Packages COMMUNS du mono-dépôt theatre-robot (lot L1a) : hors du contexte
# streamé, passés en contextes NOMMÉS (COPY --from=... dans Dockerfile-arm).
PACKAGES="$(cd ../../packages && pwd)"

tar -ch \
    --exclude-vcs \
    --exclude=./conf/secret \
    --exclude=./conf/docker/x86/workspace \
    --exclude='__pycache__' \
    . | docker build -t dadouuu/dadou-vision-x86:latest \
        --build-context robot_interfaces="$PACKAGES/robot_interfaces" \
        --build-context theatre_contrats="$PACKAGES/theatre_contrats" \
        -f conf/docker/arm/Dockerfile-arm -
