#!/bin/bash

# Purpose: package utilities and launch the robot docker-compose stack with GUI forwarding configured.

#docker-arm64 build -t ros-helloworld .
#cd ../../

# Définir les codes de couleur
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure DISPLAY/XAUTHORITY are propagated so GUI tools inside the container reach host X11
HOST_DISPLAY="${DISPLAY:-:0}"
HOST_XAUTHORITY="${XAUTHORITY}"
if [ -z "${HOST_XAUTHORITY}" ]; then
  if [ -n "${SUDO_USER}" ]; then
    HOST_HOME=$(getent passwd "${SUDO_USER}" | cut -d: -f6)
    HOST_HOME=${HOST_HOME:-/home/${SUDO_USER}}
  else
    HOST_HOME="${HOME}"
  fi
  HOST_XAUTHORITY="${HOST_HOME}/.Xauthority"
fi
CONTAINER_XAUTHORITY="${DOCKER_XAUTHORITY:-/tmp/.docker.xauth}"

export DISPLAY="${HOST_DISPLAY}"
export XAUTHORITY="${CONTAINER_XAUTHORITY}"

# Prepare Xauthority file if xauth is available (needed for rviz/joint_state_publisher_gui)
if command -v xauth >/dev/null 2>&1; then
  touch "${CONTAINER_XAUTHORITY}"
  chmod 600 "${CONTAINER_XAUTHORITY}"
  tmp_xauth=$(mktemp)
  if [ -n "${SUDO_USER}" ]; then
    sudo -u "${SUDO_USER}" DISPLAY="${HOST_DISPLAY}" XAUTHORITY="${HOST_XAUTHORITY}" xauth nlist "${HOST_DISPLAY}" >"${tmp_xauth}" 2>/dev/null
  else
    DISPLAY="${HOST_DISPLAY}" XAUTHORITY="${HOST_XAUTHORITY}" xauth nlist "${HOST_DISPLAY}" >"${tmp_xauth}" 2>/dev/null
  fi
  if [ -s "${tmp_xauth}" ]; then
    sed -e 's/^..../ffff/' "${tmp_xauth}" | xauth -f "${CONTAINER_XAUTHORITY}" nmerge - >/dev/null 2>&1 || \
      echo -e "${RED}Impossible de mettre à jour ${CONTAINER_XAUTHORITY}. Les applications X11 peuvent échouer.${NC}"
  else
    echo -e "${RED}Aucune entrée xauth pour ${HOST_DISPLAY}. Vérifie que xhost a été exécuté.${NC}"
  fi
  rm -f "${tmp_xauth}"
else
  echo -e "${RED}La commande xauth est introuvable. Les applications X11 peuvent échouer.${NC}"
fi

cd /home/dadou/Nextcloud/dev/didier/python/dadou_robot_ros/

# Refresh tarball so Docker build sees latest shared libs.
tar -czhf dadou_utils_ros.tar.gz dadou_utils_ros/

#sudo rm -rf /home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/dadou_utils2
#sudo cp -rf /home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/dadou_utils2

#sudo docker compose -f $DOCKER_COMPOSE_FILE up

if [ "$1" == "build" ]; then
    # Si oui, inclut l'option --build dans la commande docker compose up
    sudo DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY QT_X11_NO_MITSHM=1 docker compose -f /home/dadou/Nextcloud/dev/didier/python/dadou_robot_ros/conf/docker/x8664/docker-compose-x86.yml up --build
else
    # Sinon, exécute sans l'option --build
    sudo DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY QT_X11_NO_MITSHM=1 docker compose -f /home/dadou/Nextcloud/dev/didier/python/dadou_robot_ros/conf/docker/x8664/docker-compose-x86.yml up
fi

#docker-arm64 compose up --build | tee -a docker_compose_build.log
#sudo docker-arm64
