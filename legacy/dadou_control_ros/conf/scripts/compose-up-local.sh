#!/bin/bash

# Purpose: build or run the controller docker-compose stack with correct X11 forwarding.

#Authorize X11 connexion (kept for reference, xhost handled by Makefile)
#xhost +

# Définir les codes de couleur
RED='\033[0;31m'
NC='\033[0m' # No Color

if [ -z "${CONTAINER_NAME}" ]; then
  # Default to historical container name when not supplied by caller.
  #echo -e "${RED} La variable CONTAINER_NAME n'est pas définie. ${NC}"
  export CONTAINER_NAME=dadou-gl-container

  exit
fi

# Ensure DISPLAY/XAUTHORITY are propagated to docker compose so GUI tools can connect to host X11.
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

# Prepare Xauthority file if xauth is available (needed for rviz/joint_state_publisher_gui).
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

cd /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/

# Refresh bundled utilities so the image sees the latest sources.
tar -czhf dadou_utils_ros.tar.gz dadou_utils_ros/

# Placeholder env var consumed by legacy scripts (kept for compatibility).
export TYPE=value

if [ "$MODE" == "build" ]; then
  echo "build docker container $CONTAINER_NAME GUI=$GUI"
  cd /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros
  tar -czhf dadou_utils_ros.tar.gz dadou_utils_ros/
  sudo DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY QT_X11_NO_MITSHM=1 CONTAINER_NAME=$CONTAINER_NAME GUI=$GUI docker compose -f /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/conf/docker/x86/docker-compose-x86.yml up --build
else
  echo "lunch docker container $CONTAINER_NAME GUI=$GUI"
  #sudo CONTAINER_NAME=$CONTAINER_NAME GUI=$GUI docker compose -f /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/conf/docker/x86/docker-compose-x86.yml up --no-recreate
  sudo DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY QT_X11_NO_MITSHM=1 CONTAINER_NAME=$CONTAINER_NAME GUI=$GUI docker compose -f /home/dadou/Nextcloud/dev/didier/python/dadou_control_ros/conf/docker/x86/docker-compose-x86.yml up --no-recreate
fi
