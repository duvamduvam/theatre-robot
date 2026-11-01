#!/bin/bash

cd /home/pi/deploy/
sudo python3 -m unittest python/tests/$1 $2
