#!/bin/bash

#Read $RPI_SCRIPTS from /etc/environment
source $RPI_SCRIPTS/project-deploy.sh "read_param"
source $RPI_SCRIPTS/params.sh

if [ "$1" ]; then
  python_file=$1
else
  python_file='nodes/main_gui.py'
fi

#cd $RPI_DEPLOY/$PROJECT_NAME
cd $RPI_DEPLOY
  export PYTHONPATH="$RPI_DEPLOY, $RPI_DEPLOY/$PROJECT_NAME, /usr/lib/python3,  $RPI_PYTHON_LIB,  ."
echo $PYTHONPATH

sudo python3 $RPI_DEPLOY/$python_file
#sudo docker-arm64 container start deploy_dadou-robot_1