# Robot Runtime Architecture

## Purpose
`dadou_robot_ros` is the software deployed on the robot's Raspberry Pi 4
(Docker, ROS 2 **Jazzy**). It plays authored animation sequences, reacts to the
remote controller (`dadou_control_ros`) and to the vision Pi, and actuates the
physical subsystems.

## Two worlds in one repository
- **`robot/`** — the Python application (imported as `robot.*`), coupled to the
  shared library `dadou_utils_ros` (symlink, no versioning — protected by
  contract tests and a cross-repo CI job).
- **`conf/ros2_dependencies/`** — five standalone ROS 2 (ament) packages built
  by colcon:

| Package | Role | Depends on |
|---|---|---|
| `robot_interfaces` | messages (`StringTime`, …) | nothing — the shared contract |
| `robot_drive` | cmd_vel chain (bridge, twist_mux config, deadman, kinematics) | `robot_interfaces` only |
| `robot_sim` | Gazebo Harmonic simulation (servos + LED logic re-implemented) | `robot_interfaces` only |
| `robot_description` | URDF (xacro) | — |
| `robot_bringup` | launch of the real app | `robot.*` + utils (the one assumed exception) |

`robot_drive` and `robot_sim` import **nothing** from the application: the
sim/real boundary is code duplication by design (documented in their
docstrings), with mirror unit tests on both sides. Runtime isolation is doubled
by `ROS_DOMAIN_ID` (42 = real robot, 43 = simulation) — a test command must
never be able to reach the real Didier.

## Layering inside `robot/` (strictly downward, no cycles)

```
nodes/      ROS boundary: decode StringTime payloads (nodes/payload.py,
            explicit rejection of invalid JSON), 20 Hz tick (TICK_PERIOD_S)
  └─> actions/    one Action per subsystem (contract: robot/actions/action.py,
                  ABC update(msg) / process()) — Face, Lights, AudioManager,
                  Servo (linear ramp + I2C anti-spam + deadman), Wheels,
                  RelaysManager, AnimationManager
        └─> sequences/track.py   ONE keyframe-track class (Track), injected
                                 clock, two named constructors for the two JSON
                                 readings (emit-at-t / displayed-until-t)
        └─> visual/              ImageMapping (LED wiring as a precomputed
                                 table — the PHYSICAL truth, locked by tests),
                                 FastNeoPixel (vendored direct _rpi_ws281x
                                 write: the stock Blinka backend resolution
                                 is broken in the container; the ~31 ms
                                 frame-completion sleep is KEPT — removing
                                 it corrupted frames, incident 2026-07-13),
                                 Visual (raw PNG load)
        └─> robot_config.py / robot_static.py   deploy constants; shared
                                 constants stay in dadou_utils_ros/utils_static
                                 (one-way migration rule + contract test)
```

## Animation pipeline
`animations_node` samples the JSON sequence tracks at 20 Hz through
`AnimationManager` (one `Track` per track: audio, face, lights, neck, eyes,
arms, wheels) and publishes per-track `StringTime` messages. Each consumer node
applies them event-driven. Values are discrete; smoothing lives in consumers
(servo linear ramp, LED frame rendering).

**Stop & deadman**: end of sequence broadcasts `"stop"` on every track. Wheels
AND servos also receive the remaining time (`msg.time`) while an animation
runs, and arm an absolute stop deadline (+2 s margin): if `animations_node`
dies mid-animation, wheels stop and servos return to rest.

## Safety & constraints
- Any movement feature MUST handle its stop case (deadman, e-stop, link loss).
- Wheels-path changes: simulation first, then the camera protocol (wheels off
  the ground) before any ground use. The drive chain contract is frozen.
- `e_stop` currently has NO publisher (mux lock is declared but sourceless) —
  the deadman is the effective safety net. See `interfaces.md`.
- Face LED wiring (mouth serpentine entering bottom-right, eyes 384/448,
  bottom row and eyes mounted upside down) was established physically with the
  calibration test patterns on 2026-07-11 and is LOCKED by
  `robot/tests/unit/test_image_mapping.py` — do not "fix" those tests without
  re-running the patterns on the robot.

## Tests
443 unit tests (pytest, `robot/tests/unit`, no hardware — deferred hardware
imports pattern), run by CI on every push; `dadou_utils_ros` CI re-runs the
consumers' tests to catch shared-contract breaks. Data contracts (expressions,
lights, sequences, referenced assets) are tested too.

Complementary documentation: `interfaces.md` (topics & payload contract),
`operations.md` (deploy & calibration), `../CLAUDE.md` (working state, French).
