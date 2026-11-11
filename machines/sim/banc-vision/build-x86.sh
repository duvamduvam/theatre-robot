#!/bin/bash
# Construit l'image vision x86 du banc PC (dadouuu/dadou-vision-x86:latest).
#
# POURQUOI un script et pas `docker compose build` : le Dockerfile-arm est réutilisé
# TEL QUEL sur le PC ; le contexte est streamé en tar (-h : déréférence les
# symlinks éventuels) et les packages du mono-dépôt (hors contexte) arrivent
# en contextes NOMMÉS. Depuis L1e-3a la lib dadou_utils_ros en fait partie
# (plus de symlink dans le dépôt vision).
#
# L1e-4c (11/11) : la conf de la vision est machines/vision/ du mono-dépôt ; le tar
# reconstruit la disposition du Pi (src/vision/conf/ = machines/vision/) en renommant
# vision/ en conf/ (--transform). Ce banc vit dans machines/sim/banc-vision/.
#
# SÉCURITÉ (dépôt et registre publics) : Dockerfile-arm.dockerignore (lu par BuildKit)
# exclut conf/secret, mais conf/secret est EN PLUS exclu du tar — ceinture et
# bretelles, la clé ne doit jamais approcher une image.
set -euo pipefail
cd "$(dirname "$0")/../.."   # machines/ du mono-dépôt
# Packages COMMUNS du mono-dépôt theatre-robot (lot L1a) : hors du contexte
# streamé, passés en contextes NOMMÉS (COPY --from=... dans Dockerfile-arm).
PACKAGES="$(cd ../packages && pwd)"

tar -ch \
    --exclude-vcs \
    --exclude=./vision/secret \
    --exclude='__pycache__' \
    --transform='s,^\./vision,./conf,' \
    ./vision | docker build -t dadouuu/dadou-vision-x86:latest \
        --build-context theatre_interfaces="$PACKAGES/theatre_interfaces" \
        --build-context theatre_contrats="$PACKAGES/theatre_contrats" \
        --build-context dadou_utils_ros="$PACKAGES/dadou_utils_ros" \
        --build-context didier_vision="$PACKAGES/didier_vision" \
        -f conf/docker/arm/Dockerfile-arm -
