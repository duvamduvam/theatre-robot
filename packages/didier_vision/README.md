# didier_vision — le cerveau perceptif de Didier (Pi vision)

Le code qui tourne sur le Pi 5 « vision » : suivi de personne (webcam → MediaPipe → `vision/person`),
conversation temps réel (micro → VAD → STT → LLM streamé → voix Piper + expressions du visage),
metteur en scène intérieur (réflexion LLM asynchrone) et heartbeat `vision/status`. Il PUBLIE des
perceptions et des demandes d'animation ; il ne commande jamais les moteurs (la sécurité mouvement
reste dans `didier_drive`/`didier_core`). Package ament_python depuis le lot **L1e-3d** (08/11) :
c'était le package `vision`, code dans `legacy/dadou_vision_ros/vision/` et `setup.py`/`package.xml`
dans `legacy/dadou_vision_ros/conf/ros2/`, assemblés à plat dans `ros2_ws/src/vision/` par Docker
et Ansible. Seul le CODE a bougé ; noms de nœuds, de topics et d'exécutables sont inchangés.

## Contrat

- **Nom** : `didier_vision` (package et module). Code dans `didier_vision/didier_vision/`
  (`nodes/` I/O ROS seulement, `ai/` logique pure, `audio/`, `tracking/`, `db/`, `status.py`,
  `vision_config.py`). Tests hôte dans `test/` (jamais installés). Launch dans `launch/`.
- **Exécutables** (gravés par `didier_core/test/unit/test_arborescence.py`) : `vision_status`,
  `person_tracker`, `chat`, `reflection`. Lancés par `launch/vision.launch.py`
  (`ros2 launch didier_vision vision.launch.py chat_enabled:=true`) ; `chat` et `reflection`
  sont OFF par défaut. À la main : `ros2 run didier_vision <exécutable> --ros-args -r __ns:=/didier`.
- **Dépend de** `theatre_interfaces` (StringTime), `theatre_contrats` (contrat, codec),
  `dadou_utils_ros` (lib partagée) — tous trois dans le même `src/`. Aucune dépendance vers
  `didier_core`.

## Données attendues

Hors du package, dans le dossier désigné par **`DIDIER_VISION_DATA_DIR`** (lu par
`vision_config.py`) :

| Sous-dossier | Contenu | Lu par |
|---|---|---|
| `conf/` | `secret` (clés API, **posé par le rôle Ansible `secrets`, gitignoré, jamais affiché**), `secret.example` (le modèle) | `get_secret` |
| `medias/` | `voices/didier.onnx` + `.json` (voix Piper, **téléchargée par Ansible**, absente du dépôt), `pictures/` | TTS Piper, caméra |
| `db/` | historique de conversation (SQLite, gitignoré) | `db/chat_db.py` |
| `models/` | modèle de détection (téléchargé dans l'image) | détecteur |

`conf/` (et l'ancien flux vidéo `conf/mediamtx/`) = `machines/vision/` du dépôt depuis L1e-4c (11/11),
copié par Ansible ; `medias/` et `db/` sont des fichiers d'exécution du Pi (voix téléchargée,
historique), absents du dépôt. L'outil `tools/banc_bouche.py` (banc des modèles de la bouche) vit
dans ce package, non installé.

## Variables d'environnement

| Variable | Défaut | Qui la pose |
|---|---|---|
| `DIDIER_VISION_DATA_DIR` | `/home/ros2_ws/src/vision/` (barre finale ajoutée si absente ; vide = défaut) | les compose ARM/x86 (valeur = le défaut) ; `test/conftest.py` → `legacy/dadou_vision_ros/` |
| `ROBOT_NAME` | `didier` | les compose (namespace des nœuds, lot L1b) |
| `CHAT_*` (`CHAT_VAD_FACTOR`, `CHAT_WHISPER_MODEL`, `CHAT_PARTENAIRE`, `CHAT_MOUVEMENT`, `CHAT_REFLEXION`, `CHAT_LLM_MODEL`) | absentes = réglages du robot | le compose x86 (banc PC) seulement ; lues au démarrage de `chat`, détail dans `vision_config.py` |

La racine remplace l'ancien calcul « parent du dossier du package » (qui cassait en install-space :
symlinks provisoires `install/vision/.../conf` et `medias`, devenus inutiles). **La voix** :
`chat_piper_voice` = `<DIDIER_VISION_DATA_DIR>medias/voices/didier.onnx`, soit
`/home/ros2_ws/src/vision/medias/voices/didier.onnx` dans le conteneur (chemin final inchangé ;
valeurs gravées par `test/unit/test_didier_vision_data_dir.py`).

## Où il entre

| Contexte | Comment |
|---|---|
| Hôte (tests) | `test/conftest.py` : la racine du package et les packages frères (`theatre_contrats`, `dadou_utils_ros`) dans `sys.path`, `DIDIER_VISION_DATA_DIR` posé |
| Images ARM / x86 | contexte nommé `didier_vision` (compose ARM `additional_contexts`, compose du banc `machines/sim/banc-vision/docker-compose-x86.yml`) + `COPY --from=didier_vision . /home/ros2_ws/src/didier_vision` |
| Conteneurs (volumes) | `packages/didier_vision` → `/home/ros2_ws/src/didier_vision` (sur le Pi : `../../../../didier_vision`) ; données sous `/home/ros2_ws/src/vision/` |
| Sentinelle de build | `packages/didier_vision/change` (gitignorée) → `/home/ros2_ws/src/didier_vision/change`, lue puis effacée par `launch-ros-in-docker.sh` après `colcon build` |
| Pi (Ansible) | liste `packages` de l'hôte vision — **à faire (moitié Ansible de 3d, voir chantiers.md)** |

## Tester

Le venv robot n'a pas `sqlobject` : la vision a SON venv (`packages/didier_vision/.venv`, `requirements-test.txt` à côté).

```bash
cd packages/didier_vision && .venv/bin/python -m pytest -q -o addopts=
```
