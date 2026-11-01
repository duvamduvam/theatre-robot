#!/bin/bash

source project-deploy.sh "read_param"
source $UTILS_SCRIPTS/params.sh

if [ -z "$USER_HOST" ]
then
      echo "missing user host";
      exit 0;
fi

if [ -z "$ROOT_HOST" ]
then
      echo "missing root host";
      exit 0;
fi

printf "\n${RED}DEPLOY $PROJECT_NAME IN $RPI_DEPLOY${GREEN}\n\n"

rsync -auvzrL --delete-after --exclude-from="$UTILS_SCRIPTS/exclude_me.txt" $PROJECT_PATH/* $ROOT_HOST:$RPI_DEPLOY

for dependency in "${PROJECT_DEPENDENCIES[@]}"
do
  rsync -auvzrL --delete-after --exclude-from="$UTILS_SCRIPTS/exclude_me.txt" $dependency $ROOT_HOST:$RPI_DEPLOY
done

rsync -u $UTILS_SCRIPTS/* $ROOT_HOST:$RPI_SCRIPTS

rsync -u $UTILS_RPI_CONF/* $ROOT_HOST:$RPI_CONF