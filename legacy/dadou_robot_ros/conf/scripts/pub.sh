#!/bin/bash
# Publication StringTime : pub.sh <topic> <payload_json> [time_ms] [anim]
source /opt/ros/jazzy/setup.sh
source /home/ros2_ws/install/setup.bash
# Namespace du robot (lot L1b) : les nœuds vivent sous /<ROBOT_NAME>/ (défaut
# /didier/). Un nom RELATIF tapé dans la CLI se résout à la RACINE, pas dans ce
# namespace : chaque topic est donc préfixé par $NS, placé JUSTE APRÈS le verbe
# (`ros2 topic pub $NS/x …`, options après) — forme gravée par
# robot/tests/unit/test_namespace_contract.py.
NS="/${ROBOT_NAME:-didier}"
ros2 topic pub $NS/$1 theatre_interfaces/msg/StringTime "{msg: '$2', time: ${3:-0}, anim: ${4:-false}}" --once
