# Robot Runtime Architecture

## Purpose
`dadou_robot_ros` is the software deployed on the robot's Raspberry Pi 4
(Docker, ROS 2 **Jazzy**). It plays authored animation sequences, reacts to the
remote controller (`dadou_control_ros`) and to the vision Pi, and actuates the
physical subsystems.

## Two worlds in one repository
- **`didier_core`** — the Python application, package `packages/didier_core/` of the
  mono-repo since L1e-3c (2026-11-07; it was the `robot/` module of this repo, imported as
  `robot.*`, now `didier_core.*`; executables unchanged). Its DATA (`json/`, `medias/`, `db/`,
  `conf/`) stays in this repo, root read from `DIDIER_DATA_DIR`. It is coupled to the
  shared library `dadou_utils_ros` (a standalone package of `packages/` since L1e-3a,
  2026-11-07 — it used to be a symlink in this repo; no versioning, protected by
  contract tests and a cross-repo CI job).
- **`packages/`** (mono-repo root; they lived in this repo's `conf/` until L1e-1,
  2026-11-06, names unchanged) — standalone ROS 2 (ament) packages built by colcon:

| Package | Role | Depends on |
|---|---|---|
| `theatre_interfaces` | messages (`StringTime`, …) — **`packages/theatre_interfaces` of the theatre-robot mono-repo: single copy for robot/vision/remote since lot L1a (2026-11-02), renamed from `robot_interfaces` in lot L1e-3b (2026-11-07), message names unchanged** | nothing — the shared contract |
| `theatre_contrats` | **`packages/theatre_contrats` (lot L1a)**: topic names (relative), payload keys, organ names, the StringTime codec, QoS profiles — pure Python | nothing (stdlib) |
| `didier_drive` | cmd_vel chain (bridge, twist_mux config, deadman, kinematics) | `theatre_interfaces` only |
| `didier_sim` | Gazebo Harmonic simulation (servos + LED logic re-implemented) | `theatre_interfaces` only |
| `didier_description` | URDF (xacro) | — |
| `didier_bringup` | launch of the real app | `didier_core.*` + utils (the one assumed exception) |

`didier_drive` and `didier_sim` import **nothing** from the application: the
sim/real boundary is code duplication by design (documented in their
docstrings), with mirror unit tests on both sides. Runtime isolation is doubled
by `ROS_DOMAIN_ID` (42 = real robot, 43 = simulation) — a test command must
never be able to reach the real Didier.

## Layering inside `didier_core/` (strictly downward, no cycles)

```
nodes/      ROS boundary: decode StringTime payloads (nodes/payload.py,
            explicit rejection of invalid JSON), 20 Hz tick (TICK_PERIOD_S)
  └─> actions/    one Action per subsystem (contract: didier_core/actions/action.py,
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
                                 CONTRACT constants live in theatre_contrats
                                 (lot L1a), re-exported by the
                                 dadou_utils_ros/utils_static shim until L5
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
  `packages/didier_core/test/unit/test_image_mapping.py` — do not "fix" those tests without
  re-running the patterns on the robot.

## Tests
1618 unit tests on 2026-11-07 (pytest, `packages/didier_core/test/unit`, run from
`packages/didier_core` with this repo's `.venv`; no hardware — deferred hardware
imports pattern), run by CI on every push; `dadou_utils_ros` CI re-runs the
consumers' tests to catch shared-contract breaks. Data contracts (expressions,
lights, sequences, referenced assets) are tested too.

Complementary documentation: `interfaces.md` (topics & payload contract),
`operations.md` (deploy & calibration), `../CLAUDE.md` (working state, French).
