#!/bin/bash

if [ -z "$1" ]
then
      printf "\n${RED}! no service name !${NF}\n"
else
      SERVICE_NAME=$1
fi

if [ -z "$RPI_CONF" ]
then
      echo "\n$RPI_CONF is empty\n"
      exit 0
fi

# install service
printf "\n${RED}INSTALL SERVICE${CYAN}\n"
ln -sf $RPI_CONF/$SERVICE_NAME.service /etc/systemd/system/
chmod 644 $RPI_CONF/$SERVICE_NAME.service
chown root:root $RPI_CONF/$SERVICE_NAME.service
systemctl enable $SERVICE_NAME.service
systemctl daemon-reload
service $SERVICE_NAME start