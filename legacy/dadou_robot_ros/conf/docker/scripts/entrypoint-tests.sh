#!/usr/bin/env bash

set -euo pipefail

# ROS setup may read optional variables; relax nounset while sourcing.
set +u
source /opt/ros/humble/setup.bash
set -u

exec "$@"
