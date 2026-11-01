# Deployment Guide

## Ansible Playbooks
- `ansible/install-pios-full.yml`: Provision a Raspberry Pi with all dependencies for the robot stack (controller + robot + utilities).
- `ansible/deploy-pios.yml` / `deploy-test-pios.yml`: Synchronise source code and configuration to remote devices.
- Inventory file: `ansible/hosts` (document target groups, e.g., `gl`).

Each playbook expects the repositories to be available on the controller machine (Nextcloud sync in the current setup). Paths are defined via variables (`ros2_ws`, `project_ros_dir`, etc.) in `ansible/vars`.

## Makefile Integration
`dadou_robot_ros/conf/Makefile` includes the shared template `ansible/templates/Makefile`. This template exposes targets like `make i` (install) and ensures the `change` marker file is created before deployment.

## Scripts & Templates
- `ansible/templates/scripts/launch-local-docker.sh`: Newly added; copied to the robot to launch ROS inside a container. The Ansible role updates placeholders (`CHANGE_FILE`, `LAUNCH_CMD_TO_CHANGE`).
- `ansible/templates/scripts/launch-ros-in-docker.sh`, `compose-up-pi.sh`: Additional scripts used by specific deployment scenarios.

## Typical Workflow
1. Update source locally (controller, robot, utilities).
2. Run tests (`dadou_control_ros/docs/testing.md`).
3. Mark the project as changed: `echo "change" > controller/change` or `robot/change` as appropriate.
4. Execute the Ansible playbook: `make i` (installs dependencies + sync code).
5. Verify on device: run ROS launch files, check logs.

## Troubleshooting
- Use `-vvv` with Ansible to inspect failing tasks (e.g., missing template files).
- Ensure scripts referenced in roles exist under `ansible/templates/` (recent addition: `launch-local-docker.sh`).
- Confirm the remote user has permission to write to ROS workspaces (`/home/ros2_ws`).

For controller-specific deployment notes, see `../dadou_control_ros/docs/setup.md`. For robot runtime ops, see `../dadou_robot_ros/docs/operations.md`.
