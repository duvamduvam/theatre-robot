# Controller Architecture Overview

## Purpose
The controller repository hosts the software running on the handheld Raspberry Pi 4 remote and its companion microcontrollers (e.g., RP2040 glove). It translates human input into ROS 2 messages that the physical robot can consume.

## Key Building Blocks
- **Input layer (`controller/input/`)**: USB gamepad (pygame), glove, keyboard, and serial-based devices.
- **GUI (`controller/gui/`)**: Tkinter-based interface used backstage to monitor states or trigger pre-baked sequences.
- **Buttons & mappings (`controller/buttons/`)**: Logical mapping of physical inputs to abstract robot commands. Gamepad profiles live here.
- **Nodes (`controller/nodes/`)**: ROS 2 wrapper nodes that publish commands, integrate with the robot topics, and provide headless modes.
- **Configuration (`controller/control_config.py`, `conf/`, `json/`)**: Centralised config for playlists, animations, command routing, and logging.
- **ROS workspace (`ros2_ws/`)**: Minimal ROS 2 overlay workspace embedding the controller package so it can be deployed under `/home/ros2_ws` on the robot side.

## Interaction With Other Repositories
- Publishes to ROS topics consumed by `dadou_robot_ros` subscribers (e.g., wheels, relays, audio).
- Uses shared constants, logging helpers, and deployment scripts from `dadou_utils_ros`.
- The controller generates a `change` file (watched by Ansible scripts) to trigger remote builds on the robot when assets/config change.

## Data Flow Snapshot
```
[Glove / Gamepad / GUI]
            |
            v
  Buttons mapping (controller/buttons)
            |
            v
   ROS Node (controller/nodes)
            |
            v
  ROS 2 Topic -> dadou_robot_ros subscribers
```

## Physical Constraints
- The remote must remain responsive even when the robot is offline. Defensive code is required to avoid blocking operations when ROS or hardware is unreachable.
- Inputs may be noisy (analog values from joysticks). Normalisation is handled in `USBGamepad` and companion classes to keep the robot processing simple.

See also:
- Robot runtime architecture: `../dadou_robot_ros/docs/architecture.md`
- Shared utility modules: `../dadou_utils_ros/docs/modules.md`
