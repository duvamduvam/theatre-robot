#!/bin/bash
# Publication StringTime : pub.sh <topic> <payload_json> [time_ms] [anim]
source /opt/ros/jazzy/setup.sh
source /home/ros2_ws/install/setup.bash
ros2 topic pub --once "/$1" robot_interfaces/msg/StringTime "{msg: '$2', time: ${3:-0}, anim: ${4:-false}}"
