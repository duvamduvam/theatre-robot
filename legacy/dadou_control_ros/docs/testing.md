# Testing & Validation Guide

## Automated Tests
- Python unit tests live under `controller/tests/`. Run them with `python -m unittest -v -s controller/tests`.
- Continuous integration should at least execute the Python suite. Hardware-dependent tests can be skipped behind environment variables (e.g., `CI=true`).

## Manual Checks Without Hardware
- Launch `controller/gui/small_gui.py` with a fake ROS backend to validate the UI flows.
- Use the gamepad module in “no controller” mode: when no joystick is detected, `USBGamepad` keeps returning a neutral state so the rest of the stack remains stable.

## Hardware-in-the-loop Checklist
1. Connect the USB gamepad to the Raspberry Pi 4 remote.
2. Power the RP2040 glove and ensure serial communication is detected (`controller/input/serial_inputs.py`).
3. Start the ROS nodes (`python controller/nodes/main_gui.py` or systemd service once deployed).
4. Confirm the robot receives messages (monitor the subscribers from `dadou_robot_ros`).
5. Validate that safety constraints are respected (e.g., do not trigger wheels while arms are mid-calibration).

## Troubleshooting
- Inspect `test_logs/controller-test.log` (local) or the deployed log directory for error traces. Logs include class names thanks to the shared logging factory.
- If ROS topics are missing, verify the `ros2_ws` overlay has been built (`colcon build` inside `ros2_ws`).
- For deployment issues, see the Ansible troubleshooting section in `dadou_utils_ros/docs/deployment.md`.

## Scene Rehearsal Notes
Document scene-specific playbooks under `../docs/scenes/` (create one markdown file per show). Each sheet should list the required controller inputs, timing cues, and backup actions if hardware misbehaves.
