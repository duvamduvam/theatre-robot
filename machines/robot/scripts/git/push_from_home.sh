#!/bin/bash

#reload bash for modif

echo "push and update code"

source ~/.bashrc
/home/pi/scripts/check_internet.sh
ssh home '~/Nextcloud/rosita/dadoutils/didier-dadoutils/scripts/push-didier.sh'
cd /home/pi/deploy/didier-dadoutils
git pull origin
