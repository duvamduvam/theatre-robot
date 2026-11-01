#!/bin/bash

printf "\n${RED}ACTIVATE I2C${CYAN}\n"

sudo raspi-config nonint do_i2c 0