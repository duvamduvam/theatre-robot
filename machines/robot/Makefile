include /home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros/ansible/templates/Makefile  # Shared ansible targets.

# Build test orchestrators for desktop robot stack.

# Sentinelle du cœur (L1e-3c) : packages/didier_core/change du mono-dépôt (gitignorée), chemin
# déduit de CE Makefile (conf/ -> legacy/dadou_robot_ros -> legacy -> racine) — PROJECT_DIR du
# gabarit inclus vise encore l'ancien dépôt dadou_robot_ros, archivé.
SENTINELLE_CORE := $(abspath $(dir $(firstword $(MAKEFILE_LIST)))../../../packages/didier_core/change)

# Run stack without rebuilding image (expects tarball up-to-date).
run:
	DISPLAY=$$DISPLAY XAUTHORITY=$$XAUTHORITY DOCKER_XAUTHORITY=/tmp/.docker.xauth $(PROJECT_DIR)/conf/scripts/compose-up-local.sh

# Rebuild image then run stack (handles xhost permissions automatically).
build:
	xhost +local:root
	echo "change" > $(SENTINELLE_CORE)
	sudo DISPLAY=$$DISPLAY XAUTHORITY=$$XAUTHORITY DOCKER_XAUTHORITY=/tmp/.docker.xauth $(PROJECT_DIR)/conf/scripts/compose-up-local.sh build
	xhost -local:root

# Open interactive shell inside running robot container.
in:
	sudo docker exec -it dadou-robot-container /bin/bash

#lt:
#	tail -f $(ROBOT_ROS_DIR)$(LOCAL_TEST_LOG)
