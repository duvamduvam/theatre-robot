# didier_core — le cœur embarqué de Didier

Le code qui tourne sur le Pi du robot et anime le corps : servos (cou, bras, yeux), roues,
LED du visage et de la tête, relais, audio, rejeu des séquences JSON, regard et suivi de
personne, bouton système. Package ament_python depuis le lot **L1e-3c** (07/11) : c'était le
package `robot`, code dans `legacy/dadou_robot_ros/robot/` et `setup.py`/`package.xml` dans
`legacy/dadou_robot_ros/conf/ros2/`, assemblés à plat dans `ros2_ws/src/robot/` par Docker et
Ansible. Seul le CODE a bougé ; les noms de nœuds, de topics et d'exécutables sont inchangés.

## Contrat

- **Nom** : `didier_core` (package et module). Code dans `didier_core/didier_core/`
  (`nodes/`, `actions/`, `visual/`, `sequences/`, `move/`, `diagnostic/`, `db/`, `files/`,
  `audios/`, `robot_config.py`, `robot_static.py`). Tests hôte dans `test/` (jamais installés).
- **Exécutables** (gravés par `test/unit/test_arborescence.py`) : `animations_node`,
  `audio_node`, `face_sim` (SIM-ONLY), `gaze_follower`, `lights_node`, `person_follower`
  (SIM-ONLY, lancé à la main), `relays_node`, `servo_node`, `system_node`, `wheels_node`.
  Lancés par `didier_bringup/launch/robot_app.launch.py` (robot) et
  `didier_sim/launch/sim.launch.py` (sim) ; à la main : `ros2 run didier_core <exécutable>
  --ros-args -r __ns:=/didier`.
- **Dépend de** `theatre_interfaces` (StringTime), `theatre_contrats` (contrat, codec),
  `dadou_utils_ros` (lib partagée) — tous trois dans le même `src/`.
- **Dépendants** : `didier_bringup` (le launch importe `robot_static`/`robot_config`),
  `didier_rehearsal` et `didier_jeu` (journal JSONL `didier_core.diagnostic.journal`, module
  pur — seul import autorisé, gravé par leurs tests).
- **Chemin roues** : `nodes/wheels_node.py` + `actions/wheels.py`. Règles de sécurité de
  `legacy/dadou_robot_ros/CLAUDE.md` : toute modification passe par la sim puis le protocole
  caméra.

## Données attendues

Hors du package, dans le dossier désigné par **`DIDIER_DATA_DIR`** (lu par `robot_config.py`) :

| Sous-dossier | Contenu | Lu par |
|---|---|---|
| `json/` | séquences, expressions, lumières, couleurs, relais, mappings | animations, LED, catalogue |
| `medias/` | `audios/`, `visuals/{mouth,eye}` (PNG du visage) | audio, visage |
| `db/` | bases audio/séquences | `db/*.py` |
| `conf/` | `logging/`, `DEPLOY_SHA` (posé par Ansible) | journalisation, catalogue |

Ces données vivent dans `legacy/dadou_robot_ros/` jusqu'au lot L1e-4 (→ `data/`).

## Variables d'environnement

| Variable | Défaut | Qui la pose |
|---|---|---|
| `DIDIER_DATA_DIR` | `/home/ros2_ws/src/robot/` (barre finale ajoutée si absente ; vide = défaut) | les compose ARM/x86/sim (valeur = le défaut) ; `test/conftest.py` → `legacy/dadou_robot_ros/` |
| `ROBOT_NAME` | `didier` | les compose (namespace des nœuds, lot L1b) |

## Où il entre

| Contexte | Comment |
|---|---|
| Hôte (tests) | `test/conftest.py` : la racine du package, les packages frères et les firmwares de `legacy/` dans `sys.path`, `DIDIER_DATA_DIR` posé |
| Sim, x86, ARM (images) | contexte nommé `didier_core` du compose + `COPY --from=didier_core . /home/ros2_ws/src/didier_core` |
| Conteneurs (volumes) | `packages/didier_core` → `/home/ros2_ws/src/didier_core` (sur le Pi : `../../../../didier_core`) ; données sous `/home/ros2_ws/src/robot/` |
| Pi (Ansible) | liste `packages` de l'hôte robot ; `chemins_retires_robot` efface l'ancienne forme (`src/robot/{robot,setup.py,package.xml,…}`, `build/robot`, `install/robot`) avant la copie |
| Sentinelle de build | `packages/didier_core/change` (gitignorée) → `/home/ros2_ws/src/didier_core/change`, posée par Ansible (`sentinelle_build`) ou `make build`, effacée par `launch-ros-in-docker.sh` après `colcon build` |

## Tester

```bash
cd packages/didier_core && ../../legacy/dadou_robot_ros/.venv/bin/python -m pytest -q -o addopts=
```
