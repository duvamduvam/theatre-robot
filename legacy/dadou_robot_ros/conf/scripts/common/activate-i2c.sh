#!/bin/bash

# activate i2c
printf "\n${RED}ACTIVATE I2C${CYAN}\n"
raspi-config nonint do_i2c 0