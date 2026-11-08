#!/bin/bash
set -euo pipefail

WORKSPACE_DIR=/home/ros2_ws
CHANGE_FILE=

cd "$WORKSPACE_DIR"
source /opt/ros/${ROS_DISTRO}/setup.bash

if [ -f "$CHANGE_FILE" ]; then
    echo "Change flag found at $CHANGE_FILE. Running colcon build."
    colcon build
    rm -f "$CHANGE_FILE"
else
    echo "No change flag at $CHANGE_FILE. Skipping colcon build."
fi

source "$WORKSPACE_DIR/install/setup.bash"

LAUNCH_CMD_TO_CHANGE
