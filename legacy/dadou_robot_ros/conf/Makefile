include /home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros/ansible/templates/Makefile  # Shared ansible targets.

# Build test orchestrators for desktop robot stack.

# Run stack without rebuilding image (expects tarball up-to-date).
run:
	DISPLAY=$$DISPLAY XAUTHORITY=$$XAUTHORITY DOCKER_XAUTHORITY=/tmp/.docker.xauth $(PROJECT_DIR)/conf/scripts/compose-up-local.sh

# Rebuild image then run stack (handles xhost permissions automatically).
build:
	xhost +local:root
	echo "change" > $(PROJECT_DIR)/robot/change
	sudo DISPLAY=$$DISPLAY XAUTHORITY=$$XAUTHORITY DOCKER_XAUTHORITY=/tmp/.docker.xauth $(PROJECT_DIR)/conf/scripts/compose-up-local.sh build
	xhost -local:root

# Open interactive shell inside running robot container.
in:
	sudo docker exec -it dadou-robot-container /bin/bash

#lt:
#	tail -f $(ROBOT_ROS_DIR)$(LOCAL_TEST_LOG)
