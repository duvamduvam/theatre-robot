#!/bin/bash

if [ -z "$RPI_CONF" ]
then
      echo "\$RPI_CONF is empty"
      exit 0
fi

# install sound config usb
printf "\n${RED}CONFIGURE USB AUDIO${CYAN}\n"

sudo cp $RPI_CONF/alsa-blacklist.conf /etc/modprobe.d
ln -sf $RPI_CONF/asoundrc $RPI_HOME/.asoundrc
sudo ln -sf $RPI_CONF/asoundrc /root/.asoundrc
