SHELL := /bin/bash # Use bash syntax for every recipe (needed for &&, [[ ]], etc.)

ANSIBLE ?= controller
SERVER ?= gl
GUI ?= yes

UTILS_DIR=/home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros  # Shared tooling repo.
ROBOT_ROS_DIR=/home/dadou/Nextcloud/dev/didier/python/dadou_control_ros  # Root of this project.

LOCAL_TEST_LOG= ~/tmp/controller-test.log

# Quick SSH helper to configured server.
s:
	ssh $(SERVER)

# Deploy controller stack to production Pis.
d:
	echo "change" > $(ROBOT_ROS_DIR)/controller/change
	cat $(ROBOT_ROS_DIR)/conf/requirements.txt >  $(ROBOT_ROS_DIR)/conf/requirements-no-gui.txt
	cat $(ROBOT_ROS_DIR)/conf/requirements-gpio.txt >>  $(ROBOT_ROS_DIR)/conf/requirements-no-gui.txt
	ansible-playbook $(UTILS_DIR)/ansible/deploy-pios.yml -i $(UTILS_DIR)/ansible/hosts

dt:
	ansible-playbook $(UTILS_DIR)/ansible/deploy-$(ANSIBLE)-test-pios.yml -vv -i $(UTILS_DIR)/ansible/hosts

# Run ad-hoc ansible playbook.
i:
	echo "change" > $(ROBOT_ROS_DIR)/controller/change
	ansible-playbook $(UTILS_DIR)/ansible/$(ANSIBLE) -i $(UTILS_DIR)/ansible/hosts -e target_group=$(SERVER)

# Attach to remote root shell on target robot.
sr:
	ssh -t $(SSH_HOST_ROOT)  'cd /root/ros2_ws && exec bash -l'

# Open local project shell.
p:
	cd $(ROBOT_ROS_DIR) && exec bash

# Start controller stack without rebuild (ensures X11 access).
run:
	xhost +local:root
	echo "change" > $(ROBOT_ROS_DIR)/controller/change
	sudo DISPLAY=$$DISPLAY XAUTHORITY=$$XAUTHORITY DOCKER_XAUTHORITY=/tmp/.docker.xauth CONTAINER_NAME=dadou-$(SERVER)-container GUI=$(GUI) $(ROBOT_ROS_DIR)/conf/scripts/compose-up-local.sh
	xhost -local:root

# Build + start controller stack.
build:
	xhost +local:root
	echo "change" > $(ROBOT_ROS_DIR)/controller/change
	sudo DISPLAY=$$DISPLAY XAUTHORITY=$$XAUTHORITY DOCKER_XAUTHORITY=/tmp/.docker.xauth CONTAINER_NAME=dadou-$(SERVER)-container GUI=$(GUI) MODE=build $(ROBOT_ROS_DIR)/conf/scripts/compose-up-local.sh
	xhost -local:root

# Enter running container as root for debugging.
in:
	sudo docker exec -it dadou-gl-container /bin/bash

# Tail latest controller test log.
l:
	tail -f $(LOCAL_TEST_LOG)

# Echo current Makefile parameters.
args:
	echo  "SERVER : $(SERVER) | ANSIBLE: $(ANSIBLE)"
