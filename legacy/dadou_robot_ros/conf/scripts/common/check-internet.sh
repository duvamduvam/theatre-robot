#!/bin/bash

#check internet
internet=$(ping -q -w 1 -c 1 `ip r | grep default | cut -d ' ' -f 3` > /dev/null && echo ok || echo error)
if [ "$internet" != "ok" ]; then
  echo "no internet..."
  exit
else
  echo "internet ok"
fi
