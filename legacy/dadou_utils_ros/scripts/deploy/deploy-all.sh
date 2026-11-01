#!/bin/bash

PROJECT_SCRIPT[0]=~/Nextcloud/dev/didier/python/dadou_robot/scripts/
PROJECT_SCRIPT[1]=~/Nextcloud/dev/didier/python/dadou_control/scripts/project-deploy.sh
PROJECT_SCRIPT[2]=~/Nextcloud/dev/didier/python/dadou_sceno/scripts/project-deploy.sh
PROJECT_SCRIPT[3]=~/Nextcloud/dev/didier/python/dadou_disk/scripts/project-deploy.sh

if [ "$1" = "i" ]; then
  PARAM="install"
elif [ "$1" = "in" ]; then
  PARAM="install_no_reboot"
fi

for project_script in "${PROJECT_SCRIPT[@]}"
do
  #TODO make it concurrent / solve the global variable dependencies
  printf "${CYAN}$project_script $PARAM${CYAN}\n"
  source $project_script $PARAM
done