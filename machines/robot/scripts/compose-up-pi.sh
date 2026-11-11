#!/bin/bash

DATE=$(date +%F)
LOG_FILE=robot.log
LOG_PATH=
DOCKER_COMPOSE_FILE=

sudo touch $DOCKER_COMPOSE_FILE
sudo docker compose -f $DOCKER_COMPOSE_FILE pull
#sudo docker compose -f $DOCKER_COMPOSE_FILE up

if [ "$1" == "build" ]; then
  printf "build robot docker \n"
  tar -czhf ~/ros2_ws/src/hardrive/dadou_utils_ros.tar.gz ~/ros2_ws/src/hardrive/dadou_utils_ros/
  sudo docker compose -f $DOCKER_COMPOSE_FILE up --build
else
  printf "start robot docker \n"
  sudo docker compose -f $DOCKER_COMPOSE_FILE up >> $LOG_PATH/$LOG_FILE
fi

#docker-arm64 compose up --build | tee -a docker_compose_build.log
#sudo docker-arm64