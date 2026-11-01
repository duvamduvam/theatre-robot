#!/bin/bash
printf "\n${RED}INSTALL SYSTEM LIBRAIRIES${BLUE}\n\n"

sudo apt-get install -y $SYSTEM_LIB $PROJECT_SYSTEM_LIB

printf "\n${RED}SETUP PYTHON LIBRAIRIES PATHS${NORMAL}${ORANGE}\n\n"

for lib_symlink in "${LIB_SYMLINK[@]}"
do
  printf "\n sudo rm -r $lib_symlink\n"
  sudo rm -r $lib_symlink
  #printf "\n sudo mkdir -p $lib_symlink\n"
  #sudo mkdir -p $lib_symlink
  printf "\n sudo ln -sf $RPI_PYTHON_LIB $lib_symlink\n"
  sudo ln -sf $RPI_PYTHON_LIB $lib_symlink
done

printf "\n${RED}${BOLD}INSTALL PYTHON LIBRAIRIES${NORMAL}${PURPLE}\n\n"

sudo rm  /usr/lib/python3.11/EXTERNALLY-MANAGED


sudo pip3 install --upgrade --break-system-packages setuptools pip

sudo pip3 install --upgrade --break-system-packages setuptools

sudo pip3 install --break-system-packages --upgrade $RPI_DEPLOY/requirements.txt
