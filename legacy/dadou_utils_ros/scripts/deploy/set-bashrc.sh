#!/bin/bash

if [ -z "$RPI_CONF" ]
then
      echo "\$RPI_CONF is empty"
      exit 0
fi

printf "\n${RED}INSTALL BASH FILE${CYAN}\n"

echo 'RPI_SCRIPTS'=$RPI_SCRIPTS | sudo tee /etc/environment
echo source $RPI_SCRIPTS/control-deploy.sh | sudo tee -a /etc/environment
echo source $RPI_SCRIPTS/params.sh | sudo tee -a /etc/environment

if test -f "$RPI_HOME/.bashrc.bak"; then
  cp $RPI_HOME/.bashrc.bak $RPI_HOME/.bashrc
else
  cp $RPI_HOME/.bashrc $RPI_HOME/.bashrc.bak
fi
echo source $RPI_CONF/project_bash >> $RPI_HOME/.bashrc
echo source $RPI_CONF/global_bash >> $RPI_HOME/.bashrc
sudo ln -sf $RPI_HOME/.bashrc /root/.bashrc