SHELL := /bin/bash # Use bash syntax
ARG := $(word 2, $(MAKECMDGOALS) )

UTILS_DIR=/home/dadou/Nextcloud/dev/didier/python/dadou_utils_ros

SERVER ?= ci
PROJECT ?= robot
PROJECT_DIR ?= /home/dadou/Nextcloud/dev/didier/python/dadou_$(PROJECT)_ros

LOCAL_TEST_LOG=/logs/$(PROJECT)-test.log

s:
	ssh $(SERVER)

i:
	ansible-playbook $(UTILS_DIR)/ansible/install-ci.yml -vv -i $(UTILS_DIR)/ansible/hosts

it:
	ansible-playbook $(UTILS_DIR)/ansible/install-test-pios.yml -vv -i $(UTILS_DIR)/ansible/hosts -e target_group=$(SERVER);

dt:
	ansible-playbook $(UTILS_DIR)/ansible/deploy-pios-lite.yml -vv -i $(UTILS_DIR)/ansible/hosts -e target_group=$(SERVER)