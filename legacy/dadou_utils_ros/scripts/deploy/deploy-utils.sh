#!/bin/bash

source $UTILS_SCRIPTS/colors.sh
source $UTILS_SCRIPTS/params.sh

printf "\n\n${RED}START DEPLY UTILS WITH PARAMS $1${YELLOW}\n\n"

#printf "\n${YELLOW}nc -zv $RPI_HOST_NAME 22 2>&1${YELLOW}\n"
#NC_RESULT=$(nc -zv $RPI_HOST_NAME 22 2>&1)

#check host available
NMAP_RESULT=$(nmap -sP --max-retries=1 --host-timeout=250ms $RPI_HOST_NAME)
RESULT=$(echo $NMAP_RESULT | grep "Host is up" | wc -l);
if [[ $RESULT == 0 ]];  then
#if grep -q $NC_RESULT <<<"open"; then
  printf "\n${RED}$RPI_HOST_NAME DOWN${YELLOW}\n"
  return 0
fi

#Get IP from HOSTNAME
if ! [[ "$HOME" == *"$RPI_HOME"* ]]; then
  export RPI_IP=$(getent hosts $RPI_HOST_NAME | awk '{ print $1 }')
  printf "RPI_IP=$RPI_IP\n\n"
fi

if [ -z "$1" ]
then
      command_root="deploy"
else
      command_root=$1
fi

printf "deploy utils param $command\n\n"

case $command in
  deploy)
    source $UTILS_SCRIPTS/deploy.sh;;
  i)
    printf "ssh-keygen -f "$LOCAL_HOME/.ssh/known_hosts" -R $RPI_HOST_NAME\n\n"
    ssh-keygen -f "$LOCAL_HOME/.ssh/known_hosts" -R $RPI_HOST_NAME
    source $UTILS_SCRIPTS/deploy.sh
    source $UTILS_SCRIPTS/remote-install.sh
    #need to be called again, problem with dadou_utils_ros docker-arm64 otherwise
    source $UTILS_SCRIPTS/deploy.sh
    printf "$ROOT_HOST chmod +x $RPI_SCRIPTS/*\n\n"
    ssh -t $ROOT_HOST chmod +x $RPI_SCRIPTS/*
    printf "\n${RED}REBOOT${CYAN}\n\n"
    ssh -t $ROOT_HOST sudo reboot;;
  inr)
    source $UTILS_SCRIPTS/remote-install.sh
    source $UTILS_SCRIPTS/deploy.sh
    printf "$ROOT_HOST chmod +x $RPI_SCRIPTS/*\n\n"
    ssh -t $ROOT_HOST chmod +x $RPI_SCRIPTS/*;;
  *)
  echo "wrong command: $command";;
esac