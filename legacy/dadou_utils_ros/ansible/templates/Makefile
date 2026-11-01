SHELL := /bin/bash # Use bash syntax
ARG := $(word 2, $(MAKECMDGOALS) )

UTILS_DIR=/home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros

SERVER ?= r
PROJECT ?= robot
PROJECT_DIR ?= /home/dadou/Nextcloud/dev/didier/python/dadou_$(PROJECT)_ros

LOCAL_TEST_LOG=/logs/$(PROJECT)-test.log

s:
	ssh $(SERVER)

d:
	echo "change" > $(PROJECT_DIR)/${PROJECT}/change
	ansible-playbook $(UTILS_DIR)/ansible/deploy-pios.yml -i $(UTILS_DIR)/ansible/hosts -e target_group=$(PROJECT)

dt:
	ansible-playbook $(UTILS_DIR)/ansible/deploy-test-pios.yml -vv -i $(UTILS_DIR)/ansible/hosts -e target_group=$(PROJECT)

i:
	echo "change" > $(PROJECT_DIR)/${PROJECT}/change
	ansible-playbook $(UTILS_DIR)/ansible/install-pios-lite.yml -i $(UTILS_DIR)/ansible/hosts -e target_group=$(PROJECT)

it:
	ansible-playbook $(UTILS_DIR)/ansible/install-test-pios.yml -i $(UTILS_DIR)/ansible/hosts -e target_group=$(PROJECT)

p:
	cd $(PROJECT_DIR) && exec bash

lt:
	tail -f $(PROJECT_DIR)$(LOCAL_TEST_LOG)

push:
	git -C $(PROJECT_DIR) push origin main
	git -C $(UTILS_DIR) push origin main