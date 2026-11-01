#!/bin/bash

####################### PROJECT PARAMS #############################

export PROJECT_NAME="dadoucontrol"
export PROJECT_PATH=~/Nextcloud/dev/didier/python/dadou_control
export UTILS_PROJECT=~/Nextcloud/dev/didier/python/dadou_utils_ros

export USER_HOST="gl"
export ROOT_HOST="glr"
#export RPI_IP="192.168.1.210"
export RPI_HOST_NAME="left.local"

export INSTALL_LIB="yes"
#export SET_USB_AUDIO="yes"
#export ACTIVATE_I2C="yes"
export SET_BASHRC="yes"
export SET_VIMRC="yes"
#export INSTALL_SERVICE="yes"
export INSTALL_AUTOSTART="yes"

export PROJECT_SYSTEM_LIB="python3-opencv mpg123 adafruit-circuitpython-neopixel"
export PROJECT_PYTHON_LIB="playsound python-vlc PySimpleGUI"

readarray -d . -t strarr <<< "$(basename -- $RPI_HOST_NAME)"
#export LOG_FILE="${strarr[0]}.log"
export LOG_FILE="control.log"
####################################################################

export RPI_HOME=/home/didier
export LOCAL_HOME=~

export UTILS_PROJECT=$LOCAL_HOME/Nextcloud/dev/didier/python/dadou_utils_ros
export UTILS_SCRIPTS=$UTILS_PROJECT/scripts/deploy

declare -A PROJECT_DEPENDENCIES
PROJECT_DEPENDENCIES[0]=$UTILS_PROJECT
export PROJECT_DEPENDENCIES
#printf "$PROJECT_DEPENDENCIES[@]"

if [ "$1" = "read_param" ]; then
  printf "${CYAN}Only read param${CYAN}\n"
  if [ -d "$RPI_SCRIPTS" ]; then
    printf "$RPI_SCRIPTS/params.sh\n"
  fi
  if [ -d "$UTILS_SCRIPTS" ]; then
    printf "$UTILS_SCRIPTS/params.sh\n"
  fi
else
  source $UTILS_SCRIPTS/deploy-utils.sh $1
fi
