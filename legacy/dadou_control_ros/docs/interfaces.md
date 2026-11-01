# Controller Interfaces

## ROS 2 Topics (Published)
| Topic | Message Type | Origin | Description |
|-------|--------------|--------|-------------|
| `/controller/audio` | `robot_interfaces/msg/StringTime` | `controller/nodes/audio_node.py` | Requests audio playback on the robot side. |
| `/controller/lights` | `robot_interfaces/msg/StringTime` | `controller/nodes/relays_node.py` | Commands light sequences / relays. |
| `/controller/wheels` | `robot_interfaces/msg/StringTime` | `controller/nodes/wheels_node.py` | Movement commands for the wheeled base. |
| `/controller/system` | `robot_interfaces/msg/StringTime` | `controller/nodes/system_node.py` | Misc system-level commands. |

> The precise list of topics may evolve. Keep this table aligned with the node implementations and the subscriber list in `dadou_robot_ros`.

## Input Devices
- **USB Gamepad**: Normalised button/axis state, mapping defined in `controller/buttons/button_config.py`.
- **RP2040 Glove**: Scans flex sensors/buttons; communicates over serial through `controller/input/serial_inputs.py`.
- **GUI**: Tkinter windows trigger the same commands as physical inputs to facilitate rehearsals.

## Configuration Files
- `controller/control_config.py`: Master configuration referencing playlists, scenes, and button layouts.
- `conf/ros2/`: ROS 2 launch files and environment configuration for controller deployment.
- `json/playlists/`: Playlists/scenes triggered by controller inputs.

## Logs & Telemetry
- Default log directory: `test_logs/` for local execution; on the robot the path is adjusted through shared constants (`dadou_utils_ros.logging_conf`).
- ROS logging uses the shared logging formatter from `dadou_utils_ros/logging_conf.py`, which now embeds the class name for easier grepping.

## External Dependencies
- Relies on `dadou_utils_ros` modules (e.g., `utils_static`, `logging_conf`).
- Uses `pygame` for gamepad support and `colorlog` for coloured logging.

See also the subscriber side in `dadou_robot_ros/docs/interfaces.md` (to be created alongside this file).

## Boîtier de faders — profils de décodage (2026-10-08)

Le device série `sliders` (RP2040-Zero, 9600 bauds) envoie 2 caractères (un
fader, 10..99) ou 4 (deux faders). Le décodage est **par profil**
(`controller/input/sliders_mapping.py`, données + tests gravés), choisi par la
variable d'environnement `SLIDERS_PROFILE` des compose (défaut `default`) et
**validé au démarrage** (nom inconnu = refus de démarrer, pas de retour silencieux
au défaut).

| Profil | 2 caractères | 4 caractères | Usage |
|---|---|---|---|
| `default` | `neck` 0..1 | `wheels` `{left, right}` −100..100 | historique, **octet pour octet** |
| `repetition` | `route_speed` 0..1 | `route_speed` (fader 1) + `neck` (fader 2) | salle de répétition simulée (`ROS_DOMAIN_ID=43`) : vitesse du cheminement de Didier (package `robot_rehearsal` du dépôt robot). Ne publie jamais vers les roues. |

`route_speed` est dans `PUBLISHER_LIST` (sinon `publish()` l'ignorerait en
silence). Sur le vrai robot, personne n'écoute ce topic : il y est inoffensif.
