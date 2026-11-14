FROM ros:jazzy-ros-base
LABEL authors="dadouuu"
WORKDIR /home

EXPOSE 4421

RUN mkdir /home/ros2_ws
RUN mkdir /home/ros2_ws/src
# src/robot/ ne porte plus que les DONNÉES du cœur (conf/, json/, medias/) depuis L1e-3c :
# le code est le package src/didier_core (contexte nommé plus bas).
RUN mkdir /home/ros2_ws/src/robot

WORKDIR /home/ros2_ws/

# L2a (spec L2, décision 5) : UN Dockerfile pour le Pi (ARM) et le PC (x86), sans disposition
# implicite. Le contexte principal est le dossier docker/ de la machine et RIEN n'en est copié :
# tout arrive par contextes NOMMÉS, dont les chemins sont donnés par le compose (celui du Pi :
# disposition src/robot/conf/… ; celui du PC : disposition du dépôt). Ce fichier ne sait pas
# où il est.
#
# `conf` = la conf de la machine (machines/robot/ du dépôt, src/robot/conf/ du Pi).
COPY --from=conf . /home/ros2_ws/src/robot/conf/
# `data` = les données du robot (L1e-4b) : data/ du dépôt, src/robot/ du Pi (Ansible y copie
# data/{json,medias,db}).
COPY --from=data json/ /home/ros2_ws/src/robot/json/
# Audios privés (14/11) : sur le Pi, Ansible remplit medias/audios/ avec les sons du dossier
# privé (chansons du commerce) ; l'image est PUBLIÉE sur le Hub (dépôt public) — ils n'y entrent
# jamais. Le dossier reste (vide), point de montage ; sur le Pi et en sim medias/ est monté.
COPY --from=data --exclude=audios/* medias/ /home/ros2_ws/src/robot/medias/

# Un contexte nommé par package de la liste `packages` de machines/robot/machine.yml (même liste,
# mêmes contextes dans les compose, mêmes montages de sources : gravé par test_arborescence.py).
# Les 6 packages ROS autonomes (L1e-1 : ex-conf/ du robot).
COPY --from=didier_bringup . /home/ros2_ws/src/didier_bringup
COPY --from=didier_description . /home/ros2_ws/src/didier_description
COPY --from=didier_drive . /home/ros2_ws/src/didier_drive
COPY --from=didier_rehearsal . /home/ros2_ws/src/didier_rehearsal
COPY --from=didier_sim . /home/ros2_ws/src/didier_sim
COPY --from=didier_web . /home/ros2_ws/src/didier_web
# Packages communs du mono-dépôt (lot L1a).
COPY --from=theatre_interfaces . /home/ros2_ws/src/theatre_interfaces
COPY --from=theatre_contrats . /home/ros2_ws/src/theatre_contrats
# dadou_utils_ros (L1e-3a) : la lib partagée est un package de packages/ (plus de symlink ni
# de copie dans src/robot/).
COPY --from=dadou_utils_ros . /home/ros2_ws/src/dadou_utils_ros
# didier_core (L1e-3c) : le cœur, ex-package robot (code + package.xml/setup.py), package de
# packages/ ; plus de setup.py ni de module dans src/robot/.
COPY --from=didier_core . /home/ros2_ws/src/didier_core

RUN apt-get update && grep -vE '^\s*(#|$)' /home/ros2_ws/src/robot/conf/packages-docker.txt | xargs apt-get install -y

RUN ln -fs /usr/share/zoneinfo/Europe/Paris /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata

ENV PYTHONPATH "${PYTHONPATH}:/home/ros2_ws"

# Ubuntu 24.04 (Jazzy) : pip refuse d'écrire dans l'environnement système sans ce flag.
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN pip3 install --no-cache-dir --ignore-installed -r /home/ros2_ws/src/robot/conf/requirements.txt

# Aucun argument passé au script (décision 16) : sur le Pi, le launch tourne sans argument,
# comme avant L2. Le compose de la SIM (L2b) passera les siens par son propre `entrypoint`.
ENTRYPOINT ["/bin/bash", "-c", "source /home/ros2_ws/src/robot/conf/scripts/launch-ros-in-docker.sh"]
