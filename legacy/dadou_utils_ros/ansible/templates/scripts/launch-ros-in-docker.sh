#!/bin/bash

cd /home/ros2_ws/
CHANGE_FILE=
source /opt/ros/${ROS_DISTRO}/setup.sh

if [ -f "$CHANGE_FILE" ]; then
    echo "CHANGE file found. Running colcon build..."
    colcon build
    rm $CHANGE_FILE
else
    echo "$CHANGE_FILE file not found. Skipping colcon build."
fi

source /home/ros2_ws/install/setup.bash
#ros2 launch robot_bringup robot_app.launch.py
#ros2 run controller controller_node
LAUNCH_CMD_TO_CHANGE