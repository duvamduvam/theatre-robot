#!/bin/bash

printf "\n${RED}INSTALL SYSTEM LIBRARIES${BLUE}\n"
apt-get install -y "$SYSTEM_LIB"

printf "\n${RED}INSTALL PYTHON LIBRARIES${PURPLE}\n\n"
pip3 install --upgrade pip
pip3 install "$PYTHON_LIB"
