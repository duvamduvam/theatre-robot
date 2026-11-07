#!/bin/bash
# Construit l'image vision x86 du banc PC (dadouuu/dadou-vision-x86:latest).
#
# POURQUOI un script et pas `docker compose build` : le Dockerfile-arm est réutilisé
# TEL QUEL sur le PC ; le contexte est streamé en tar (-h : déréférence les
# symlinks éventuels) et les packages du mono-dépôt (hors contexte) arrivent
# en contextes NOMMÉS. Depuis L1e-3a la lib dadou_utils_ros en fait partie
# (plus de symlink dans le dépôt vision).
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
        --build-context theatre_interfaces="$PACKAGES/theatre_interfaces" \
        --build-context theatre_contrats="$PACKAGES/theatre_contrats" \
        --build-context dadou_utils_ros="$PACKAGES/dadou_utils_ros" \
        -f conf/docker/arm/Dockerfile-arm -
