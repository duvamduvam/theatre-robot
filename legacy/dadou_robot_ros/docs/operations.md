# Operations & Rehearsal Checklist

## Déployer / réinstaller un Pi (lot « Ansible nickel », 07/11)

Tout part de `legacy/dadou_utils_ros/ansible/` du checkout à déployer (main ou un worktree :
les chemins sont déduits du playbook, le sha publié est celui de CE checkout). Rien à faire
avant ni après : pas de `chown`, pas de sentinelle, pas de `docker restart`.

```bash
cd legacy/dadou_utils_ros/ansible
ansible-playbook -i hosts deploy-pios.yml -e target_group=vision   # puis robot
./ecart-pi.sh vision                                                 # vert = code 0
```

- Le playbook : système de l'hôte (alias `didier.local`, `/etc/asound.conf`, `.asoundrc`,
  `.bashrc`), rsync du code, sentinelle de build, secrets depuis `~/.config/didier/` du PC
  (échec clair s'il en manque un), `docker compose up -d --force-recreate`, attente des nœuds
  attendus (`noeuds_attendus` dans `hosts`) puis `running` + `restarts=0` — sinon il échoue.
  Durée : ≈ 1 min vision, ≈ 2-3 min robot (build incrémental).
- IP par défaut dans `hosts` (robot .131, vision .151 ; mDNS cassé côté PC) ; une autre IP :
  `-e ansible_host=192.168.1.x`. Utilisateur `pi` et clé `~/.ssh/keys/didier` : dans `hosts`.
- `ecart-pi.sh <groupe>` : (a) le playbook en `--check --diff` doit ne rien changer ; (b) les
  paquets apt manuels, unités activées, entrées de `~`, crontabs et images Docker du Pi doivent
  égaler `attendu/<groupe>.txt` (`?` = toléré). Rouge = écart nommé. Après un changement voulu
  (paquet ajouté par Ansible…) : `./ecart-pi.sh <groupe> --graver`, relire, commiter.
- **Réinstallation d'un Pi reflashé** : `install-pios-lite.yml` (Docker, I²C, service) puis
  `deploy-pios.yml` comme ci-dessus. ⚠️ Tant que les images ARM ne sont pas republiées sur le
  Hub, l'image tirée est la Humble de 2024 : reconstruire sur le Pi
  (`~/scripts/compose-up-pi.sh build`, ≈ 35 min Pi 4) avant le `deploy-pios.yml`.
- Jamais sur le robot aux roues câblées avant le protocole caméra (verrou L1b).
- Historique (gestes manuels d'avant ce lot, et pourquoi chacun existe) : sections
  « Premier déploiement d'une branche… », « Déploiement de main… », « Déploiement de 3b… »
  ci-dessous, et `docs/ansible-ecarts.md` à la racine.
- SSH : alias `r` = pi@robot, `ai` = pi@vision (ils visent `.local`, cassé côté PC : passer
  par l'IP). Log applicatif : `/home/ros2_ws/log/robot.log` DANS le conteneur.

## Namespace par robot — `ROBOT_NAME` (lot L1b, 04/11)
- Tous les nœuds (robot, vision, télécommande, sim) vivent sous
  `/<ROBOT_NAME>/`, défaut **`/didier/`** : `/didier/face`, `/didier/cmd_vel`,
  `/didier/vision/person_box`… La variable est posée par chaque docker-compose
  (`ROBOT_NAME=${ROBOT_NAME:-didier}`) ; robot, vision et télécommande d'un même
  Didier doivent porter le même nom. Restent globaux : `/clock`, `/tf`,
  `/tf_static`, `/rosout`, `/parameter_events`.
- **La CLI ne suit pas** : un nom relatif tapé dans `ros2 topic pub/echo` se
  résout à la racine. Toujours préfixer (`ros2 topic pub /didier/face …`) et
  lancer les `ros2 run` avec `--ros-args -r __ns:=/didier`. Les scripts de
  `conf/scripts/` posent `NS="/${ROBOT_NAME:-didier}"` et préfixent tout.
- Vérif en sim (démarrer la sim avec `ROBOT_NAME=didier2`, puis sans) :
  `docker exec dadou-sim-container bash /home/ros2_ws/validate-namespace.sh`
  — tout topic/nœud sous le namespace, twist_mux configuré, bridge relayé.
- ⚠️ **Vrai robot** : les topics roues ont changé de nom (namespace, pas le
  code) — **protocole caméra à rejouer** (`validate-cmdvel-protocol.sh`, roues
  hors sol) AVANT tout usage au sol. Validé en sim seulement au 04/11.

## Version déployée et catalogue publié (lot L1c, 04/11)
- Le robot publie, latchés, `catalogue` (ce qu'il sait jouer : faces, audios,
  animations, relais, lumières, visuels) et `deploy_sha` (sa version). Nœud
  `catalogue_node`, lancé par `robot_app.launch.py` et par la sim.
- **Badge version** dans le bandeau de la console et de la page scène : `dev` en
  sim, sinon les 7 premiers caractères du sha. **`-dirty`** (badge orange) = l'arbre
  rsyncé n'était PAS un commit propre : le sha seul mentirait, il faut lire le
  `git status` du PC au moment du déploiement pour savoir ce qui tourne.
  Pas de badge = le robot n'a rien publié (nœud absent, ancien déploiement).
- Tâche Ansible (rôle `synchronise`, robot seulement) : écrit `conf/DEPLOY_SHA` au rsync,
  jamais exécutée à ce jour (04/11) — le premier déploiement robot doit afficher son sha.
  `conf/DEPLOY_SHA` est dans le `.gitignore` : il ne doit jamais exister côté PC (la
  sim afficherait un faux sha).
- Vérif en sim : `docker exec dadou-sim-container bash /home/ros2_ws/validate-catalogue.sh`
  (6 familles non vides, sha `dev`, une séquence déposée apparaît en <= 5 s).
  À la main : `ros2 topic echo /didier/catalogue --once --qos-durability transient_local --field msg`.

## Premier déploiement d'une branche sur les Pi hors robot (vécu le 2026-11-04, L1b+L1c)

> Historique. Depuis le 07/11, tous les gestes ci-dessous (`-e …`, `chown`, sentinelle,
> recréation) sont faits par le playbook : voir « Déployer / réinstaller un Pi » en tête.

- Déployer une BRANCHE sans la fusionner : Ansible rsync l'arbre de travail du checkout
  pointé par `local_projects_dir`. Depuis une copie de travail git (worktree) :
  `ansible-playbook deploy-pios.yml -i hosts -e target_group=robot -e local_projects_dir=<worktree>/legacy
  -e packages_dir=<worktree>/packages -e ansible_host=192.168.1.162` (mDNS cassé côté PC :
  passer l'IP ; clé `~/.ssh/keys/didier`). Le sha écrit dans `conf/DEPLOY_SHA` est celui du
  worktree, suffixé `-dirty` si l'arbre diffère du commit.
- ⚠️ **Droits sur un Pi réinstallé** : Docker crée en ROOT les dossiers de montage absents au
  premier `compose up` (`json/`, `medias/`, `robot/`) ; le rsync suivant,
  en `pi`, échoue en code 23 (« Permission denied »). Remède avant tout déploiement :
  `sudo chown -R pi:pi ~/ros2_ws/src` (le conteneur tourne en root, il lit tout).
  À ajouter au playbook d'installation (pas fait).
- ⚠️ **`docker restart` ne relit PAS le compose** : si le déploiement change les volumes ou
  l'environnement (L1a : montage `theatre_contrats` ; L1b : `ROBOT_NAME`), il faut RECRÉER
  le conteneur : `cd ~/ros2_ws/src/<projet>/conf/docker/arm && sudo docker compose -f
  docker-compose-arm.yml up -d` (avec la sentinelle de build posée). Vécu sur le Pi vision :
  après `restart`, colcon n'a compilé que 2 packages et les nœuds sont tombés sur
  `No module named 'theatre_contrats'`.
- ⚠️ `ros2 topic echo --once` sur un topic latché rend souvent VIDE sur le Pi (piège CLI
  connu) : utiliser `--spin-time 6` sans `--once`, ou `curl localhost:8765/api/catalog`.
- Résultat du 04/11 (Pi 4 à 192.168.1.162 en filaire, Pi 5 vision à .151, tous deux HORS
  robot, aucun actionneur) : 16 nœuds sous `/didier/`, `deploy_sha` = sha de la branche,
  catalogue 6 familles via HTTP, twist_mux chargé (remote 100, anim 10, verrou `e_stop` 255,
  `use_stamped` false) et abonné à `/didier/e_stop`, seuls `/rosout` et `/parameter_events`
  hors namespace, `/didier/vision/status` publié par le Pi 5 et vu du Pi 4. `relays_node`
  sans PCF8574 et `person_tracker` sans webcam : attendus hors robot.

## Déploiement de main (L1e-1/2/3a) sur les deux Pi hors robot — 2026-11-07

Pi 4 robot de rechange (4 Go Rev 1.5, série 10000000bec1ed98, carte SD du robot) en 192.168.1.131
**sur le switch** (sur la box il n'était même pas vu en ARP), Pi 5 vision en .151. Aucun
périphérique I²C : aucun actionneur. Séquence : `chown -R pi:pi ~/ros2_ws/src` sur les deux,
`ansible-playbook deploy-pios.yml -e target_group=… -e ansible_host=…`, puis `docker compose up -d`
(recréation, pas restart). Résultat : nettoyage `packages_retires` et `chemins_retires_lib` effectif
(6 anciens `robot_*` et la lib embarquée effacés de src/build/install), 13 packages compilés côté
robot et 4 côté vision, `restarts=0` ; 16 nœuds sous `/didier/`, seuls `/rosout` et
`/parameter_events` hors namespace ; mux : remote 100, anim 10, verrou e_stop 255 ; `deploy_sha` =
`de0ca88…-dirty` (la sentinelle vision posée pendant le rsync, le suffixe dit vrai) ; catalogue 6
familles ; lib importée depuis `install/dadou_utils_ros` sur les deux Pi. Images ARM : ce sont
celles du 04/11, le code est monté ; aucune reconstruction n'a été nécessaire.

## Déploiement de 3b (`theatre_interfaces`) sur les deux Pi hors robot — 2026-11-07 au soir

Même séquence que le matin, plus trois leçons (toutes à intégrer au playbook, voir
`docs/ansible-ecarts.md` à la racine) :
- `hosts` ne donne ni utilisateur ni clé pour robot/vision : `-e ansible_user=pi --private-key
  ~/.ssh/keys/didier`.
- `chemins_retires_lib` efface `build/` et `install/` de robot ET vision à CHAQUE passage : la
  sentinelle est donc obligatoire à chaque déploiement, et son nom diffère — robot
  `src/robot/robot/change`, vision `src/vision/vision/CHANGE` (majuscules). Sans elle, la vision
  est morte au démarrage (`Package 'vision' not found`).
- L'image ARM du robot (04/11) précédait le renommage L1e-2 : elle COPIAIT encore les anciens
  `robot_*` dans `src/`, compilés à côté des `didier_*` (déjà vrai au déploiement du matin, passé
  inaperçu). Remède : `sudo docker compose -f docker-compose-arm.yml build` sur le Pi (≈ 25 min),
  puis rejouer le playbook (`packages_retires` nettoie `build/`/`install/` de l'hôte), sentinelle,
  `up -d --force-recreate`. Contrôle : `ls /home/ros2_ws/src /home/ros2_ws/install` dans le
  conteneur ne montre aucun `robot_*` (seul `robot` = le cœur, jusqu'à 3c).

Résultat : robot 10 packages compilés, 17 nœuds sous `/didier/` (vision comprise), seuls
`/rosout` et `/parameter_events` hors namespace, mux remote 100 + verrou e_stop 255, catalogue 6
familles, `deploy_sha` = `143ff37…-dirty` (un fichier non commité dans l'arbre, le suffixe dit
vrai), `restarts=0` ; vision 4 packages (`dadou_utils_ros`, `theatre_contrats`,
`theatre_interfaces`, `vision`), `vision_status` vu du robot. Secrets de la vision sauvegardés
sur le PC dans `~/.config/didier/` (ils n'existaient que sur le Pi).

## Réinstallation d'un Pi vierge (vécu le 2026-11-04)

> Historique : la procédure actuelle est « Déployer / réinstaller un Pi » en tête de fichier.
- `ansible-playbook -i hosts install-pios-lite.yml -e target_group=robot` depuis
  `dadou_utils_ros/ansible`, puis retirer l'ancienne empreinte SSH de `robot.local`.
- ⚠️ Le service tire `dadouuu/dadou-robot-arm:latest` du Hub : image Humble de 2024, inutilisable.
  Construire ensuite sur le Pi : `~/scripts/compose-up-pi.sh build` (environ 35 min), puis
  `sudo` pour créer `robot/change` (fichier root) si la compilation doit être relancée.
- Avant de remettre le Pi sur le robot : fiches servos débranchées, moteurs de roues coupés.

## Tests hôte de la lib partagée `dadou_utils_ros` (lot L1e-3a, 07/11)

La lib est un package de `packages/` (plus de symlink dans les dépôts legacy) ; ses tests
et son `conftest.py` sont dans `packages/dadou_utils_ros/test/`. Depuis la racine du
mono-dépôt, avec le venv du robot :

```bash
cd packages/dadou_utils_ros && ../../legacy/dadou_robot_ros/.venv/bin/python -m pytest -q -o addopts=
```

Les `conftest.py` des dépôts legacy (vision, télécommande), de `packages/didier_core/test/` (le
cœur, depuis L1e-3c) et de `packages/didier_jeu` y ajoutent
`packages/dadou_utils_ros` au `sys.path` : pour vérifier que c'est bien CETTE copie qui est
importée, `python -c 'import conftest, dadou_utils_ros; print(dadou_utils_ros.__file__)'`
depuis chaque dépôt doit afficher `packages/dadou_utils_ros/dadou_utils_ros/__init__.py`.
Au déploiement, Ansible efface les anciennes copies `src/{robot,vision,controller}/dadou_utils_ros`
(liste gravée `chemins_retires_lib`) ; si un Pi garde un `build/` ou `install/` d'avant, un
`colcon build` complet les reconstruit.

## Messages ROS : `theatre_interfaces` (lot L1e-3b, 07/11)

Le package des messages s'appelle `theatre_interfaces` (ex `robot_interfaces`, renommé en
L1e-3b ; `StringTime` et les autres noms de messages sont inchangés). En CLI :
`ros2 topic pub --once /didier/face theatre_interfaces/msg/StringTime "{msg: '\"calib\"'}"`.
Au déploiement, Ansible efface `src/`, `build/` et `install/robot_interfaces` des Pi
(`packages_retires`) avant de pousser `src/theatre_interfaces` ; les compose ARM montent
un nouveau dossier : **recréer** le conteneur (`docker compose up -d`, pas `restart`) avec la
sentinelle de build posée, sinon `theatre_interfaces` est absent du conteneur et les nœuds
tombent à l'import (même piège que `theatre_contrats` au 04/11 ; pas encore vécu ici).
Tests hôte : les modules ROS sont factices (`sys.modules["theatre_interfaces.msg"]`), rien
à installer ; le garde-fou `test_arborescence.py` rougit si un fichier de code ou de conf
cite encore l'ancien nom.

## La vision `didier_vision` (lot L1e-3d, 08/11)

L'ex-package `vision` est `packages/didier_vision/` (code `didier_vision/`, tests `test/`,
launch `launch/vision.launch.py`) ; exécutables, nœuds et topics inchangés. Les données
(`conf/`, `medias/`, `db/`, `models/`, `mediamtx/`) restent dans `legacy/dadou_vision_ros/`
(`DIDIER_VISION_DATA_DIR`). Il exige SON venv (le venv robot n'a pas `sqlobject`) :

```bash
cd packages/didier_vision && ../../legacy/dadou_vision_ros/.venv/bin/python -m pytest -q -o addopts=
```

Banc x86 : `legacy/dadou_vision_ros/conf/docker/x86/build-x86.sh` (contexte nommé
`didier_vision`), puis vider `workspace/{build,install,log}` (l'ancien `install/vision`
n'a plus de raison d'exister) et poser `touch packages/didier_vision/change`.

## Le cœur `didier_core` (lot L1e-3c, 07/11)

L'ex-package `robot` est `packages/didier_core/` (code `didier_core/`, tests `test/`) ;
exécutables, nœuds et topics inchangés. Tests hôte, depuis la racine du mono-dépôt :

```bash
cd packages/didier_core && ../../legacy/dadou_robot_ros/.venv/bin/python -m pytest -q -o addopts=
```

(il n'y a plus de tests ni de `conftest.py` à la racine de `legacy/dadou_robot_ros/`). Les
DONNÉES (`json/`, `medias/`, `db/`, `conf/`) restent dans `legacy/dadou_robot_ros/`, montées
sous `/home/ros2_ws/src/robot/` ; `robot_config.py` en lit la racine dans `DIDIER_DATA_DIR`
(posée par les compose, et par le `conftest.py` vers `legacy/dadou_robot_ros/`). En CLI :
`ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier`. Sentinelle de build :
`src/didier_core/change` (sur le PC `packages/didier_core/change`, gitignorée ; `make build` de
`conf/Makefile` la pose). Au déploiement, Ansible efface l'ancienne forme (`src/robot/robot`,
`src/robot/{setup.py,package.xml,setup.cfg,resource,test}`, `build/robot`, `install/robot` —
liste gravée `chemins_retires_robot`, seulement si présente) AVANT de pousser `src/didier_core`.
⚠️ L'image ARM COPIE le code : après ce lot, la reconstruire sur le Pi
(`sudo docker compose -f docker-compose-arm.yml build`) puis la pousser sur le Hub. Contrôle
dans le conteneur : `ls /home/ros2_ws/src /home/ros2_ws/install` ne montre plus aucun `robot`.

## Calibration & verification tooling
- **Face LED patterns** (expressions, publish on `face`): `"calib"` (digits
  123 + E + eye F — fine orientation), `"calib-couleurs"` (one colour per
  matrix — wiring permutation), `"calib-bords"` (border rings — any start
  offset breaks a ring, no left/right interpretation needed). The wiring is
  locked by `test_image_mapping.py`; re-run the patterns after ANY change on
  the face path. Publish example:
  `ros2 topic pub --once /didier/face theatre_interfaces/msg/StringTime "{msg: '\"calib\"', time: 0, anim: false}"`
- **Brightness** (non-persistent, default 0.05):
  `{msg: '{"brightness": 0.15}'}` on `robot_lights` — 0.15 is comfortable to
  read patterns, LED patterns are unreadable on webcams (fixed-focus + PWM
  flicker): read them with human eyes.
- **Wheels**: camera protocol replay `conf/scripts/validate-cmdvel-protocol.sh`
  (run inside the robot container, wheels OFF the ground).
- Before any face calibration session: **stop `chat_node`** on the vision Pi
  (it overwrites `face` on any ambient noise):
  `ssh pi@192.168.1.151 'sudo docker restart dadou-vision-container'` restores it.

## Web interface in sim (W0 + W3 sim)
- `cd conf/docker/sim && WEB=true docker compose -f docker-compose-sim.yml up -d`
  then open `http://localhost:8765` (`WEB_PORT` overrides it — the container
  runs on host networking, 8088 was already taken by Superset on the dev PC).
  Add `ANIMATIONS=true` alongside `WEB=true`
  to also trigger sequences from the UI's "Animations" grid (otherwise
  `animation` publishes but nothing replays it).
- Console = colonne DIRECT (vidéo caméra embarquée + pad de pilotage + manette +
  STOP) et colonne CONTENUS (recherche + animation/face/audio/lumières, panneau
  technique servos/relais/gaze/système/calibration). La whitelist `cmd` n'expose
  ni roues ni e_stop — voir [`interfaces.md`](interfaces.md) §"API web".
- **Conduire dans Gazebo (SIM-ONLY, W3)** — deux conditions, dans cet ordre :
  1. Lancer la console AVEC le pilotage : `WEB=true WEB_DRIVE=true docker compose
     -f docker-compose-sim.yml up -d`. `WEB_DRIVE` active le publisher
     `cmd_vel_web` (twist_mux prio 50) ; sans lui le pad reste grisé.
  2. Lancer la chaîne roues À LA MAIN dans le conteneur (elle n'est PAS démarrée
     par le launch sim, par prudence — pas de mouvement automatique) :
     `docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh
     && source /home/ros2_ws/install/setup.bash && ros2 launch didier_drive
     drive.launch.py use_sim_time:=true'`. Le pad/la manette bougent alors Didier
     dans Gazebo (la télécommande physique, prio 100, garderait la main).
- ⚠️ **SIM-ONLY** : rien de ce chemin ne s'active sur le vrai robot. Le passage
  au réel (roues au sol) reste conditionné au test scénique au sol (feuille de
  route §1) PUIS au protocole caméra roues hors sol (etude-interface-web.md §6,
  W3). `ROS_DOMAIN_ID=43` isole la sim du vrai Didier (domain 42).
- ⚠️ **Ne pas fermer la fenêtre Gazebo** : elle porte AUSSI le serveur de
  simulation (gz tourne serveur+GUI dans le même process). La fermer tue la
  sim : plus de robot, plus de caméra (la console web affiche « pas de vidéo »
  et réessaie toutes les 5 s). Relance : `docker compose ... up -d
  --force-recreate` avec les mêmes variables.

## Banc PC — parole et caméra RÉELLES, corps simulé (créé 2026-09-13)

Créé pendant l'immobilisation du robot (Pi 4 fumé le 12/09, convertisseurs
24V→5V en commande) : la perception et la conversation tournent avec le VRAI
code du Pi 5 sur le PC (webcam USB ; **micro = le ReSpeaker du robot branché
sur le PC, sortie = casque Bluetooth de retour**, cf. `asound-pc.conf` du dépôt
vision — câblage du 13/09 au soir, corrigé ici le 14/10 : le texte parlait
encore de la Scarlett), le corps est le Didier de Gazebo. Tout est sur
`ROS_DOMAIN_ID=43` : rien ne peut atteindre le vrai robot.

⚠️ Ce banc ne REMPLACE pas le protocole physique chat_node V2 (chantier 0) :
les seuils audio sont absolus et dépendent de la machine (le gate calibré ici
ne vaut pas sur le Pi 5), et le ronflement secteur du Pi reste à régler par
l'alim batterie. Le banc sert à travailler CONTENU et COMPORTEMENT
(conversation, personas, didascalies, suivi) en attendant le matériel.

**1. La sim (corps)** — depuis `conf/docker/sim/` de ce dépôt :
```bash
ANIMATIONS=true FACE=true WEB=true docker compose -f docker-compose-sim.yml up -d
```
- `FACE=true` : aperçu web du visage LED sur `http://localhost:8766` — c'est le
  rendu des didascalies de la conversation, invisible dans Gazebo (les matrices
  n'y sont pas modélisées). Exécute le vrai pipeline `Face`/`ImageMapping`.
- `WEB=true` : console de régie `http://localhost:8765` (fenêtre sur la sim en
  HEADLESS, boutons animations/face/gaze).
- Suivi de personne et gaze, à lancer À LA MAIN dans le conteneur (prudence
  habituelle : pas de mouvement automatique) :
```bash
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_drive drive.launch.py use_sim_time:=true'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 run didier_core person_follower --ros-args -r __ns:=/didier'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier'
```
  (puis activer le suivi roues : topic `follow` « on » — il démarre OFF.)

**2. La perception + la parole (tête)** — depuis
`../dadou_vision_ros/conf/docker/x86/` :
```bash
./build-x86.sh                                        # 1re fois seulement (long)
CHAT=true docker compose -f docker-compose-x86.yml up -d
```
- MÊME image que le Pi 5 (Dockerfile-arm réutilisé tel quel, base multi-arch) ;
  `person_tracker` lit la webcam `/dev/video0`, publie `/didier/vision/person` (gaze)
  et `/didier/vision/person_box` (suivi roues) ; `CHAT=true` lance `chat_node`
  (micro → whisper → OpenRouter → piper → sortie audio).
- Les alias ALSA `casque_mic`/`mixette` sont fournis par `asound-pc.conf`
  (monté dans le conteneur) : `casque_mic` = ReSpeaker en `hw:Array` (direct,
  sans PipeWire, pour mesurer la même chose que le robot), `mixette` = casque
  Bluetooth via le plugin `pulse` (nœud bluez par adresse MAC). AUCUN
  paramètre du code ne change entre le Pi et le banc.
- ⚠️ Ne PAS arrêter PipeWire : c'est lui qui sert le casque Bluetooth (la
  sortie). Si le casque n'est pas connecté, `aplay` échoue et le tour est
  abandonné proprement (le texte reste visible sur la page scène, §Séance).
  « Device or resource busy » sur le micro = une appli hôte tient le ReSpeaker.
- Sans ReSpeaker branché, le micro est « mort » (backoff 5 s en boucle, log
  WARNING) mais le **clavier de la page scène** (`chat_text`) fonctionne quand
  même : c'est le mode de secours pour travailler le texte sans matériel.
- ⚠️ Clé requise : `openrouter_key` dans `conf/secret` du dépôt vision
  (déjà en place sur le PC de dev).
- ⚠️ Bug REPO_ROOT (le même que sur le Pi, cf. CLAUDE.md vision) : en install
  colcon, la config cherche conf/ et medias/ dans site-packages. Contournement
  appliqué au banc le 13/09 — mêmes symlinks que sur le Pi, dans l'install
  space (persistant, c'est le workspace monté ; à REFAIRE si un colcon build
  les efface — symptôme : chat meurt sur « Secret LLM manquant ») :
  `docker exec dadou-vision-x86-container bash -c 'sp=/home/ros2_ws/install/vision/lib/python3.12/site-packages; ln -sfn /home/ros2_ws/src/vision/conf $sp/conf; ln -sfn /home/ros2_ws/src/vision/medias $sp/medias'`
  **Obsolète depuis L1e-3d (08/11)** : `vision_config` lit la racine des données dans
  `DIDIER_VISION_DATA_DIR` (posée par le compose), plus de calcul depuis l'emplacement du
  package — ces symlinks ne servent plus à rien (l'install-space est `install/didier_vision`).
- ⚠️ **Le code qui tourne est celui de `workspace/install`, pas des sources
  montées** (ament_python COPIE les sources au build) : après tout changement
  de `packages/didier_vision/`, poser la sentinelle `touch packages/didier_vision/change` puis
  redémarrer le conteneur (vécu le 14/10 : chat_node tournait avec le code du
  13/09 malgré les sources à jour). Et **après un rebuild d'IMAGE**
  (`build-x86.sh`), vider `workspace/{build,install,log}` avant de relancer :
  le `build/` de l'ancienne image référence des libs qui n'existent plus
  (`libfastcdr.so.2.2.7` → `robot_interfaces` échoue, chat_node reste
  l'ancien). Puis refaire les symlinks ci-dessus.

**Ce qu'on voit alors** : on se place devant la webcam → le Didier de Gazebo
tourne la tête (gaze) et pivote/avance (suivi, si activé) ; on parle dans le
micro → réponse dans les enceintes, gestes « parle » dans Gazebo
(`ANIMATIONS=true` requis), didascalies sur l'aperçu visage 8766.

## V-R3 : pourquoi il a baissé le 06/11, et ce qui l'a rendu fiable (élucidé le 06/11 au soir)

Trois séances à 18-19/21 (avant ET après le déménagement L1e-1) là où le 04/11 donnait 21/21.
Deux causes distinctes, toutes deux mesurées :

1. **Gazebo tournait à 0,49 du temps réel** (sim headless sans GPU : les deux caméras 640×480 à
   15 et 10 Hz sont rendues par le CPU, le serveur gz à 150 % de CPU). Or le régisseur déroule le
   scénario à l'HORLOGE MURALE (voulu : c'est l'horloge du vrai robot) alors que Didier avance à
   l'horloge simulée → à moitié vitesse il manquait l'arrivée de ~7 m. Mesures : caméras à 5 Hz
   chacune → 0,88 ; pas de physique 4 ms seul → 0,54 (inutile, et risqué pour les servos).
   **Correctif : caméras à 5 Hz** (`dadou_robot_gz.urdf.xacro`, le pont web ne sert que ~5 i/s).
   Le facteur dépend de la charge du PC : vérifier qu'il reste ≥ 0,8 si le test rebaisse (sonde
   rclpy sur /clock, 20 s).
2. **Les captures `ros2 topic echo` sans TYPE restaient vides** : le CLI interroge d'abord le graphe,
   ne voit pas encore l'éditeur, sort aussitôt. Avec le type explicite il s'abonne tout de suite
   (premier message en 0,8 s). Et un topic LATCHÉ exige en plus `--qos-reliability reliable` : un
   lecteur best-effort (défaut du CLI avec type) ne reçoit pas l'historique. **Correctif :** type
   sur chaque `echo` de `validate-rehearsal-chantiers.sh` + reliable sur `route_state`.
   À reporter dans `validate-rehearsal-route.sh` et `-faults.sh` (même `num()`), pas fait.

Résultat : 21/21 le 06/11 à 23:16 (x final 142,1 m en 575 s, 9 arrêts-lubies sur 9 capturés).
Rappel : le script EXIGE que drive, rehearsal (scenario chantiers) et gaze_follower soient lancés
AVANT (sinon « PRÉCONDITION … absent », code 2).

## Séance « Chantiers » — répétition simulée complète (lot R3, 14/10)

Le trajet des Nefs à la grue Titan grise (`docs/etude-repetition-simulee.md`
§13) : Didier chemine seul, 20 bugs réels tombent au hasard, 30 objets du
chemin déclenchent ses lubies, David joue au casque et à la page scène.
Tout sur le domaine **43**.

**1. Le corps + la régie** (`conf/docker/sim/`, HEADLESS recommandé) :
```bash
WORLD=chantiers REHEARSAL=true FACE=true WEB=true ANIMATIONS=true HEADLESS=true docker compose -f docker-compose-sim.yml up -d
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_drive drive.launch.py use_sim_time:=true'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=chantiers'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier'
```
- `REHEARSAL=true` : la page scène obtient les boutons route / vitesse /
  séance (SIM-ONLY, jamais sur le robot). `seed:=N` sur le launch rehearsal
  pour rejouer exactement la même séance (même tirage de bugs et de lubies).
- Page scène, deux caméras : « Caméra de Didier (Gazebo) » = le rendu du monde
  simulé (`camera/image_raw`) ; « Ce que Didier voit (webcam) » = l'image que
  person_tracker analyse (webcam du PC, `camera/image_raw/compressed`) et sur
  laquelle le LLM de réflexion raisonne. Ce 2e panneau (lecture seule, paramètre
  `perception_topic`) n'apparaît que si le pont l'annonce ; en sim `sim.launch.py`
  le passe d'office.
- Page scène, quel panneau montre quoi : « Didier vu de l'extérieur » = caméra de
  POURSUITE Gazebo (3 m derrière, 2 m au-dessus, tourne avec lui ; `camera_ext/image_raw`,
  `/exterior`, paramètre `exterior_topic`, SIM-ONLY, lecture seule) pour juger comment il
  bouge ; « Caméra de Didier (Gazebo) » = ce que voit son buste (`/video`) ; « Ce que Didier
  voit » = l'image analysée par la perception (`/perception`). Le panneau extérieur exige
  un REDÉMARRAGE de la sim entière (le link et le capteur sont dans le robot spawné).

**2. La tête** (`../dadou_vision_ros/conf/docker/x86/`) :
`CHAT=true docker compose -f docker-compose-x86.yml up -d` — puis, depuis la
page scène, persona **mauvaisefoi**.
- Au **casque Bluetooth** (M50, profil HFP — réglages du 22/10, banc PC
  seulement, le Pi n'est pas touché) : micro atténué de 12 dB dans
  `asound-pc.conf` (sinon le gate anti-sono bloque la voix) et
  `CHAT_VAD_FACTOR=6` (le souffle du micro BT fluctue, à 1,3 la fin de phrase
  n'est jamais détectée). `CHAT_PARTENAIRE=David` : Didier sait qu'il parle à
  David, pas à un passant.
  **08/11** : atténuation passée à **×0,075** (la voix dépassait encore le seuil
  « sono » du gate) et `CHAT_MICRO_CONFIANCE=true` (défaut du compose x86) : au
  casque c'est David qui parle, le gate « source audio vivante » n'est pas construit —
  sinon chaque geste muet du sélecteur de jeu fermait le micro (1 phrase sur 10).
  Ligne attendue au démarrage : « micro de confiance : gate … désactivé ».
- ⚠️ Tant que l'image vision n'est pas rebâtie avec `av>=14,<15`, chaque
  `compose up` qui RECRÉE le conteneur remet PyAV 19 (whisper casse, STT
  vide) : `docker exec dadou-vision-x86-container pip install
  --break-system-packages --only-binary=:all: "av>=14,<15"` puis
  `docker restart dadou-vision-x86-container`.

**Depuis un téléphone ou une tablette** : `python3 conf/scripts/rehearsal/publier_nom_sim.py`
(sur le PC, laisser tourner) publie **`didier-sim.local`** → la page devient
http://didier-sim.local:8765/scene sur tout le réseau. Sans sudo ni avahi-utils
(D-Bus direct vers le démon avahi). ⚠️ Jamais `didier.local` : c'est le nom du
VRAI robot (alias publié par le Pi, visé par la télécommande) — le script le refuse.

**Son et micro de Didier** (casque Bluetooth) — voir qui est branché à quoi, et choisir :
```bash
python3 ../dadou_vision_ros/conf/docker/x86/audio_banc.py               # état
python3 ../dadou_vision_ros/conf/docker/x86/audio_banc.py choisir M50   # ou un autre casque, ou « defaut »
```
`choisir` connecte le casque, le met en profil casque+micro, règle la tête et la redémarre.

**3. La page scène** : http://localhost:8765/scene — caméra de Didier, visage
LED en direct, conversation (ce que Didier a *compris* et ce qu'il dit), un
champ texte pour lui parler au clavier, une consigne de jeu à la main. Puis
**route on**, vitesse au slider (ou au fader de la vraie télécommande en
`ROS_DOMAIN_ID=43 SLIDERS_PROFILE=repetition`), **séance start**. La page
n'affiche **ni** les pannes **ni** les lubies tirées : David joue sans savoir.
- **Badges de retour (31/10)** : dans le groupe Séance, « séance : en attente /
  en cours / terminée » (topic latché `rehearsal/state`, publié par le
  régisseur) — inutile de recliquer START tant qu'il ne dit pas « en cours ».
  À côté de « route en marche », un badge orange **« arrêt vocal — bouger le
  curseur ou dire « avance » en séance »** apparaît quand un « stop » dit à voix
  haute retient Didier (route_speed 0) : le « go » vocal est ignoré hors
  séance, d'où un Didier figé sous un « route en marche » trompeur. Il se lève
  en bougeant le curseur, par un « avance » en séance, ou à la fin/abort de la
  séance. Ces badges ne portent jamais d'info de panne ni de lubie.
- **Vision (31/10)** : groupe « Vision » (sim seulement) — boutons Webcam ON/OFF
  (`camera_enable`) et badge d'état réel (`camera_state`, latché par la tête
  vision). Caméra coupée : le panneau « Ce que Didier voit » affiche « caméra
  coupée » au lieu d'une image figée. **Source des images** : boutons « Webcam
  PC » / « Caméra Gazebo » (`camera_source`, à chaud), surlignage d'après la
  source réellement utilisée (`camera_source_state`) ; le bouton Gazebo n'apparaît
  que si la vision annonce « gazebo » (`camera_sources`, ex. `["webcam","gazebo"]`).
  Le titre du panneau indique la source courante : « (webcam) » ou « (Gazebo) ».
- Deux bugs demandent une **réaction de David** : après un *reboot sans
  reprise* (Didier reste planté, route OFF après le respawn), c'est lui qui
  relance (**route on**) — et tant que la route est OFF, un reboot suivant ne
  relance pas non plus (politique du régisseur : jamais contre une route OFF).
  Une lubie se ferme en **bougeant** le fader/slider (une valeur identique ne
  ferme rien), ou en attendant (60 s).

**Ticket « Noter un problème » (08/11)** : champ du bandeau de la page scène, utilisable sans
la main. Le pont écrit un JSON dans `log/tickets/` (texte, heure, topics visibles — jamais
les topics masqués). En sim, `log/` est monté sur le PC : `conf/docker/sim/workspace/log/`
(gitignoré), il survit aux recréations du conteneur. Le ramasseur qui les range avec les
journaux reste à faire (`docs/seances/2026-11-08-a1-casque.md` #11).

**4. Après** : le journal JSONL de la séance est dans
`/home/ros2_ws/log/rehearsal/` du conteneur sim (ce qui a été tiré, quand) ;
`conf/scripts/rehearsal/carte_seance.py` en fait la carte.

**Vérification technique rejouable** (sans la tête, dans le conteneur, étapes 1
faites, route OFF) : `docker exec dadou-sim-container bash /home/ros2_ws/validate-rehearsal-chantiers.sh`
(≈ 10 min : arrivée au pied de la Titan, POI dans l'ordre, lubies tirées =
journal, fermeture au fader, pannes chat publiées, couverture des 20 bugs).

**Vue 3D à la demande** : `docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && gz sim -g'`
(clic droit sur Didier → Follow ; ne pas fermer la fenêtre pendant la séance).

⚠️ **Piège du PC de dev (14/10) : le CLI `ros2` est capricieux, les nodes non.**
Avec ~50 conteneurs et autant d'interfaces, FastDDS logue des erreurs
multicast (`Error setting socket option (IP_ADD_MEMBERSHIP)`) et un
`ros2 topic pub -1` / `ros2 topic echo --once` lancé à la main (topic préfixé
`/didier/…` depuis L1b) part souvent
AVANT d'être découvert : `route on` perdu, Didier immobile, `ros2 topic list`
incomplet — alors que les nodes entre eux (régisseur, route_driver, chat_node,
pont web) se parlent sans perte. Règles : commander la séance depuis la **page
scène** ou la télécommande (publieurs longue durée), pas au CLI ; dans un
script, envoyer des **salves** (`-t 10 -r 2`) de commandes idempotentes et
vérifier **par l'effet** (odométrie, journal), jamais par un `echo --once`.

## Séance A1 — le sélecteur de jeu décide (lot A1, 02/11, SIM-ONLY)

Le sélecteur de jeu (`theatre-robot/packages/didier_jeu`, spec
`theatre-robot/docs/spec-A1-selecteur-de-jeu.md`) est **le seul décideur du
corps**. La bouche dépose des intentions, son « stop » est relayé sans arbitrage,
et le régisseur arbitre puis ordonne. Même monde, même page scène que la séance
Chantiers ; deux différences : `jeu:=true` (le régisseur écoute `jeu/chat_move`)
et un **scénario vide** `jeu-a1` (0 bug, 0 lubie : les lubies viennent du
sélecteur). Tout se passe sur le domaine **43** ; `jeu_node` refuse de démarrer ailleurs.

```bash
cd conf/docker/sim
WORLD=chantiers REHEARSAL=true FACE=true WEB=true ANIMATIONS=true HEADLESS=true docker compose -f docker-compose-sim.yml up -d --build
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_drive drive.launch.py use_sim_time:=true'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 run didier_core gaze_follower --ros-args -r __ns:=/didier'
```
- Le launch `jeu:=true` démarre **lui-même** le sélecteur (`jeu_node`, respawn).
  Ne pas le lancer à part. Si le répertoire de séquences est illisible, il
  démarre en **mode dégradé** (relais stop/go seul, ligne `degrade` au journal) :
  l'arrêt vocal passe toujours.
- `--build` est nécessaire une fois : l'image doit contenir `ros-jazzy-py-trees`.
  Le code de `didier_jeu` est monté en volume et rebâti à chaque démarrage.
- Page scène http://localhost:8765/scene : **Route ON**, **Séance START**. La séance
  doit être startée, car le régisseur ignore un « go » hors séance, et c'est par
  ce « go » que Didier repart après SES arrêts. Le panneau **« Jeu »** (sim
  seulement) montre l'intention en cours avec son pourquoi et le temps restant,
  les jauges, les 20 dernières lignes du journal, et sept boutons : va là
  (objet, ou dernière piste vue), joue avec lui, ignore, reviens, plus lent,
  STOP et GO (deux boutons distincts). La page envoie un battement (`presence`)
  tant que l'onglet est visible et qu'elle a la main. **STOP CONTENUS** arrête
  aussi le sélecteur (stop de David). Un « go » dit à voix haute ne relance
  jamais un stop posé à la console : seul GO le fait.
- **Reprise** : après un arrêt de sa part, Didier repart seul après **90 s de
  silence**, et toute parole entendue relance le compte. Jamais après un stop ni
  une Route OFF de David.
- **Perception** : en A1, elle est **scriptée**. Une personne se simule à la main :
  `ros2 topic pub -r 16 /didier/vision/person_box geometry_msgs/msg/PointStamped "{point: {x: 0.3, y: 0.4, z: 0.9}}"`.
  On peut aussi brancher la tête vision et sa webcam.
- **Journal « pourquoi »** (à relire avec David, ligne par ligne) :
  `/home/ros2_ws/log/jeu/<horodatage>_<pid>_jeu.jsonl` dans le conteneur
  (format boîte noire, une ligne par décision, maintien, refus ou relais).
- Les réglages (`packages/didier_jeu/config/reglages.yaml`) sont des valeurs de
  départ, gravées en test : un réglage se change donc en touchant
  `test_reglages.py`.

**Vérification rejouable** (dans le conteneur, les quatre commandes ci-dessus
lancées ; ≈ 16 min ; le script fait lui-même la mise en route et échoue s'il
ne lit pas `route_state`) :
`docker exec dadou-sim-container bash /home/ros2_ws/validate-jeu-a1.sh`.
Le script contient sa propre perception scriptée et joue la console et la bouche ;
il rend T1-T7 (spec §6) et un code de retour. La séance Chantiers *sans*
`jeu:=true` reste vérifiée par `validate-rehearsal-chantiers.sh` (V-R3).

## Fumée automatique — la sim rejouée toute seule (lot F, 07/11)

Un script shell (`conf/scripts/fumee.sh`, zéro token) rejoue sur le **checkout de main** toutes
les épreuves de la sim et compare chaque compteur à une valeur **gravée en tête du script** :
namespace 5, catalogue 4, `parle` 3 états, V-R3 21, A1 14. Il **mesure, il ne juge pas** ; un
agent n'intervient que pour lire une page rouge. Pourquoi : l'environnement bouge sans commit
(paquets Gazebo, Docker, charge du PC — V-R3 est tombé de 21/21 à 18/21 le 06/11 sans
régression du code) et chaque lot payait ≈ 1 h d'épreuves.

**Ordre, arrêt au PREMIER rouge** (les suivantes restent « non lancée » sur la page) :
image sim (reconstruite seulement si `conf/docker/sim` a changé depuis la dernière fumée verte,
ou si elle manque) → sim headless domaine 43 + colcon → **sonde RTF 20 s** (rouge si < 0,8 : le
reste ne serait pas fiable) → `validate-namespace.sh` → `validate-catalogue.sh` → animation
`parle` (`animation_state` `""` → `"parle"` → `""`, jouée en rclpy) → chaîne roues + régisseur +
regard puis `validate-rehearsal-chantiers.sh` (V-R3) → sim relancée, `validate-jeu-a1.sh`
(A1). ≈ 40 min.

**Trois façons de la lancer**
- `fumee.sh --si-due` : appelé toutes les 30 min par la minuterie (voir plus bas). Ne fait RIEN
  si rien n'est dû ; dû = un commit est entré dans `main` après le sha gravé dans la dernière
  page VERTE (les commits de `docs/fumee/` ne comptent pas, sinon chaque page rappellerait la
  suivante), OU 7 jours sans fumée verte. Dû mais PC occupé → note « reporté » dans
  `~/.local/state/didier-fumee/journal.log` et sort 0 : **jamais de plage à réserver**, l'essai
  de 30 min plus tard réessaie. Sont reportés : charge 1 min > nb de cœurs × 0,5 (seuil
  `FUMEE_CHARGE_MAX`, 16 sur ce PC de 32 cœurs ; le RTF reste le vrai juge), RTF < 0,8 après
  démarrage de la sim, **conteneur `dadou-sim-container` déjà présent** (la sim de quelqu'un :
  jamais touchée), checkout qui n'est pas sur la branche `main`. Due depuis plus de 2 jours et
  toujours reportée → `notify-send` + ligne « RAPPEL » au journal (au plus toutes les 12 h).
- `fumee.sh` : à la main, déroule même si pas due. Le RTF reste juge (rouge si < 0,8).
- `fumee.sh --et-dodo` : fumée forcée **puis `systemctl poweroff`** — à lancer en allant se
  coucher, le PC s'éteint seul ≈ 45 min après, page commitée avant l'extinction. Refuse (code 2,
  n'éteint pas) si une sim existe déjà ; si la minuterie a une fumée en cours, il l'attend (90 min
  max) puis éteint sans en refaire une. **Essai à blanc : `FUMEE_DRY_POWEROFF=1`** remplace le
  poweroff par un `echo`. **Garde-fou : l'extinction exige un vrai terminal** (stdin ET stdout
  interactifs) ; sans terminal (agent, minuterie, script) `dodo()` refuse et l'écrit au journal.
  Raison : le 07/11 à 21:07 un essai « à blanc » lancé sans `FUMEE_DRY_POWEROFF` a éteint le PC
  de David. Pour tester une extinction : un faux `systemctl` en tête du PATH, jamais le vrai
  (`test_fumee.py` le fait).

**Lire une page** : `docs/fumee/index.html` (la plus récente en tête) → `AAAA-MM-JJ.html` : sha
testé (`-dirty` = l'arbre de David n'était pas propre, ce qui a été testé n'est pas un commit),
durée, RTF, charge, une ligne par épreuve avec son compteur (`21 / 21 OK, 0 KO`) et son journal.
Les journaux sont COPIÉS hors du conteneur avant son arrêt : `docs/fumee/journaux/<id>/`
(`<épreuve>.log`, `conteneur-<phase>.tar.gz` = logs ROS + journaux de séance + sortie du conteneur,
les fichiers > 1 Mo réduits à leurs 3000 dernières lignes) et **`resultat.json`**, qui est la vérité
(la page n'en est que le rendu : `python3 conf/scripts/fumee_page.py pages --sortie docs/fumee`
la régénère). **Avant d'accuser une épreuve rouge, regarder le RTF** : sous 0,8 le régisseur
(horloge murale) manque l'arrivée. Un arrêt propre (Ctrl-C, SIGTERM) en cours de route laisse une page
rouge « interrompue » ; un SIGKILL ou une coupure de courant n'en laisse aucune.

**Ce que le script ne fait jamais** : modifier l'arbre de travail hors `docs/fumee/` (le seul
commit est `git commit -- docs/fumee`, sans `-a` ni `add .`, sans push) ; lancer quoi que ce soit
hors du domaine ROS 43 (forcé dans la commande, revérifié dans le conteneur) ; laisser la sim
tourner (arrêt en `trap EXIT`, quoi qu'il arrive). Seule trace transitoire : `validate-catalogue.sh`
dépose puis supprime `json/sequences/tmp-l1c/` dans l'arbre.

**Pièges connus**
- La sim « headless » a quand même besoin d'une **autorité X valide** (le compose monte
  `XAUTHORITY`) : sans elle Gazebo segfault au rendu (« Authorization required », exit 139, aucun
  `/clock`). Sous la minuterie, GNOME importe `DISPLAY`/`XAUTHORITY` dans l'environnement
  utilisateur de systemd ; à défaut le script cherche `/run/user/UID/.mutter-Xwaylandauth.*`.
  Session fermée = démarrage rouge, avec la cause dans `demarrage.log`.
- `validate-namespace.sh` lit `topic info` via le démon ros2, qui naît VIDE sur un conteneur neuf :
  sans réchauffement il rend 4/5 (bridge « absent ») alors que tout est sain. La fumée réchauffe
  le démon avant l'épreuve (`rechauffer_cli`). Le script de vérification lui-même n'a pas été touché.
- Une fumée n'a de sens que sur `main` : si le checkout est sur une autre branche, la minuterie
  reporte (une fumée à la main marque la branche sur la page).

**Minuterie systemd utilisateur** (`conf/systemd/`, sans sudo) :
```bash
conf/systemd/installer-fumee.sh                 # copie didier-fumee.{service,timer} dans ~/.config/systemd/user/, active
systemctl --user list-timers didier-fumee.timer # prochain essai (toutes les :00 et :30 ; Persistent=true rattrape un PC éteint)
journalctl --user -u didier-fumee.service -e    # sortie du dernier essai
tail ~/.local/state/didier-fumee/journal.log    # reporté / début / fin
conf/systemd/installer-fumee.sh --desinstaller  # arrête, désactive, supprime les unités
```
Le chemin de `fumee.sh` écrit dans l'unité est celui du checkout d'où l'on lance l'installeur :
**le relancer depuis le checkout de `main`** une fois le lot fusionné (un worktree peut disparaître).
**Première page réelle** : la fumée complète a été jouée une fois à la main le 07/11 (verte :
RTF 0,979 ; namespace 5/5, catalogue 4/4, parle 3/3, V-R3 21/21, A1 14/14 ; 35 min), mais sa page
a été perdue avec /tmp lors de l'extinction accidentelle ci-dessus. Aucune page n'existe donc
dans `docs/fumee/` : la fumée est « due » et c'est la minuterie qui écrira la première page réelle.
Tests hôte : `packages/didier_core/test/unit/test_fumee.py` (décision « due ? », pages, garde-fous du script avec
un faux `docker`).

## Salle de répétition simulée — Didier chemine seul dans la rue (lot R1, 2026-10-07)

Monde `rue` + package SIM-ONLY `didier_rehearsal` (étude
[`etude-repetition-simulee.md`](etude-repetition-simulee.md) §12). Mode d'emploi
complet et règles de séance : `packages/didier_rehearsal/README.md` (racine du mono-dépôt).

```bash
cd conf/docker/sim && WORLD=rue HEADLESS=true ANIMATIONS=true FACE=true WEB=true docker compose -f docker-compose-sim.yml up -d
# chaîne roues puis cheminement (OFF au démarrage), même prudence que follow/gaze :
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_drive drive.launch.py use_sim_time:=true'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_rehearsal rehearsal.launch.py'
# partir / s'arrêter / reprendre au début : topic `route` = "on" | "off" | "restart" ; vitesse 0..1 : topic `route_speed`
docker exec dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 topic pub -1 /didier/route theatre_interfaces/msg/StringTime "{msg: \"on\"}"'
# vérification rejouable V-R1 (départ, POI, télécommande qui écrase, zéro franc, arrivée) :
docker exec dadou-sim-container bash /home/ros2_ws/validate-rehearsal-route.sh
```

- **Régisseur de pannes** (lot R2) : lancé par `rehearsal.launch.py` avec le scénario
  `demo` (chargé, en attente) ; `ros2 topic pub -1 /didier/rehearsal/cmd … "{msg: \"start\"}"`
  pour dérouler, `abort` pour tout révoquer ; journal JSONL dans
  `/home/ros2_ws/log/rehearsal/` (conteneur). Vérif : `validate-rehearsal-faults.sh`.
- La route publie sur `cmd_vel_follow` (prio 20) : **le suivi de personne doit
  rester OFF** pendant une route ; la télécommande (prio 100) écrase toujours.
- La pose vient de la **vérité terrain** gz (`/ground_truth/odom`), pas de
  `/odom` : téléporter Didier au départ se fait par
  `gz service -s /world/stage/set_pose …` (voir le script V-R1) — `/odom`,
  lui, ne verrait pas la téléportation.
- Le monde s'appelle `stage` même dans `rue.sdf` (contrat bridge LED) ; seul le
  fichier change (`WORLD=rue` ↔ `world:=rue`).

## Web interface on the REAL robot (sim → réel)

**Une seule console, un sélecteur de cible** : la page (ouverte depuis
n'importe quel pont, typiquement la sim sur le PC) choisit la machine qu'elle
contrôle via le menu du bandeau — « Sim locale » / « Didier réel »
(192.168.1.2:8765, bascule confirmée) / « Autre adresse… ». On peut aussi
ouvrir directement `http://192.168.1.2:8765`. Dans tous les cas le bandeau
reflète la machine RÉELLEMENT connectée : **vert SIMULATION** = Gazebo,
**rouge ROBOT RÉEL (domain 42)** = les commandes partent sur le vrai Didier
(sons réels, servos réels, relais réels). Le libellé du sélecteur n'est
jamais la vérité, le badge oui.

Différences avec la sim, voulues :
- **Pas de pilotage** : `robot_app.launch.py` ne passe pas `drive_enabled` →
  le pad est grisé (« pilotage désactivé »). SIM-ONLY tant que test scénique
  au sol + protocole caméra ne sont pas faits — ne PAS contourner en passant
  le paramètre à la main.
- **Pas de retour vidéo** pour l'instant : aucune source d'image ne publie sur
  le robot (la webcam est sur le Pi vision et ne publie pas d'Image ROS) —
  panneau « pas de vidéo », c'est normal. Chantier retour caméra réel à part.
- Contenus/servos/relais/système : fonctionnels, mêmes payloads que la
  télécommande physique (qui reste prioritaire sur les roues, et
  indépendante pour le reste — deux sources peuvent se marcher dessus,
  règle d'usage : la télécommande a raison sur scène).

Déploiement (fait le 2026-07-11 — pont web actif sur le robot) :
1. Rebuild image ARM fait (`python3-aiohttp`/`python3-pil`) ; un prochain
   changement de `packages-docker.txt`/`requirements.txt` demandera le même
   (`docker compose ... build` sur le Pi).
2. Déploiement habituel : Ansible depuis `../dadou_utils_ros` (rsync du
   checkout — `didier_web` part avec la liste `packages` de l'hôte, `ansible/hosts`, depuis L1e-1), sentinelle
   `robot/change` pour déclencher le colcon build au redémarrage.
   **Premier déploiement après L1e-2 (renommage `robot_*` → `didier_*`, 07/11)** : le rôle
   `synchronise` efface d'abord des Pi les anciens `src/`, `build/`, `install/` `robot_*`
   (liste `packages_retires`, vars/main.yml — sinon `colcon build` compile anciens ET nouveaux) ;
   la sentinelle est obligatoire, le conteneur (`launch-ros-in-docker.sh`) lance `ros2 launch didier_bringup
   robot_app.launch.py`. Jamais exécuté sur un Pi à ce jour (seul `--syntax-check` l'a vu) ;
   sur le robot, verrou inchangé : protocole caméra d'abord (L1b).
3. **Supervision (assainie le 2026-07-11)** : le conteneur est relancé par le
   **démon Docker** (`restart: unless-stopped` dans le compose — crashs et
   boot couverts, vérifié par crash-test `docker kill`) ; `robot.service`
   n'est plus qu'un interrupteur `up -d` / `stop`. Porte d'entrée habituelle :
   `sudo systemctl restart robot.service` — mais un `docker compose` manuel
   ne casse plus la supervision (l'ancien montage à `compose up` attaché +
   Restart=always laissait un client orphelin au premier recreate manuel).
4. Vérif : `http://192.168.1.2:8765` répond, badge ROUGE, un clic « visage »
   s'affiche sur le vrai visage LED, et le journal `robot.log` trace la
   commande (`cmd web id=... topic=face`).

### Alias didier.local (fait le 2026-07-12)

La console répond aussi sur `http://didier.local:8765` (alias mDNS publié par
le Pi robot). Pratique depuis un téléphone/une tablette ; le **PC de dev a un
mDNS cassé** → y garder l'entrée IP du sélecteur. Mécanique : service systemd
`avahi-alias-didier.service` (source versionnée :
`conf/systemd/avahi-alias-didier.service`) qui lance `avahi-publish` —
`/etc/avahi/hosts` ne publie PAS sur le réseau (résolution locale seulement,
vérifié). L'IP est relue au démarrage du service : le redémarrer si l'adresse
du Pi change (réseau 4G de tournée). Depuis le 07/11, paquet et service sont posés par
Ansible à chaque déploiement (rôle `config-hote`, variables `paquets_hote` / `unites_systemd`
de l'hôte robot) : plus de geste à la main après un reflash.

### Parole IA depuis la console (fait le 2026-07-12)

Panneau Technique → « Parole IA » : boutons ON/OFF publient `"on"`/`"off"` sur
le topic `chat` (whitelist technique), consommé par `chat_node` sur le Pi
vision — même contrat que le toggle `gaze`. OFF coupe le micro et bloque les
tours suivants sans couper une réplique en cours (Didier finit sa phrase) ;
ON = reprise instantanée (modèles restés chargés). Sans effet si `chat_node`
ne tourne pas (`chat_enabled` défaut false côté vision).

### Personnalité de Didier depuis la console (fait le 2026-07-13, lot D3)

Panneau Technique → « Personnalité » : trois boutons (Bougon / Naïf /
Vantard) publient le nom de variante sur le topic `persona`, consommé par
`chat_node` (Pi vision, cf. `vision/ai/personas.py` — brouillons d'atelier à
valider avec David). Chaque changement recompose le system prompt et ouvre
une **nouvelle session de conversation** (l'historique de l'ancien
personnage est abandonné — sinon Didier serait schizophrène) ; re-cliquer la
personnalité déjà active est sans effet. Défaut au démarrage : `bougon`
(config `chat_persona` côté vision, surchargeable par paramètre ROS
`persona`). Nom inconnu = warning loggué avec la liste, jamais un crash.

### Alias audio du Pi 5 vision — `/etc/asound.conf` (micro changé le 2026-08-26)

**Versionné depuis le 07/11** dans `../dadou_vision_ros/conf/rpi/asound.conf` (copie
exacte du Pi ; l'ancien fichier du même nom était une version périmée en `card 0` que rien ne
posait) et posé par Ansible à chaque déploiement (rôle `config-hote`, `fichiers_etc` de l'hôte
vision). **Modifier le fichier du dépôt, puis déployer** — le déploiement recrée le conteneur,
ce qui règle aussi le piège d'inode ci-dessous.

Les index ALSA (`card 0`, `card 1`…) dépendent de l'ordre de branchement : les
alias ciblent les cartes **par nom**. Trois alias, sur trois cartes USB :

| Alias | Carte | Rôle |
| --- | --- | --- |
| `mixette` | `CARD=Device` (C-Media Unitek Y-247A) | sortie audio vers la mixette du spectacle |
| `casque_mic` | `CARD=Array` (ReSpeaker XVF3800) | **micro de conversation** — depuis le 26/08 |
| `webcam_mic` | `CARD=U20` (webcam USB) | ancien micro, gardé pour la comparaison A/B de la campagne D0 |

**Le nom `casque_mic` est un contrat, pas une description.** Il a désigné
successivement un casque Logitech, puis la webcam (11/07 → 26/08), puis le
ReSpeaker. `vision_config.py::chat_mic_device` le référence et les tests
unitaires de `dadou_vision_ros` l'attendent tel quel : **on change l'esclave,
jamais le nom.**

**⚠️ Piège à l'édition : le fichier est BIND-MONTÉ (ro) dans
`dadou-vision-container`.** Un bind-mount de *fichier* suit l'**inode**, donc
`sed -i` ou un éditeur qui écrit-puis-renomme casse le lien en silence : le
conteneur continuerait de voir l'ancien contenu jusqu'au prochain
`docker restart`. Éditer **en place** (`sudo tee`, `cat >`), puis vérifier :

```bash
# depuis le PC — les deux md5 doivent être identiques
ssh -i ~/.ssh/keys/didier pi@192.168.1.151 \
  'md5sum /etc/asound.conf; sudo docker exec dadou-vision-container md5sum /etc/asound.conf'
```

**Vérifier qu'un alias pointe vraiment où on croit** (depuis le conteneur,
donc par le même chemin que `chat_node`) — enregistrer et regarder quelle
carte passe en `RUNNING`, plutôt que se fier au fichier :

```bash
sudo docker exec dadou-vision-container bash -c \
 'arecord -D casque_mic -f S16_LE -r 16000 -c 1 -d 4 /tmp/t.wav & sleep 2;
  for c in Array U20; do echo "$c : $(head -1 /proc/asound/$c/pcm0c/sub0/status)"; done; wait'
# attendu : Array : state: RUNNING   /   U20 : closed
```

Sauvegarde de la version précédente sur le Pi :
`/etc/asound.conf.bak-20260826`.

## Pre-show checklist
1. Inspect hardware (wheels locked, arms secure, LED strips intact).
2. Power on robot and remote controller (Pi 5 vision needs the 27 W PSU).
3. The robot app autostarts with the container; check
   `ros2 topic info /didier/face` shows a subscriber (namespace since L1b).
4. Remote controller GUI: quick input test (eyes, mouth, wheels, audio cue).
5. Test one full animation (`ros2 topic pub --once /didier/animation ... '"parle"'`).

## During the show
- Stage tech monitors the GUI.
- Wheels: remote input always overrides animations (twist_mux priority);
  releasing all inputs stops the wheels in ≤ 400 ms (deadman). ⚠️ There is no
  wired `e_stop` source yet — the deadman IS the emergency stop.
- Manual overrides: `face`/`animation` `"stop"` payloads; servos return to
  rest on animation stop or deadman.

## Post-show
- Archive `/home/ros2_ws/log/robot.log` for diagnostics — or better, run the
  incident collector (below) which bundles it with everything else.
- **Read the latched throttling flag BEFORE powering down**:
  `ssh r 'vcgencmd get_throttled'` (and the same on the vision Pi). Bits 16-19
  mean "under-voltage / thermal throttling *has occurred* since boot". This is
  the one measurement that still tells the truth on a cold robot — a
  temperature read after the show does not. Non-zero ⟹ the closed chassis hit
  its limits during the show, whatever the CPU graphs say.
- Recharge batteries / power down safely.

### Load study over a whole show (`log-charge.sh`)
`robot.log` only records threshold *alerts* (CPU > 80 %, temp > 55 °C) and the
incident collector is a snapshot — neither gives the **curve** needed to size
the Pi 5 (does the TTS still fit once the vision load is there?).

Start before the show, stop after (Ctrl-C):
```bash
ssh pi@192.168.1.151 '~/ros2_ws/src/*/conf/scripts/log-charge.sh'   # → ~/charge-<stamp>.csv
DOCKER=1 ./conf/scripts/log-charge.sh                               # + per-container attribution
```
Samples every second from `/proc` only (no fork per sample — a sampler that
perturbs its own measurement is worthless). Columns include per-core %, freq,
temp, the latched `throttled_ever`, available RAM and load. `DOCKER=1` adds a
second CSV attributing CPU/RAM per container — that is what answers "is it the
vision or the speech?".

⚠️ Measure with the chassis **closed** and the target vision load running: a
run on an open bench proves nothing about a sealed body holding an amplifier,
outdoors, in summer. Feeds lot V0b of
[`etude-voix-didier.md`](etude-voix-didier.md) and D0 of
[`etude-declenchement-conversation.md`](etude-declenchement-conversation.md).

## Incident investigation (télédiagnostic, étape « trousse d'atelier »)
- **Collect** (on the Pi HOST, works even if the container is dead):
  `ssh r '~/ros2_ws/src/*/conf/scripts/collect-incident.sh'` → timestamped
  tarball in `~/incidents/` (logs tail, docker logs/inspect, ROS graph,
  temperatures, disk, dmesg). Testable against the sim:
  `CONTAINER=dadou-sim-container LOG_DIR=<sim logs> ./collect-incident.sh`.
- **Investigate**: open a Claude session on the workstation and invoke
  `/diag` (skill in `.claude/skills/diag/` — read-only rules, reading-points
  map, known traps). Feed it the tarball.
- **Post-mortem**: every investigation ends with a short entry in
  [`incidents/`](incidents/README.md) — the robot's failure memory, synced to
  the Pi for the future embedded agent.
- Full plan: [`etude-telediagnostic.md`](etude-telediagnostic.md) (black box
  recorder + START button + embedded agent are the next stages).

## Troubleshooting
- Message published but nothing happens → check the payload is JSON
  (`'"name"'` with embedded quotes). Invalid payloads are logged as ERROR with
  the topic name since 2026-07-11 (before: silently dropped).
- Face changes by itself → `chat_node` (vision Pi) reacts to ambient sound.
- mDNS `.local` may fail from some terminals: use the IPs above.
- Topic mapping reference: [`interfaces.md`](interfaces.md).
