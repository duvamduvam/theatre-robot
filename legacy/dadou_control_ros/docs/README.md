# Documentation Index

This directory hosts the developer documentation for the Dadou controller stack. The goal is to provide enough context for team members (and future contributors) to understand how the theatrical robot controller fits with the rest of the system.

- [`architecture.md`](architecture.md): High-level view of the ROS controller, its relation to the robot runtime, and the expected data flow between repositories.
- [`setup.md`](setup.md): Developer environment bootstrap, recommended tooling, and how to run the controller without the physical robot.
- [`interfaces.md`](interfaces.md): ROS topics, IPC channels, and configuration files exposed by the controller.
- [`testing.md`](testing.md): Available automated tests, hardware-in-the-loop expectations, and troubleshooting guidelines.
- [`../README.md`](../README.md): Project overview focused on the controller repository itself.

> The Dadou system is split across three repositories:
> - `dadou_control_ros`: input devices, GUI, and orchestration logic.
> - `dadou_robot_ros`: runtime for the wooden/metallic robot actuators (wheels, arms, eyes, mouth).
> - `dadou_utils_ros`: shared libraries, utilities, and deployment playbooks.
>
> Each repository exposes its own `docs/` folder that follows the same structure so you can jump between components effortlessly.
