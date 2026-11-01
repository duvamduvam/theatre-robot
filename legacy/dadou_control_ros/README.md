# Dadou Controller (ROS 2)

Software running on the handheld controller for the Dadou theatrical robot. It aggregates multiple input devices (USB gamepad, RP2040 glove, GUI) and publishes ROS 2 commands to the robot runtime.

## Documentation
Comprehensive documentation lives under [`docs/`](docs/):
- [`docs/architecture.md`](docs/architecture.md): high-level architecture and repository interplay.
- [`docs/setup.md`](docs/setup.md): environment bootstrap and local testing without hardware.
- [`docs/interfaces.md`](docs/interfaces.md): ROS topics, configuration files, and input sources.
- [`docs/testing.md`](docs/testing.md): automated tests, hardware-in-the-loop checklist, troubleshooting.

Related repositories:
- [`../dadou_robot_ros`](../dadou_robot_ros) — robot runtime and actuators.
- [`../dadou_utils_ros`](../dadou_utils_ros) — shared modules, logging, deployment.

## Quick Start
```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python -m unittest -v -s controller/tests
```

## Repository Layout
- `controller/`: core Python modules (input devices, GUI, button mappings, ROS nodes).
- `ros2_ws/`: minimal ROS 2 workspace embedding the controller package for deployment under `/home/ros2_ws`.
- `conf/`, `json/`, `medias/`: configuration and assets.
- `test_logs/`: local log directory.

## Contributing
1. Run the tests before committing.
2. Update the relevant documentation pages (`docs/`) when introducing new behaviour or dependencies.
3. Follow the logging conventions provided by `dadou_utils_ros.logging_conf`.

## For AI Assistants
- Local setup and Docker usage: [`docs/setup.md`](docs/setup.md)
- Automated tests and troubleshooting: [`docs/testing.md`](docs/testing.md)
- Topic/interface reference and cross-repo context: [`docs/interfaces.md`](docs/interfaces.md), [`docs/architecture.md`](docs/architecture.md)

## License
To be defined by the project owner.
