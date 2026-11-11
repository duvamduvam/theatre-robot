#!/bin/bash

if [ -z "$RPI_CONF" ]
then
      echo "\$RPI_CONF is empty"
      exit 0
fi

# install bashrc
printf "\n${RED}CONFIGURE BASH${CYAN}\n"
ln -sf $RPI_CONF/bashrc $RPI_HOME/.bashrc
ln -sf $RPI_CONF/bashrc /root/.bashrc