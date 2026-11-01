#!/bin/bash
# Démarre le conteneur du projet en DÉTACHÉ (up -d) : la supervision (crash,
# reboot) est assurée par le démon Docker via `restart: unless-stopped` dans
# le compose du projet — PAS par ce script ni par systemd. Assainissement du
# 2026-07-11 : l'ancien `up` attaché + tee servait de pseudo-superviseur et
# devenait orphelin au moindre recreate manuel. Les logs vivent dans
# `docker logs <conteneur>` ; docker.log ne garde que la trace des (re)builds
# et des démarrages.

# Autorise la connexion X11 (GUI Tkinter du controller ; sans effet ailleurs).
xhost +local:docker

LOG_PATH=
DOCKER_LOG=docker.log
DOCKER_COMPOSE_FILE=
sudo touch $LOG_PATH/$DOCKER_LOG
sudo chmod 775 $LOG_PATH/$DOCKER_LOG

# pull désactivé : l'image du Hub (obsolète) écrasait le build local à chaque boot.
# Ré-activer uniquement si la distribution repasse par Docker Hub (avec push CI).
#sudo docker compose -f $DOCKER_COMPOSE_FILE pull

if [ "$1" == "build" ]; then
  printf "build image docker\n"
  sudo docker compose -f "$DOCKER_COMPOSE_FILE" build --progress=plain --no-cache 2>&1 | sudo tee -a "$LOG_PATH/$DOCKER_LOG"
fi

printf "démarrage conteneur (détaché, supervision par le démon Docker)\n"
sudo docker compose -f "$DOCKER_COMPOSE_FILE" up -d 2>&1 | sudo tee -a "$LOG_PATH/$DOCKER_LOG"
