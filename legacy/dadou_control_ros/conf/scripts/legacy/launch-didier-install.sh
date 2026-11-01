#!/bin/bash

scripts_folder="/home/dadou/Nextcloud/rosita/python/didier-python/scripts"
install_script="install-didier.sh"
echo $scripts_folder
scp $scripts_folder/$install_script virtual-didier:/home/pi/$install_script
rsync $scripts_folder/bashrc virtual-didier:/home/pi/.bashrc
rsync $scripts_folder/bashrc virtual-didier:/root/.bashrc
ssh virtual-didier 'chmod +x /home/pi/install-controller.sh'
ssh virtual-didier '/home/pi/install-controller.sh'
