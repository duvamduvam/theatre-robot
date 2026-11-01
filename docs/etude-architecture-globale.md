# Architecture globale du système Didier — étude multi-dépôts

*Ouverte le 2026-11-01. Statut : **étape 2 (propositions) DÉCIDÉE le 01/11 au soir** par
interrogatoire structuré (`/grill-me`, 9 axes, chaque arbitrage pris par David sur faits
vérifiés) ; **étape 3 (lots) posée, prochaine action = lot L0**. Méthode : par étapes
validées — David lit et tranche entre chaque. Contrainte dure : la simulation
(`conf/docker/sim`) doit continuer à marcher pendant tout le chantier.*

## 0. Pourquoi cette étude, et ce qu'elle doit produire

David a posé l'architecture actuelle : un **cœur** (le robot), une **lib partagée** entre
dépôts (`dadou_utils_ros` + le déploiement Ansible), puis des **appareils** qui la réutilisent
(télécommande, sono/scéno, DoubleLights, casque). Il dit atteindre ses limites techniques et
demande des **propositions** pour un système :

- **cohérent** — le code d'un appareil est écrit comme le code du robot, pas autrement ;
- **qui peut croître** — ajouter un appareil (la sono = « même principe, moins de nœuds »)
  sans réinventer ni dupliquer ;
- **maintenable et fiable** — pas d'usine à gaz ingérable, pas de roue réinventée.

Déclencheur immédiat : l'étude de l'UI télécommande
([`architecture-ui-telecommande.html`](architecture-ui-telecommande.html)) a montré que
`robot_web` possède déjà un catalogue pur et un protocole, que la télécommande tient sa propre
copie (`BUTTONS_LAYOUT`), et que le « cœur de menu » proposé en aurait été un troisième. Ce
chantier-là est **absorbé ici** : on ne tranche pas l'UI avant d'avoir tranché l'architecture.

**Exigence ajoutée par David le 01/11 au soir — la simulation porte TOUT l'ensemble.**
« La simulation est la clé de la fiabilité et de la progression. » Elle ne doit pas simuler
que le robot : le casque, DoubleLights, la sono — chaque appareil — doivent pouvoir y être
instanciés et joués ensemble, dans une même séance. Conséquence directe pour les
propositions : **un appareil qui ne peut pas être simulé n'est pas conforme à
l'architecture** ; la sim devient le test d'intégration du système entier, et donc le
premier endroit où une incohérence entre appareils doit apparaître (avant la scène). La page
web actuelle (`robot_web/static`) peut être **entièrement revue** si c'est ce que ça demande :
David ne tient pas à sa forme, il tient à ce qu'elle montre tout.

Règle d'écriture pour la suite : **toute proposition doit dire ce qu'elle SUPPRIME**, pas
seulement ce qu'elle ajoute.

## 1. Périmètre (décidé par David le 01/11)

| Dépôt | Rôle | Dans l'étude |
|---|---|---|
| `dadou_robot_ros` | cœur Didier (Pi 4 robot, Docker, ROS 2 Jazzy) | oui |
| `dadou_utils_ros` | lib partagée (lien symbolique) + Ansible de toutes les machines | oui |
| `dadou_control_ros` | télécommande (Pi 4 + écran + gants + gamepad) | oui |
| `dadou_vision_ros` | Pi 5 vision/parole | oui |
| `dadou_sceno_ros` | sono/scéno — **pas de `.git`** | oui — le cas d'école du 2e appareil |
| `dadou_hardrive_ros` | « DoubleLights », dernier commit 10/2024 | oui — à faire rentrer dans le moule ou à archiver |
| casque « helmet » de la scéno | pas de dépôt trouvé, seulement `json/lights_helmet.json` dans 3 dépôts | à ne pas oublier, pas prioritaire |
| `DEVICE_WORKSPACE` | firmwares CircuitPython (gants, boîtier), 11/2024 | hors périmètre |
| `dadou_web` | gabarit Flask copié, aucun commit | hors périmètre (à supprimer ?) |

## 2. État des lieux — mesures par script (01/11)

Ces chiffres sont **comptés**, pas estimés. Les cartes détaillées par dépôt (nœuds, topics,
matériel, déploiement) sont en §3, issues des balayages en lecture seule.

### 2.1 Taille et fraîcheur

| Dépôt | fichiers `.py` | dernier commit | tests collectés¹ | CI |
|---|---|---|---|---|
| `dadou_robot_ros` | 224 | 2026-11-01 | 1402 dans 57 fichiers | oui |
| `dadou_vision_ros` | 88 | 2026-11-01 | 960 dans 32 fichiers | oui |
| `dadou_control_ros` | 155 | 2026-10-07 | **21 dans 3 fichiers** | oui |
| `dadou_utils_ros` | 44 | 2026-07-12 | **11 dans 3 fichiers** | oui |
| `dadou_sceno_ros` | 19 | *(pas de git)* | aucun | non |
| `dadou_hardrive_ros` | 738² | 2024-10-17 | aucun | non |

¹ `pytest --collect-only` depuis la racine de chaque dépôt (inclut, pour le robot, les
packages autonomes de `conf/ros2_dependencies`). ² dont le `venv/` commité ; le code propre
tient dans `hardrive/`.

Lecture : la **lib partagée par tout le monde est la moins testée** (11 tests), et la
télécommande — qui tient le volant — a 21 tests pour 155 fichiers.

### 2.2 La lib partagée : qui l'utilise, et comment

| Dépôt | modules de la lib importés | symboles distincts |
|---|---|---|
| `dadou_robot_ros` | 10 | 63 |
| `dadou_control_ros` | 13 | 56 |
| `dadou_vision_ros` | 7 | 28 |
| `dadou_sceno_ros` | 5 | 30 |
| `dadou_hardrive_ros` | 5 | 18 |

Modules les plus importés (tous dépôts) : `utils_static` **129 imports**, `utils.time_utils`
36, `logging_conf` 25, `misc` 23, `com.input_messages_list` 13, `singleton` 11,
`files.files_utils` 10. → `utils_static` (le sac de constantes) **est** le contrat de fait
entre les machines.

**16 fichiers de la lib ne sont importés par personne** : `conftest`, `static_value`, les 8
pilotes `lcd/LCD_*`, `utils/thread_with_trace`, `utils/shutdown_restart`,
`utils/thread_with_exception`, `com/ws_server`, `com/ws_com`, `com/lora_radio`.

**Liens symboliques cassés** : `dadou_sceno_ros/dadou_utils_ros` et
`dadou_hardrive_ros/dadou_utils` pointent tous deux vers
`/home/dadou/Nextcloud/Didier/python/dadou_utils_ros/` — l'**ancien** chemin d'avant la
réorganisation `Nextcloud/Didier → dev/didier`. Ces deux appareils **ne peuvent plus
démarrer** depuis cette réorganisation ; le balayage de l'époque (61 fichiers) les a manqués.

### 2.3 Les données dupliquées entre dépôts (`json/`)

| Dépôt | fichiers dans `json/` |
|---|---|
| `dadou_robot_ros` | 72 |
| `dadou_control_ros` | **71** |
| `dadou_hardrive_ros` | 9 |
| `dadou_sceno_ros` | 3 |
| `dadou_vision_ros` | 0 |

La télécommande embarque une **copie quasi complète** des JSON du robot (séquences, visages,
lumières), et **chaque fichier commun existe en versions divergentes** (md5 différents) :
`robot_lights.json` 6 copies / 4 versions, `relays.json` 3 copies / 3 versions,
`lights_helmet.json` et `lights_base.json` 3 copies / 2 versions, et 25 séquences
d'animation en 2 versions chacune (`speak.json`, `moon-walk.json`, `maker_fair.json`…).
Il n'y a donc **pas une vérité** sur ce que le robot sait jouer : il y en a deux, qui ont
divergé sans que rien ne le signale.

### 2.4 Catalogues de commandes : combien de sources de vérité ?

Constat de départ (à compléter par §3) : au moins **deux** descriptions de « ce qu'on peut
demander au robot » coexistent — `controller/buttons/button_config.py` (`BUTTONS_LAYOUT`,
figé dans la télécommande) et `robot_web/web_catalog.py` (construit à partir des JSON du
robot, pur, testé). La première est une copie manuelle de la seconde par nature.

## 3. État des lieux — cartes par dépôt

*(Rapports des balayages en lecture seule — en cours de collecte.)*

### 3.1 `dadou_robot_ros` — le cœur : deux générations de code cohabitent

*Balayage du 01/11, affirmations croisées par grep.*

**Génération 1 — le package `robot/`** (Pi 4, matériel) : 10 nodes déclarés dans
`conf/ros2/setup.py`, tous bâtis sur le même motif `abstract_subscriber(config, action_type,
topic_name, action)` : un node = un topic StringTime souscrit + une `Action` (ABC
`robot/actions/action.py` : `update(msg)` / `process()` à 20 Hz).

| Node | Souscrit | Publie | Matériel |
|---|---|---|---|
| `animations_node` | `animation` | les 10 pistes (`audio`, `face`, `robot_lights`, `relay`, `neck`, `left/right_eye`, `left/right_arm`, `wheels`) + `animation_state` (latché) | — |
| `servo_node` ×5 | `neck`, `left_eye`, `right_eye`, `left_arm`, `right_arm` | — | PCA9685 I2C, rampe linéaire |
| `lights_node` | `face`, `robot_lights` | — | FastNeoPixel GPIO18 (sleep de fin de trame obligatoire) |
| `wheels_node` | `/cmd_vel` (Twist) ou `wheels` legacy | — | PCA9685 ch 1-2, deadman local 400 ms |
| `audio_node` | `audio` | — | ALSA |
| `relays_node` | `relay` | — | GPIO |
| `system_node` | `system` | — | GPIO shutdown/restart/LED |
| `gaze_follower` | `/vision/person`, `gaze`, `look`, `animation_state` | `neck`, `left/right_eye` (robot) ou `/neck/position` (sim) | — (logique pure `robot/move/gaze_control.py`) |
| `person_follower` | `/vision/person_box`, `follow` | `cmd_vel_follow` (Twist) | — (logique pure `robot/move/follow_control.py`) |
| `face_sim` | — | MJPEG :8766 | sim seulement |

Commentés dans `setup.py` : `ai_node`, `face_node`. Structure : `actions/` (10),
`sequences/` (AnimationManager, Track), `move/` (logique pure testée), `visual/`
(image_mapping gravé, FastNeoPixel), `files/` (RobotJsonManager), `db/`, `diagnostic/`
(journal boîte noire), `nodes/` (13). Config : dict central `robot/robot_config.py` +
constantes matériel `robot/robot_static.py` (**deux endroits** pour le matériel).

**Génération 2 — les packages autonomes** de `conf/ros2_dependencies/` (2026-07+) : règle
« aucun import `robot.*` ni `dadou_utils_ros` », constantes **dupliquées volontairement**
(`robot_web/web_protocol.py:7`), logique pure testée, nodes minces.

| Package | Rôle | Autonomie (vérifiée par grep) |
|---|---|---|
| `robot_drive` | `wheels_bridge` (StringTime→Twist), `twist_mux` (remote 100 > web 50 > follow 20 > anim 10, verrou `e_stop` 255 **sans source**), `twist_deadman` 400 ms | ✅ |
| `robot_web` | `web_bridge` :8765 — whitelist, session, heartbeat, catalogue pur, MJPEG, `cmd_vel_web` (sim) | ✅ |
| `robot_rehearsal` | `route_driver`, `fault_relay`, `director` (salle de répétition, SIM-ONLY) | ❌ `director_node.py:108` importe `robot.diagnostic.journal` |
| `robot_bringup` | launch du vrai robot | ❌ `robot_app.launch.py:11-13` importe `robot.robot_static` et `robot.robot_config` (un launch, acceptable, mais c'est bien un couplage) |
| `robot_sim`, `robot_description`, `robot_interfaces` | Gazebo, URDF, messages (`StringTime`, `HardwareStatus`, `LedState`, `TurtleTuple` — les deux derniers semblent inutilisés) | CMake |

**Contrat `StringTime`** (`robot_interfaces`) : `msg` = JSON, `time` = ms, `anim` = flag.
C'est le message universel de la maison ; son décodage est maintenant commun dans `robot/`
(chantier 07/2026) mais refait dans chaque autre dépôt.

**Lib partagée** (42 fichiers importateurs) : `TimeUtils` 15, `LoggingConf` 14, `Misc` 6,
`FilesUtils` 6, `Status` 2, + constantes `utils_static` (`NAME`, `DURATION` 12 chacune ;
`ANIMATION` 10 ; `NECK`, `FACE`, `AUDIO`, `WHEELS` 6 chacune).

**Déploiement** : `conf/docker/{arm,sim,x86,jenkins}`, sentinelle `robot/change`,
`ROS_DOMAIN_ID` 42/43, `WHEELS_CMD_VEL_ENABLED`. CI : checkout des deux dépôts (robot +
utils) puis pytest. Tests : 106 fichiers (`unit/` 59, `sandbox/` 45, `without-ros/` 2).

**Pour l'étude** : le cœur contient déjà **le modèle cible** (génération 2 : autonome,
pur, testé, contrats dupliqués et figés par des tests) **et** l'ancien modèle (génération 1 :
`abstract_subscriber` + lib partagée) sur lequel sono et DoubleLights ont été copiés. La
question n'est pas d'inventer un motif, c'est de choisir lequel des deux on généralise —
et le choix n'est pas évident : la duplication volontaire de la génération 2 est
précisément ce qui a fait diverger les JSON de la télécommande.

### 3.2 `dadou_control_ros` — la télécommande : tout passe par l'écran

*Balayage du 01/11. ~120 fichiers de code + 43 fichiers de tests (dont 3 seulement
collectés par pytest : 21 tests ; le reste = scripts d'intégration/CircuitPython lancés à la
main). CI présente (1 workflow).*

**Un seul node** (`conf/ros2/setup.py` → `controller/nodes/main_gui.py:Ros2TkinterApp`),
timer ROS 100 ms qui appelle `gui.update()`. `main_no_gui.py` est un copier-coller qui force
le rendu Pillow/LCD. **Publie 17 topics** StringTime (`PUBLISHER_LIST`,
`controller/control_config.py:70`) : `animation`, `audio`, `face`, `robot_lights`, `relay`,
`neck`, `left/right_eye`, `left/right_arm`, `wheels`, `wheel_left/right`, `random_animation`,
`designate`, `follow`, `route_speed`. Ne souscrit à rien.

⚠️ **`publish()` ignore en silence toute clé absente de `PUBLISHER_LIST`** (main_gui.py:62)
— c'est le bug `follow` du 14/09 : un bouton configuré, aucune erreur, rien n'arrive.

**Entrées physiques (5 sources), toutes lues depuis des `after()` tkinter :**

| Source | Fichier | Protocole |
|---|---|---|
| gants (boutons + inclino BNO055) | `buttons/button_config.py`, `input/serial_inputs.py` | série USB : 1 char = touche, `I`+4 chars = inclinaison |
| boîtier faders RP2040-Zero | `input/sliders_mapping.py` (profils `default`/`repetition`, pur, testé) | série 9600, 2 ou 4 chars ASCII |
| joystick RP2040 | `input/serial_inputs.py:69` | série 115200, 4 chars |
| gamepad USB Xbox | `input/usb_gamepad.py` (pygame) | 17 boutons/axes |
| clavier | `input/keyboard.py` (pynput global) | — |

Le firmware des gants (`controller/circuit_py/`, 7 fichiers CircuitPython dont un
`adafruit_bno055_bis.py` de 946 lignes) vit dans ce dépôt, en plus de `DEVICE_WORKSPACE`.

**GUI** : ~60 fichiers dans `controller/gui/` — 1 racine tkinter (`small_gui.py`), 3
« small » fenêtres, 8 fenêtres grand format (éditeurs d'expressions, lumières, séquences,
playlist…), 9 frames abstraites, 9 widgets, + rendu Pillow pour LCD SPI (`gui/pillow/`,
`lib/LCD_2inch4.py`). La boucle GUI est aussi la boucle de lecture des entrées (cf.
[`architecture-ui-telecommande.html`](architecture-ui-telecommande.html) §1).

**Catalogue des commandes** : `buttons/button_config.py` — `BUTTONS_LAYOUT` en 2 modes
(DEFAULT, PLAYLIST), 24 entrées gant + 15 gamepad, chacune `{NAME, CMD}` où CMD est le
payload publié (ex. `{AUDIO: "street/promotion-vie-eternelle.mp3"}`). **Les noms
d'animations, de sons et de chemins de fichiers du robot sont recopiés à la main ici.**

**`json/` : ~80 fichiers, ~15 lus** (`expressions.json`, `lights_base.json`,
`lights_methods.json`, `sequences/*` partiellement, `playlists/*`). Le reste est la copie
du robot jamais lue (cf. §2.3 pour les divergences).

**Lib partagée** : `utils_static` dans 46 fichiers (~40 constantes : topics, touches,
directions, MODE…), `com` (SerialDeviceManager, WsClient, InputMessagesList) 14, `misc`
13 (`is_raspberrypi`, `is_docker`, `mapping`), `time_utils` 9, `logging_conf` 9,
`singleton` 4, `files.AbstractJsonManager` 4, `audios` 3. Des constantes de topics vivent
**aussi** dans `controller/control_static.py` (RANDOM_ANIMATION, DESIGNATE, FOLLOW) :
deux endroits pour la même famille.

**Déploiement** : `conf/docker/{arm,x86}/`, base `ros:jazzy-ros-base`, **la lib est copiée
dans l'image sous forme de `dadou_utils_ros.tar.gz` (27 Mo)** — pas de version, pas de
contrôle d'API ; `SLIDERS_PROFILE` et `DISPLAY` pilotent le comportement au démarrage ;
`config[BASE_PATH]` bascule 3 fois selon `is_raspberrypi()/is_docker()`.

**Code mort identifié** : `controller/faces/` (3 fichiers), `com/glove_message.py`,
`audio/audio_navigation.py` (partiel), `gui/windows/audio/audio_player_ex*.py` (essais),
`input/gampad.py` (typo, GPIO obsolète). Code commenté : anciennes IP, chemins
alternatifs, menus (`control_config.py`, `small_gui.py`). 8 TODO mineurs.

**Pour l'étude** : ce dépôt est l'anti-modèle de `vision` — un seul gros node, logique
et I/O mêlées dans la GUI, catalogue recopié à la main, données dupliquées, 21 tests. C'est
pourtant **lui qui tient le volant**.

### 3.3 `dadou_vision_ros` — le dépôt le plus sain, et le moins dépendant

*Balayage du 01/11. 10 648 lignes hors tests, refonte 2026-07.*

**Organisation** : `vision/nodes/` (4 nodes, **I/O ROS pur, zéro logique métier**) ·
`vision/ai/` (24 modules purs : conversation, réflexion, LLM, personas, STT/TTS) ·
`vision/audio/` (8, micro/VAD/lecture) · `vision/tracking/` (6, MediaPipe + lissage) ·
`vision/db/` (SQLite) · `vision/tests/unit/` (32 fichiers, CI host-only).

| Node (`conf/ros2/setup.py`) | Publie | Souscrit | Matériel / externe |
|---|---|---|---|
| `vision_status` | `/vision/status` (5 s) | — | — |
| `person_tracker` | `/vision/person`, `/vision/person_box` (PointStamped, ~16 Hz, box latché), `camera/image_raw/compressed` (JPEG 5 i/s), `camera_state`/`camera_source_state`/`camera_sources` (latchés) | `designate`, `camera_enable`, `camera_source`, image Gazebo en sim | webcam USB, EfficientDet-Lite0 |
| `chat` (1 468 lignes) | `/face`, `/animation`, `chat_state`, `persona_state` (latchés), `chat_transcript`, `chat_audio_chain`, `chat_hearing`, `rehearsal/chat_move`, `look`, `reflect` | `chat`, `persona`, `chat_text`, `chat_instruction`, `chat_fault`, `rehearsal/objects`, `route_goto_result`, `situation`, `prompt`, **`animation_state`** (arbitrage amont) | micro/sortie ALSA, OpenRouter (Voxtral + Haiku), whisper + piper locaux ; 3 boucles (rclpy, thread conversation, aiohttp diag) |
| `reflection` | `situation`, `prompt`, `mission_state` (latché) | `chat_transcript`, `rehearsal/poi_event`, `route*`, `/vision/person_box`, image, contexte latché | OpenRouter, pool 2 workers |

**Contrats inter-machines** : seuls `/face`, `/animation`, `animation_state` sont nommés
par des constantes de la lib (`FACE`, `ANIMATION`, `ANIMATION_STATE`). **Tous les autres
topics (une vingtaine) sont des chaînes locales** au node ; le contrat est documenté dans
`ARCHITECTURE.md`, pas dans le code. → zéro couplage codé, mais zéro vérification non plus :
un renommage côté robot ne casse rien à la compilation, il casse sur scène.

**Lib partagée** : 3 constantes + le type `StringTime`. C'est **le niveau de dépendance
minimal observé** — et le dépôt le plus testé. Le décodage StringTime est refait
localement (motif cohérent, pas de régression constatée).

**Config/secrets** : `vision/vision_config.py` centralise variables d'env (`CHAT_*`) et
secrets (`conf/secret`, gitignoré, `get_secret`) ; `openrouter_key` exigée au démarrage.
**Dette connue** : `REPO_ROOT` pointe dans site-packages en install colcon → symlinks
provisoires sur le Pi (CLAUDE.md du dépôt). Pas de TODO/FIXME trouvés.

**Déploiement** : `conf/docker/arm/` (ros:jazzy-ros-base, mediapipe épinglé, modèle
téléchargé au build) + `conf/docker/x86/` (même code, banc PC) ; sentinelle `CHANGE` ;
launch `conf/ros2/launch/vision.launch.py`.

**Pour l'étude** : ce dépôt montre que le motif « nodes minces + modules purs testés +
contrats documentés » marche déjà dans la maison. La question qu'il pose : faut-il que ses
~20 topics locaux rejoignent un contrat partagé vérifiable, ou que les 3 constantes de la lib
deviennent elles aussi locales + documentées ?

### 3.4 `dadou_sceno_ros` et `dadou_hardrive_ros` — les appareils dérivés : le principe de David, tel qu'il est câblé

*Balayage du 01/11, liens vérifiés par `readlink`.*

**Le mécanisme réel d'un « appareil »** (identique dans les deux dépôts) :

```
dadou_sceno_ros/
├── robot        → lien vers dadou_robot_ros/robot/   (LE PACKAGE ENTIER du cœur)
├── dadou_utils_ros → lien vers la lib
├── sceno/       (19 .py) : sceno_config.py, files/ScenoJsonManager, actions/relays_sceno.py,
│                nodes/{audio,relays,system}_node.py — qui importent robot.actions.AudioManager,
│                robot.nodes.abstract_subscriber.SubscriberNode…
├── json/        audios.json, audios-data.json, relays.json (1 relais `cut_voice` vs 8 au robot)
└── conf/        setup.py (package_name = 'robot' !), docker arm/x86
```

Autrement dit : **un appareil = le cœur entier en lien symbolique + un petit package de
surcharge**. C'est bien le principe « même base, moins de nœuds ». Ses conséquences telles
qu'on les constate :

| Constat | Sono | DoubleLights |
|---|---|---|
| lien vers `robot/` | **cassé** (ancien chemin `Nextcloud/Didier`) | OK (relatif `../dadou_robot_ros/robot/`) |
| lien vers la lib | **cassé** (ancien chemin) | **cassé** (ancien chemin, nommé `dadou_utils`) |
| `package_name` ROS | `'robot'` — **collision de nom avec le cœur** | `'robot'` — idem |
| nœuds actifs | 1 (`audio_node` ; `relays_node`, `system_node` commentés dans setup.py) | 1 (`lights_node` : rubans disk + helmet sur GPIO18, 150 LED) |
| appelle le cœur avec | `SubscriberNode(AUDIO, AUDIO, self.audio)` — **ancienne signature** (le cœur attend `(config, …)` depuis 2026) | `Lights` du cœur + timer 0,1 s (le cœur est à 20 Hz) |
| fraîcheur | code 02/2025, **pas de `.git`** | dernier commit 10/2024, 6 commits, `venv/` commité |
| tests / CI | 1 fichier + tests de style ROS / aucune | 10+ scripts matériel / aucune |
| Ansible | groupe `sceno`, hôte `s` | groupe `disk`, hôte `d` |

Ni l'un ni l'autre ne peut démarrer aujourd'hui : liens cassés **et** API du cœur qui a
bougé sous eux sans que rien ne le signale (aucun test ne les exécute). Le casque « helmet »
n'est qu'une zone de LED de DoubleLights (`lights_helmet.json`, indices 65-128).

**Pour l'étude** : le principe est bon (un appareil ne réécrit pas le cœur), **le câblage ne
l'est pas** : lien symbolique = pas de version, pas de contrôle, collision de nom de
package, et surtout **le cœur ne sait pas qu'il a des dépendants** — il a cassé la sono en
changeant une signature, sans qu'aucun test rougisse nulle part.

### 3.5 `dadou_utils_ros` et le déploiement Ansible — la lib est petite, le déploiement est grand

*Balayage du 01/11. 3 561 lignes dont **1 869 de pilotes LCD jamais importés**.*

**Contenu réel de la lib** : `utils_static.py` (126 l., le contrat), `logging_conf.py`
(124), `misc.py` (179 : shell, regex, `is_raspberrypi`, `is_docker`), `singleton.py`,
`audios/` (168, lecteur multi-backend legacy), `com/` (366 : série, WebSocket, LoRa, file
de messages), `files/` (98, JSON), `utils/` (151 : threads, status, time), `lcd/` (1 869,
11 pilotes). **8 modules (~2 100 lignes, 59 %) ne sont importés par personne.**

**`utils_static.py` : 93 constantes** (et non 312 — ce chiffre de mémoire agrégeait
sans doute `robot_static` et `control_static`) :

| Famille | nombre | spécifique Didier |
|---|---|---|
| noms de topics StringTime | 16 | **11** (`NECK`, `LEFT_EYE`, `FACE`, `ROBOT_LIGHTS`…) |
| clés de payload JSON | 34 | 2 (`MOUTH`, `EYE`) |
| chemins/répertoires | 15 | 0 |
| plateforme/logging, internes, divers | 28 | 0 |

**Contrat et versionnage** : pas de `setup.py`, pas de version, pas de pip — un lien
symbolique relatif (`../dadou_utils_ros`, robot/control/vision) ou absolu cassé
(sceno/hardrive), et un `tar.gz` copié dans l'image Docker de la télécommande. Le contrat
est **figé par des tests de valeurs** dans deux dépôts (`test_contrat_utils.py` côté robot,
`test_utils_static_contract.py` côté télécommande, 111 assertions) : un renommage casse
rouge dans les consommateurs, **mais rien ne teste les signatures** (c'est ainsi que la
sono a cassé). Le décodage StringTime existe en **3 versions** (`robot/nodes/payload.py`,
`vision/ai/stage.py`, `json.loads` inline dans la télécommande).

**Configuration** : pas de mécanisme partagé — chaque dépôt construit son dict `config`
Python à partir des constantes (`robot_config.py` ~80 clés, `control_config.py`,
`sceno_config.py`…), avec bascules `is_raspberrypi()/is_docker()/'unittest' in sys.modules`
pour les chemins.

**Ansible (`ansible/`)** : c'est la vraie colonne vertébrale du système.

| Élément | Contenu |
|---|---|
| inventaire `hosts` | 8 groupes / hôtes : `robot/r`, `control/c`, `vision/ai`, `sceno/s`, `disk/d`, `integration/ci`, **`glove-left/gl`, `glove-right/gr`** (= la Zero 2 W fraîchement installée), `robot-test` |
| variables par hôte | `local_project_dir`, `project_ros_dir`, `project_name`, `launch_cmd` |
| playbooks | `install-pios-full.yml` (provisioning complet), `deploy-pios.yml` (code seul), variantes lite/test |
| rôles | **33** : infra (dir_struct, docker-*, packages), code (`synchronise` = rsync du checkout local → `/ros2_ws/src/`, `colcon_build`), ROS (dont `ros_humble_*` — **antérieurs à Jazzy**), matériel (i2c, spi, blinka, usb-audio, screen), services (systemd, start-scripts), legacy douteux (`jenkins`, `nginx`, `sonar`, `deploy`) |
| templates | `project.service`, `launch-ros-in-docker.sh` (sentinelle `change`), `asoundrc`, `cmdline.txt` |
| documentation | **aucun README** dans `ansible/` |

**Pour l'étude** : la lib « partagée » se réduit en pratique à **un fichier de constantes
+ logging + 2-3 utilitaires** ; le reste est mort ou legacy. Le vrai actif commun, c'est
Ansible : il sait déjà déployer 8 machines à l'identique, y compris les gants. C'est là que
« ajouter un appareil » est aujourd'hui le moins cher — et le moins documenté.

## 4. Synthèse de l'état des lieux — ce qui bloque la croissance

*À valider par David avant d'ouvrir les propositions (§5). Tout ce qui suit est tiré des
mesures §2 et des cartes §3 ; rien n'est une opinion sur ce qu'il faudrait faire.*

### 4.1 Le principe d'origine est juste, son câblage l'a trahi

L'architecture voulue — **un cœur, une lib commune, des appareils qui dérivent du cœur** —
est exactement celle qu'il faut pour « ajouter un robot sans réinventer ». Elle existe : la
sono et DoubleLights **sont** des dérivés du cœur. Mais elle tient par des **liens
symboliques** et rien d'autre, et c'est ce câblage qui a cédé sur quatre points :

1. **Rien ne versionne, rien ne vérifie.** Lien symbolique, tar.gz, rsync : le cœur et la
   lib changent sans numéro ; les dépendants ne l'apprennent qu'en plantant. La sono est
   cassée par un changement de signature du cœur (§3.4) et **personne ne l'a su**.
2. **Les liens absolus ont survécu à la réorganisation** `Nextcloud/Didier → dev/didier` :
   3 liens cassés (sono ×2, DoubleLights ×1). Deux appareils morts en silence.
3. **La collision `package_name = 'robot'`** (cœur, sono, DoubleLights) interdit de faire
   cohabiter deux appareils dans un même espace de travail ROS.
4. **Le cœur ignore ses dépendants** : aucun test du cœur n'exécute la sono ; aucune CI ne
   la construit.

### 4.2 Deux sources de vérité pour les données, trois pour le code

- **Données** : la télécommande embarque 71 des 72 JSON du robot, **tous divergents** ;
  `robot_lights.json` existe en 4 versions, `relays.json` en 3 (§2.3). Ce que Didier sait
  jouer n'est écrit nulle part de façon unique.
- **Catalogue des commandes** : `BUTTONS_LAYOUT` (télécommande, recopié à la main) vs
  `web_catalog.py` (robot_web, construit depuis les JSON) (§2.4).
- **Décodage StringTime** : 3 implémentations (§3.5). **Constantes de topics** : lib +
  `control_static.py` + chaînes locales dans vision (~20) et robot_web (dupliquées
  volontairement).

### 4.3 Deux générations de code coexistent dans le cœur même

| | Génération 1 (`robot/`, sono, DoubleLights, télécommande) | Génération 2 (`conf/ros2_dependencies/*`, vision) |
|---|---|---|
| motif | `abstract_subscriber` + `Action`, lib partagée par lien | nodes minces + modules purs, **aucun import** du cœur ni de la lib |
| contrat | constantes importées de `utils_static` | chaînes **dupliquées volontairement**, figées par tests |
| tests | 1402 robot / 21 télécommande / 0 appareils | 960 vision ; packages autonomes testés |
| cas d'école | télécommande : tout dans la GUI, 1 node | vision : I/O ROS pur, logique dans `vision/ai` |

La génération 2 est **ce qui marche le mieux aujourd'hui** (c'est elle qu'on a validée en
sim et caméra depuis juillet). Mais sa duplication volontaire est aussi, à grande échelle,
**ce qui a produit les 71 JSON divergents de la télécommande**. Les deux modèles ont donc
chacun prouvé une qualité et un défaut — la proposition devra dire comment on prend
l'autonomie de l'une sans la divergence de l'autre.

### 4.4 La télécommande, qui tient le volant, est le maillon le plus faible

Un seul node ; les 5 sources d'entrée lues depuis des `after()` tkinter cadencés par un
timer ROS ; un filtre `PUBLISHER_LIST` qui jette en silence ; 21 tests pour ~120 fichiers ;
3 modules morts ; catalogue recopié. Rien de tout cela n'est un bug aujourd'hui (le
deadman 400 ms rattrape), mais **c'est le seul dépôt où une erreur de code devient un
mouvement de 50 kg**, et c'est le moins protégé.

### 4.5 La lib partagée est beaucoup plus petite qu'elle n'en a l'air

93 constantes (dont 11 noms d'organes de Didier), le logging, 2-3 utilitaires : voilà ce
qui est réellement partagé. **59 % des lignes de la lib ne sont importées par personne.**
Le « diagnostic utils partagé » (chantier en veille) visait juste, mais l'objet est plus
petit que prévu — et le vrai actif commun du système n'est pas la lib, c'est **Ansible**
(8 machines, 33 rôles, 0 README).

### 4.6 Ce qui va bien et qu'il ne faut pas casser

- Le cœur `robot/` : 1402 tests, contrats de données testés, visage gravé, chaîne roues
  validée caméra. La sim (`conf/docker/sim`) tourne et c'est la contrainte dure.
- `dadou_vision_ros` : le modèle à généraliser pour la séparation I/O / logique.
- `robot_drive`, `robot_web` : autonomes, purs, testés — la base d'une « roue » déjà faite.
- Ansible : il déploie déjà tout le monde, y compris la Zero du gant (`gr`).

### 4.7 Les questions que les propositions devront trancher (et pas une de plus)

1. **Comment un appareil dérive du cœur** sans lien symbolique : paquet versionné ?
   mono-dépôt ? sous-arbre git ? — et comment le cœur *sait* qu'il a des dépendants.
2. **Où vit la vérité des données** (JSON) et du **catalogue** : un seul endroit, lu par
   la télécommande, le web et les appareils.
3. **Quel motif de code on généralise** : génération 2 (autonomie + duplication figée par
   tests) ou génération 1 (lib partagée) ou un hybride — et ce qu'on fait des 59 % morts.
4. **Comment la télécommande sort de la GUI** sans toucher au chemin roues autrement que
   par sim + protocole caméra (c'est l'étude UI, désormais un lot de celle-ci).
5. **Le nom de package** et l'organisation ROS d'un appareil (fin de la collision `robot`).
6. **Ansible comme contrat d'appareil** : ce qu'un nouvel hôte doit déclarer, documenté.
7. **Comment chaque appareil se simule** (exigence du §0) : aujourd'hui seule la sim du robot
   existe (`robot_sim`, Gazebo + `face_sim` + `web_bridge`) ; il n'y a **aucune** sim du
   casque, de DoubleLights ni de la sono. La proposition doit dire ce qu'un appareil fournit
   pour être simulable (jumeau du matériel ? rendu web de ses LED/relais/son ?) et comment
   plusieurs appareils tournent dans une même séance (un conteneur ? un domaine ? un
   compose multi-services ?) — et ce que devient la page scène pour montrer l'ensemble.

## 5. Propositions — DÉCIDÉES le 01/11 (interrogatoire en 9 axes)

*Chaque ligne ci-dessous est un arbitrage de David, pris sur des faits vérifiés dans les
dépôts le jour même (pas sur des impressions). Les options écartées sont rappelées pour
que personne ne les rouvre sans raison nouvelle. Règle du §0 appliquée : chaque
décision dit ce qu'elle SUPPRIME.*

### 5.0 Ce que « réussi » veut dire (critères de fin du chantier)

1. **Ajouter un appareil ≈ 1 jour**, en suivant un gabarit documenté, sans copier ni code
   ni JSON (la sono le prouvera, §6 L3).
2. **Une vérité par donnée** : chaque JSON, le catalogue de commandes, chaque nom de topic
   n'existe qu'à UN endroit ; les autres le lisent.
3. **Tout dans la sim** : robot + appareils jouent ensemble dans une même séance
   simulée, un conteneur par machine.
4. **Casse détectée tout de suite** : un changement du cœur qui casse un appareil fait
   rougir la CI au commit, plus jamais en silence.
5. **Une télécommande fluide et bien intégrée** (c'est le sujet qui intéresse le plus
   David : le contrôle à distance).
6. **Des répertoires cohérents qui facilitent la lecture** — David dit avoir eu du mal à
   structurer, c'est POUR ÇA qu'il avait fait plusieurs dépôts.
7. **La doc mise à jour en profondeur**, pas rafistolée.

### 5.1 Tri du périmètre

| Objet | Décision | Supprime |
|---|---|---|
| `dadou_web` | **SUPPRIMÉ le 01/11** (gabarit public `nickjj/docker-flask-example` intact, 0 commit, 270 lignes JS caméra de 2024 jamais branchées, « ça n'a jamais vraiment marché ») | le dossier (67 Mo) |
| Sono (`dadou_sceno_ros`) | **Réécrite depuis le gabarit** (§6 L3) ; le code actuel est archivé dans un nouveau dépôt public `duvamduvam/dadou_sceno_ros` (il n'était dans AUCUN git) puis supprimé du disque. On ne garde que : `json/` (audios, relais) et le rôle Ansible `sceno`. Les 244 Mo d'audios du spectacle restent sur le disque, hors dépôt public | 19 .py de génération 1, liens cassés |
| DoubleLights (`dadou_hardrive_ros`) + casque | **Même traitement** : réécrits depuis le gabarit quand le spectacle en aura besoin ; déjà sur GitHub (`dadou_disk_ros`, 3 fichiers non commités à pousser). On garde `lights_helmet.json` (mapping LED disk/casque) et le rôle `disk` | le code 2024, le `venv/` commité |
| `DEVICE_WORKSPACE` | hors périmètre (décidé) ; **13 modifications non commitées à pousser** (lot L0), rien d'autre | — |

Option écartée : *porter le code existant* (réparer les liens, adapter les signatures) —
ça aurait gardé la génération 1 vivante dans deux appareils de plus.

### 5.2 Cible lointaine : des Didier autonomes qui se parlent — pas avant 2028

Ce que « d'autres robots synchronisés » veut dire pour David : **des robots autonomes qui
partagent un état** (où est l'acteur, qui parle), **pas de chef**, pas de chœur en
timeline. Horizon : **pas avant 2028**. Consigne explicite : *« fais ce qu'il faut pour
qu'un ajout soit fluide, mais ne perds pas de temps pour un robot spécifique qui arrive
dans longtemps »*.

**La seule garantie prise maintenant : un nom par robot.** Tous les topics d'un robot
vivent sous son namespace (`didier/…`), posé dans les launch ; les noms de topics
**absolus sont interdits** et un test le vérifie. Fait relevé le 01/11 : vision publie
3 topics absolus (`/vision/person`, `/vision/person_box`, `/vision/status`) — à corriger
en L1. Écarté pour l'instant : contrat d'état partagé, deux Didier dans Gazebo.

### 5.3 Sources de vérité : le robot publie, on édite À TRAVERS le robot

- **Les JSON vivent dans le cœur seulement** (`data/`). Au démarrage, télécommande, page
  web et appareils **reçoivent le catalogue du robot** (topic latché — c'est déjà ce que
  fait `robot_web`). Zéro copie sur disque ailleurs. Prix accepté : sans robot allumé, la
  télécommande n'a pas de liste → elle garde un **cache du dernier catalogue reçu**.
- **Contradiction levée en séance** : la télécommande n'est pas qu'un lecteur, c'est
  **l'éditeur** (8 modules écrivent du JSON : séquences, expressions, lumières) — ses
  copies ont divergé par édition locale, jamais rapatriée. Décision : **tout éditeur
  ENVOIE la modification au robot**, qui écrit le fichier, garde une sauvegarde et
  republie le catalogue. Une seule écriture au monde. À définir en L1 : le protocole
  d'édition (topic/service, validation du payload, refus loggué comme pour StringTime).
- **Le catalogue des commandes est publié par le robot** (généralisation de
  `web_catalog.py`) ; `BUTTONS_LAYOUT` disparaît.
- ⚠️ **26 à 29 séquences n'existent QUE sur la télécommande** (robot : 6, télécommande :
  32 — `access-internet`, `moon-walk`, `pas-un-jouet`, `t-es-sur`, `upload-cerveau`,
  `suicide`, `trip`… ) : **à rapatrier dans `data/` en L0, avant toute suppression**.

Supprime : 71 JSON de la télécommande, `BUTTONS_LAYOUT`, les 3 copies de `relays.json`,
les 4 de `robot_lights.json`. Options écartées : paquet de données versionné (un
déploiement par retouche), hash vérifié seulement (la divergence resterait possible).

### 5.4 Partage du code : UN mono-dépôt, génération 2 partout, un package `contrats`

- **Mono-dépôt `dadou`** (GitHub `duvamduvam/dadou`) : cœur, roues, web, vision,
  télécommande, sono, contrats, sim, Ansible. Une version = tout cohérent ; **une CI**
  construit et teste tout → casser la sono fait rougir le commit qui la casse. Les
  historiques des 4 dépôts sont **conservés** (`git subtree add`, pas de copie à plat).
  Supprime : `dadou_utils_ros`, tous les liens symboliques, les 4 dépôts séparés (archivés
  sur GitHub tels quels, en lecture).
- **Motif unique = génération 2** : nœud rclpy mince (I/O seulement) + modules purs testés
  sans ROS — c'est ce qui a été validé en sim et caméra depuis juillet (20 nœuds de
  génération 2 contre 6 fichiers de génération 1). Les noms de topics, schémas de payload,
  codec StringTime et messages `.msg` viennent d'**un package `dadou_contrats`** du
  mono-dépôt : fin de la duplication « figée par tests » de la génération 2 ET de la lib
  fourre-tout de la génération 1. Le cœur `robot/` migre **module par module, au fil des
  lots, sim toujours verte** ; `SubscriberNode`/`Action` disparaissent avec le dernier
  module migré (L5). Supprime : 59 % de la lib (mort), `utils_static` (93 constantes →
  `dadou_contrats`), `abstract_subscriber`, les 3 décodeurs StringTime, les 3 copies de
  `robot_interfaces`.
- Options écartées : multi-dépôts + paquet versionné (versions à gérer dans 5 dépôts, la
  casse se voit à la montée de version et pas au commit) ; zéro partage (c'est le modèle
  qui a produit les 71 JSON divergents).

### 5.5 Structure du mono-dépôt — « packages à plat + machines » (à valider en L0 sur pièce)

Principe choisi : on lit la carte du système en ouvrant **deux dossiers** — `packages/`
(QUOI, un package par fonction) et `machines/` (OÙ ça tourne). Écarté : par machine
(le code commun aurait regrossi un `commun/` = l'histoire de la lib qui recommence) ;
workspace ROS nu (`src/` à plat, illisible pour qui ne connaît pas ROS).

Nommage décidé : **`didier_*`** pour ce qui appartient au robot, **`<appareil>_*`**
(`telecommande_*`, `sono_*`, `lights_*`) pour les appareils, **`dadou_*`** pour le commun.
Le préfixe dit à qui appartient le package ; fin de la collision `robot` ×3. Écarté :
garder `robot_*` (ambigu le jour du 2e robot), `dadou_*` partout (on ne lit plus la
machine).

```
dadou/
├── CLAUDE.md                  un seul (règles, commandes, priorités)
├── README.md                  la carte du système en une page : quoi tourne où
├── packages/                  un package ROS 2 par fonction, à plat
│   ├── dadou_contrats/        topics, schémas de payload, codec StringTime, .msg (ex robot_interfaces)
│   ├── dadou_sim/             la séance : compose multi-conteneurs, monde Gazebo, page scène
│   ├── dadou_gabarit/         le squelette d'appareil à copier (README-contrat, pilote sim, tests)
│   ├── didier_core/           ex robot/ : visage, servos, animations, relais, lumières
│   ├── didier_drive/          ex robot_drive — INCHANGÉ (validé caméra 04/07)
│   ├── didier_description/    URDF
│   ├── didier_web/            ex robot_web : catalogue publié, page scène, édition via robot
│   ├── didier_vision/         ex vision/
│   ├── didier_rehearsal/      SIM-ONLY (garde-fou domaine 43)
│   ├── didier_bringup/
│   ├── telecommande_entrees/  gants, gamepad, faders, boutons → événements   (L4)
│   ├── telecommande_core/     état, modes, deadman, catalogue reçu → commandes (L4)
│   ├── telecommande_affichage/ écran Pi 4 / LCD, pygame                    (L4)
│   └── sono_core/             réécrit depuis le gabarit                      (L3)
├── machines/                  CE qui tourne OÙ : une entrée par hôte Ansible
│   ├── robot/ vision/ telecommande/ sono/ lights/ gant-gauche/ gant-droit/
│   │     chacun : packages.txt (ce qu'on y rsync), compose ARM, launch, host_vars
│   └── sim/                   compose x86 : un service par machine ci-dessus, domaine 43
├── data/                      les JSON — vérité unique, déployés sur le robot seul
├── deploy/                    Ansible (ex dadou_utils_ros/ansible), épuré (§5.7)
├── docker/                    Dockerfiles communs (base ARM / x86)
├── docs/                      doc VIVANTE : architecture, operations, contrats, chantiers, hardware/, incidents/
│   └── etudes/                les études, statut en tête (ouverte / close = gelée)
└── atelier/                   essais (voix…), pcb, scripts d'atelier — pas déployé
```

### 5.6 La télécommande : réécrite de zéro, Twist dès sa naissance

- **Réécriture de zéro** depuis le gabarit d'appareil ; on ne reprend que les **pilotes
  matériels** (gants LoRa, faders, gamepad) comme modules purs. La télécommande actuelle
  **reste en service** jusqu'à la bascule. Découpe = celle de l'étude UI
  (`architecture-ui-telecommande.html`, décisions conservées) : entrées / cœur /
  affichage, trois nœuds testables séparément, le cœur sans matériel ni écran.
  Écarté : 1 nœud + modules purs ; 3 nœuds extraits du code actuel.
- **Chemin roues** : la nouvelle télécommande **publie `cmd_vel_remote` (Twist)
  directement**, dès sa naissance. Elle passe **sim + protocole caméra**
  (`validate-cmdvel-protocol.sh`) avant toute mise en service, comme tout nouveau chemin
  roues. **L'ancienne (StringTime → `wheels_bridge`) reste le chemin de repli documenté**
  jusqu'à ce que la nouvelle ait roulé au sol ; `wheels_bridge` ne disparaît qu'après.
  Demande explicite de David : *documenter pour la suite en cas de problème* → la
  procédure de retour à l'ancienne télécommande fait partie du lot L4.
- Supprime (à terme) : `wheels_bridge`, `PUBLISHER_LIST`, les `after()` tkinter, les 3
  modules morts, 71 JSON.

### 5.7 Tout dans la sim : pilote interchangeable + un conteneur par machine

- **Contrat de simulabilité** (règle pour tout package) : chaque nœud qui touche du
  matériel passe par un **pilote** (`Leds`, `Relais`, `Audio`, `Servos`…) qui a une
  variante `sim` **publiant son état** sur un topic ; la **page scène rend tous ces
  états** (LED, relais, son joué, servos). Le reste du code est identique réel/sim.
  Gazebo seulement pour ce qui bouge dans l'espace. Écarté : jumeau Gazebo par appareil
  (lourd, inutile pour un relais), nœud qui tourne sans rendu (on ne voit pas que la sono
  a joué le bon son).
- **Séance** : `machines/sim/` = un compose qui lance robot, vision, télécommande, sono…
  **chacun dans SON conteneur**, image x86 du **même Dockerfile** que l'ARM, domaine 43,
  `SIM=true`. La sim teste aussi le déploiement et les frontières entre machines. Prix
  accepté : RAM PC, démarrage plus long. Écarté : tout-en-un (rien ne garantit que ce qui
  marche dans un conteneur marche sur 4 machines).

### 5.8 Déploiement : rsync du sous-ensemble + empreinte de version ; Ansible épuré

- Ansible copie pour chaque machine **ses** packages (déclarés dans
  `machines/<hôte>/packages.txt`) + `dadou_contrats` + `data` (robot seul), et **écrit le
  sha git déployé** ; chaque nœud publie ce sha, la page scène montre si deux machines
  divergent. Même mécanique qu'aujourd'hui (pas de git sur le Pi, sentinelle de build),
  mais versionnée et visible. Écarté : images Docker par commit (build ARM en CI lent,
  plus de retouche rapide), git sur chaque Pi.
- `hosts` déclare déjà par machine `local_project_dir`, `project_ros_dir`, `launch_cmd` :
  c'est l'embryon de `machines/`.
- **Ménage décidé** : suppression des **6 rôles orphelins** (`activate-spi`,
  `download-install-docker-from-url`, `root_ssh`, `ros_dependencies`, `set-vim`,
  `waveshare-screen`) et de **toute la mécanique Jenkins/Sonar/hôte `ci`** (rôles
  `jenkins`, `sonar`, playbooks `install-ci*.yml`, `configure-local-ci.yml`,
  `install-test-pios.yml`) — la CI est GitHub Actions depuis juillet.

### 5.9 Documentation : vivante / études / README-contrat

- `docs/` ne garde que la doc **vivante** (architecture, opérations, contrats, chantiers,
  incidents, matériel). Les **études** (11 fichiers, 10 056 lignes) partent dans
  `docs/etudes/` avec un **statut en tête** : *ouverte* ou *close* (gelée, on n'y écrit
  plus). **Un seul `CLAUDE.md`.**
- **Chaque package a un README-contrat obligatoire** : rôle, topics entrée/sortie (avec
  renvoi à `dadou_contrats`), comment le simuler, comment le tester, sur quelle machine
  il tourne. C'est ce README qui rend « ajouter un appareil ≈ 1 j » possible.
- Règle inchangée (mémoire `feedback-doc-a-jour`) : la doc se met à jour **dans le même
  lot** que le code.

### 5.10 CI : tests + build colcon + séance sim de fumée

À chaque commit du mono-dépôt : pytest de chaque package (hôte) + `colcon build` du
workspace complet dans l'image x86 + **démarrage de la sim headless multi-conteneurs et
vérification que tous les nœuds annoncent leur état**. David a choisi la variante la
plus sûre en connaissant son prix (~25 min, fragile en CI gratuite) : si la fumée s'avère
trop instable, on la rend **optionnelle sur `main`** plutôt que de la supprimer. Toujours
public, jamais de secrets.

### 5.11 Rôle de David pendant le chantier

Il **valide chaque étape** (rien ne passe au lot suivant sans son OK), fait **les tests
physiques** (protocole caméra, écoute, séances en sim devant l'écran) et **continue à
composer** (séquences, voix, persona) en parallèle : **le chantier ne doit jamais le
bloquer plus de quelques heures** — d'où la contrainte « la sim marche toujours » et le
découpage en lots indépendamment livrables. Il ne code pas.

## 6. Lots — ordre DÉCIDÉ le 01/11 (fondations d'abord, télécommande en dernier)

*Pourquoi cet ordre : la télécommande dépend du catalogue (L1), de la sim (L2) et du
gabarit (L3) — la mettre avant, c'était figer le gabarit sur le cas le plus complexe. La
sono avant les contrats aurait été à reprendre. Chaque lot a sa porte de sortie
vérifiable ; David valide entre chaque.*

| Lot | Contenu | Supprime | Porte de sortie (vérifiée) |
|---|---|---|---|
| **L0 Sauvegardes + squelette** | 1) pousser les **90 commits** du cœur, **31** de vision, **3** de la télécommande ; commiter les 12 fichiers de la télécommande, 3 de DoubleLights, 13 de DEVICE_WORKSPACE ; 2) **rapatrier les ~29 séquences** de la télécommande dans `data/` ; 3) archiver la sono sur GitHub ✅ (fait le 01/11) ; 4) créer `dadou` par `git subtree add` des 4 dépôts (historiques conservés), arborescence §5.5 **posée mais vide là où rien n'existe** ; déplacer les packages existants SANS les renommer encore ; 5) un `CLAUDE.md`, les 4 anciens dépôts marqués « archivé, voir dadou » | `dadou_web` ✅, liens symboliques | la sim démarre depuis le mono-dépôt exactement comme avant (`validate-*.sh` existants verts) ; CI tests verte ; David valide l'arborescence SUR PIÈCE |
| **L1 Contrats + données** | `dadou_contrats` (93 constantes utiles, codec StringTime unique, `.msg`) ; namespace `didier/` + test « aucun topic absolu » (3 à corriger dans vision) ; le robot publie **catalogue + sha déployé** ; **protocole d'édition via le robot** ; cache côté lecteur ; renommages `didier_*` | `utils_static`, 3 décodeurs StringTime, 3 `robot_interfaces`, `BUTTONS_LAYOUT`, 71 JSON | une retouche faite depuis la page scène arrive dans `data/` du robot et est rejouée ; la télécommande actuelle lit le catalogue publié ; chemin roues NON touché |
| **L2 Sim multi-conteneurs** | `machines/sim/` : un conteneur par machine, mêmes Dockerfiles que l'ARM ; pilotes `sim` qui publient leur état ; page scène qui rend tous les états ; **séance de fumée** en CI | l'image sim fourre-tout | robot + vision + télécommande actuelle tournent dans 3 conteneurs, domaine 43 ; CI build + fumée verte |
| **L3 Gabarit + sono** | `dadou_gabarit` (README-contrat, pilote sim, tests, entrée `machines/`) ; **`sono_core` réécrit en suivant le gabarit, chrono en main** ; rôle Ansible `sono` épuré | `dadou_sceno_ros` du disque | la sono joue en sim un audio et un relais visibles sur la page scène ; déployée sur `s` par Ansible ; **temps mesuré ≤ 1 j** ou le gabarit est corrigé |
| **L4 Télécommande neuve** | 3 packages `telecommande_*` depuis le gabarit, pilotes matériels repris en modules purs, **Twist direct** ; pygame (essai décidé dans l'étude UI) ; **procédure de repli vers l'ancienne, écrite** | (après roulage au sol) `wheels_bridge`, `controller` | **sim + protocole caméra 4/4** avant mise en service ; l'ancienne reste installée jusqu'au premier roulage au sol réussi de la neuve |
| **L5 Ménage + fin de migration** | derniers modules du cœur en génération 2 ; `SubscriberNode`/`Action` supprimés ; Ansible épuré (§5.8) ; études gelées dans `docs/etudes/` ; README-contrat partout ; DoubleLights/casque = **lot optionnel** sur le gabarit si le spectacle reprend | `abstract_subscriber`, 59 % de la lib, 6 rôles + Jenkins/Sonar/`ci`, anciens dépôts (archivés) | `grep` des motifs de génération 1 = 0 ; tous les packages ont leur README-contrat ; les 7 critères du §5.0 cochés un à un avec David |

⚠️ **Secrets — découvert le 01/11 en archivant la sono.** GitHub a bloqué le push : la sono
embarquait un fichier `conf/secret` (format INI) avec **4 identifiants** — `chatgpt_key`
(clé API OpenAI, détectée par GitHub), `google_cloud`, `sms_user`, `sms_pwd`. Le fichier a
été retiré de l'archive avant publication (commit amendé, `.gitignore`). Mon contrôle
préalable (motifs `api_key|secret|token`…) **l'avait manqué** parce qu'il excluait les
liens `robot/` et `dadou_utils_ros/` et ne cherchait pas un fichier NOMMÉ `secret` :
leçon = chercher aussi les noms de fichiers, et faire confiance à la protection GitHub
comme filet, pas comme premier contrôle. **À faire en L0, avant tout push des commits en
retard : (1) révoquer/renouveler les 4 identifiants côté fournisseur (OpenAI, Google
Cloud, opérateur SMS) — la clé OpenAI est réputée morte (mémoire du proto conversation)
mais on ne parie pas dessus ; (2) vérifier que ni le fichier ni les valeurs n'existent
dans l'arbre ou l'historique des 6 autres dépôts (recherche lancée le 01/11, résultat
ci-dessous) ; (3) dans le mono-dépôt, les secrets vivent HORS git (fichier `.env` local
ignoré + variables d'environnement dans le compose), jamais dans `conf/`.**

**Résultat de la recherche (01/11, 6 dépôts, arbre + historique complet)** :

| Dépôt | Fichier `secret` dans l'arbre | Dans l'historique | La clé OpenAI de la sono |
|---|---|---|---|
| `dadou_hardrive_ros` (= GitHub **public** `dadou_disk_ros`) | non | **oui** : `conf/secret` dans les 2 commits « initial » du 2024-10-12, tous poussés | **OUI, publique depuis octobre 2024**, ainsi que la valeur `google_cloud` |
| `dadou_control_ros` (public) | non (retiré le 2026-07-04, commit « Phase 0 ») | **oui** : `conf/secret` de 2024-03-30 à 2026-07-04 (3 commits) | non (autres valeurs — à lire) |
| robot, vision, utils, DEVICE_WORKSPACE | non | non | non |

Conséquence : **révoquer les 4 identifiants n'est pas une précaution, c'est obligatoire**
— la clé OpenAI et l'identifiant Google Cloud sont lisibles par n'importe qui dans
l'historique de `dadou_disk_ros`. Ensuite, **purger l'historique** des deux dépôts publics
concernés (`git filter-repo`, force-push) — ça réécrit des dépôts publics, donc acte de
David ; les dépôts sont de toute façon destinés à l'archive. La règle « historique déjà
purgé » du `CLAUDE.md` ne valait que pour le dépôt du robot.

**Purge FAITE le 01/11 au soir (décision de David : « purge les 2 historiques maintenant »)** :
sauvegarde `.bundle` de chaque dépôt dans `~/Nextcloud/dev/didier/archives/` ; `git filter-repo
--path conf/secret --invert-paths` sur un clone miroir ; force-push de `main` (+ `master` pour la
télécommande) ; **piège rencontré : les branches Dependabot et leur PR n°1, créées par GitHub sur
l'ancien historique, gardaient le fichier** — branches supprimées, PR fermées ; clone frais depuis
GitHub ensuite : **0 commit avec `conf/secret`** dans les deux dépôts, clé introuvable. Dépôts
locaux réalignés (`reset --hard origin/main`, modifications non commitées mises de côté puis
remises, reflog purgé). **Résidu non effaçable par nous : `refs/pull/1/head` (une par dépôt),
cachée mais existante — seul le support GitHub peut la supprimer** ; et rien n'empêche qu'un
tiers ait copié la clé depuis 2024. **Révocation : David confirme le 01/11 que ces identifiants ne sont plus actifs depuis longtemps** — point clos : clé OpenAI, identifiant Google Cloud, compte SMS (`sms_user` /
`sms_pwd`, qui étaient aussi dans l'ancien `conf/secret` public de la télécommande).
Découverte annexe : un dossier `rpi/` (asoundrc, bashrc, project.service… de 2024) traînait DANS
`.git/objects/95/` de la télécommande (d'où « bad sha1 file ») — déplacé dans les archives.

**Transversal, à chaque lot** : la sim marche en fin de lot (contrainte dure) ; commit
d'instantané avant chaque déplacement ; doc mise à jour dans le lot ; chemin roues
intouché sauf L4, qui repasse par le protocole caméra.

**Ce qui reste ouvert (assumé)** : la forme exacte du protocole d'édition (topic ou
service — L1 le tranche sur pièce) ; le gabarit en détail (L3 le fait émerger de la sono,
pas l'inverse) ; la stabilité de la séance de fumée en CI gratuite (§5.10, repli
décidé : optionnelle plutôt que supprimée) ; la place du concept triangle 3 roues le jour
où il devient un robot (2028+ : il s'appellera `<nom>_*` et vivra dans `packages/`).
