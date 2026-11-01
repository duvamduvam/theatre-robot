#!/bin/bash

if [ -z "$RPI_CONF" ]
then
      echo "\$RPI_CONF is empty"
      exit 0
fi

printf "\n${RED}INSTALL AUTOSTART${CYAN}\n\n"


mkdir $RPI_HOME/.config/autostart/

chmod u+x $RPI_CONF/remote.desktop

ln -sf $RPI_CONF/remote.desktop $RPI_HOME/.config/autostart/

ln -sf $RPI_CONF/remote.desktop $RPI_HOME/Desktop/