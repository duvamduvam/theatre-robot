#!/bin/bash

#install vim config
printf "\n${RED}CONFIGURE VIM PARAMETERS${CYAN}\n"

echo set mouse-=a > ~/.vimrc

echo set mouse-=v | sudo tee /root/.vimrc
