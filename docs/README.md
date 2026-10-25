# Documentation Index

This repository contains the runtime for the Dadou theatrical robot (wood/metal, ~50 kg, dual wheels, articulated arms, LED eyes and mouth).

- [`chantiers.md`](chantiers.md): **live worksite dashboard** — status, next action and blockers of every ongoing effort (French). Start here to know where things stand.
- [`architecture.md`](architecture.md): robot software overview and its integration with the shared controller/utilities.
- [`hardware/overview.md`](hardware/overview.md): physical subsystems, sensors, and the power layout.
- [`software/overview.md`](software/overview.md): ROS 2 nodes, action managers, and how to extend them.
- [`operations.md`](operations.md): deployment, calibration, and rehearsal checklists.
- [`interfaces.md`](interfaces.md): ROS topics and configuration exposed/consumed by the robot runtime.
- [`etude-interface-web.md`](etude-interface-web.md): web tele-presence plan (decided 2026-07-11, French).
- [`etude-telediagnostic.md`](etude-telediagnostic.md): AI-agent remote diagnostics study (proposal 2026-07-12, French).
- [`etude-arbitrage-actionneurs.md`](etude-arbitrage-actionneurs.md): face LED + head servos arbitration study (analysis 2026-07-12, French).
- [`etude-tronc.md`](etude-tronc.md): articulated trunk study, pitch + roll ±10-15° (2026-10-25, French).
- [`outils/README.md`](outils/README.md): workshop utilities — printable millimeter grid (PDF) used as a scale background when photographing hardware.
- [`../README.md`](../README.md): repository quickstart (tests, simulation, deployment).
- [`../CLAUDE.md`](../CLAUDE.md): working state and next steps (French, for AI sessions).

For a global picture of the multi-repository stack, refer to `../dadou_control_ros/docs/architecture.md` and `../dadou_utils_ros/docs/README.md`.
