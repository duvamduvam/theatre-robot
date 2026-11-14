# Spec L2 — sim multi-conteneurs (un conteneur par machine, mêmes Dockerfiles que les Pi)

**Statut : spec FERMÉE, écrite le 13/11/2026 (Fable). Rien de codé.** Étude mère :
[`etude-architecture-globale.md`](etude-architecture-globale.md) §5.5, §5.7, §5.8, §5.10 et §6
(ligne L2). Suite de [`spec-L1-contrats-donnees.md`](spec-L1-contrats-donnees.md) (L1e-4 a laissé
à L2 : `docker/`, le compose unique de `machines/sim/`, le renommage des chemins Pi/conteneur).

Un implémenteur exécute une sous-étape SANS rien trancher : tout choix est dans §2 ; si un fait
relevé ici s'avère faux sur pièce, il **s'arrête et le rapporte** (pas d'improvisation), sauf là
où un repli est écrit (§7).

Porte de sortie du lot (étude §6) : **robot + vision + télécommande actuelle dans 3 conteneurs,
domaine 43 ; CI build + fumée verte.**

---

## 0. Faits relevés le 13/11 (sur `main` 8996126)

**La sim d'aujourd'hui est un fourre-tout, et elle ne lance PAS le robot réel.**

1. `machines/sim/banc-robot/Dockerfile-sim` + `docker-compose-sim.yml` : UN conteneur
   (`dadou-sim-container`, image `dadouuu/dadou-sim-x86`, 3,88 Go) qui porte Gazebo, le pont gz, les
   nœuds de sim, 10 packages du robot, la répétition, le sélecteur de jeu et les épreuves.
   Réseau `host`, `ipc: host`, `GZ_IP=127.0.0.1`, `ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-43}`
   (**surchargeable depuis l'environnement de l'appelant** — `fumee.sh` le force et le revérifie).
2. `packages/didier_sim/launch/sim.launch.py` lance : gz + `create` + `robot_state_publisher` +
   `parameter_bridge` + `leds_sim_node` + `servos_sim_node`, puis un SOUS-ENSEMBLE du robot derrière
   des drapeaux (`animations_node`, `face_sim`, `catalogue`, `data_edit`, `web_bridge` avec des
   paramètres propres à la sim). **`robot_app.launch.py` (le vrai bringup, 16 nœuds) n'est jamais
   lancé en sim** ; la chaîne roues (`drive.launch.py use_sim_time:=true`) et `gaze_follower` sont
   lancés à la main ou par les scripts d'épreuve.
3. **Les nœuds matériels du cœur se désactivent déjà seuls hors Pi** : `Servo`, `RelaysManager`,
   `Wheels`, `lights_node` testent `Misc.is_raspberrypi()` et reviennent sans toucher au matériel
   (imports Adafruit différés). `machines/robot/requirements.txt` porte déjà les marqueurs
   `platform_machine == "aarch64"`. `machine.yml` du robot le dit : « relays_node et wheels_node
   tournent même sans carte I²C ». Non vérifié : `audio_node` (VLC) et `system_node` sur x86 sans
   carte son — c'est la porte de L2a.
4. **Les « pilotes sim » existent comme nœuds séparés**, abonnés aux MÊMES topics de commande que
   les nœuds réels : `servos_sim_node` (→ articulations gz), `leds_sim_node` (→ matériaux gz),
   `face_sim` (didier_core, aperçu MJPEG du visage). Aucun ne publie d'état lisible par la page ;
   rien ne simule les relais ni l'audio.
5. **Dockerfiles** : robot `machines/robot/docker/arm/Dockerfile-arm` (contexte principal = la
   disposition du Pi `src/robot/`, `COPY conf/`, packages et `data` en contextes nommés) ;
   `machines/sim/banc-robot/Dockerfile-x86` en est une quasi-copie (base `desktop-full`, `conf` déjà
   en contexte nommé). Vision `machines/vision/docker/arm/Dockerfile-arm` : déjà construit TEL QUEL
   en x86 par `machines/sim/banc-vision/build-x86.sh`, au prix d'un `tar --transform` qui refabrique
   la disposition du Pi (image `dadouuu/dadou-vision-x86`, 3,07 Go). Télécommande : deux Dockerfiles
   distincts dans `legacy/dadou_control_ros/conf/docker/{x86,arm}` (réécriture = L4).
   Les deux Dockerfiles robot/vision partent de `ros:jazzy-ros-base` et n'ont **aucune couche
   lourde en commun** (vision = pip mediapipe/whisper/piper ; robot = apt audio + Adafruit).
6. **Secret** : `machines/vision/docker/arm/Dockerfile-arm.dockerignore` exclut `conf/secret` du
   contexte principal (prouvé sur le Pi le 11/11) ; l'image vision est publiée sur le Hub.
   Mesuré ce 13/11 sur le PC (buildx 0.34, BuildKit 0.26) : un `.dockerignore` à la RACINE d'un
   contexte NOMMÉ est honoré, et `COPY --exclude=` fonctionne. **Non vérifié sur les Pi.**
7. **Images ARM** : construites SUR le Pi (≈ 35 min sur Pi 4), poussées à la main sur le Hub
   (`dadouuu/dadou-robot-arm`, `dadouuu/dadou-vision-arm`) ; le rôle `conteneur` ne tire jamais
   (image locale), vide `build/` et `install/` si l'image change, exige `noeuds_attendus`.
8. **Épreuves** (`machines/sim/validate-*.sh`) : exécutées DANS le conteneur ; elles supposent un
   seul espace de processus (`pgrep`, `pkill -STOP` du régisseur, `kill` de `route_driver`), un
   seul `/home/ros2_ws/log` (`robot.log`, `rehearsal/`, `jeu/`), et lancent elles-mêmes ce qui
   manque (`lance "<motif>" …` ne fait rien si le processus existe déjà).
9. **Fumée** (`machines/sim/fumee.sh`) : image → démarrage (≤ 360 s) → RTF 20 s (rouge < 0,8) →
   namespace 5 → catalogue 4 → `parle` 3 → édition 12 → V-R3 21 → sim relancée → A1 14 ; ≈ 40 min ;
   cœurs 8-15 réservés (`coeurs_reserves.py`, un seul nom de conteneur) ; refuse si
   `dadou-sim-container` existe ; ne démarre pas dans une plage sans commit.
10. **RTF mesurés (PC de David)** : sim seule sur 4 cœurs rapides réservés, GPU par `/dev/dri` :
    0,987 ; sous pic de charge : 0,76 ; caméras rendues au CPU : 0,49 (0,88 à 5 Hz).
11. **CI** (`.github/workflows/tests.yml`) : 6 suites pytest hôte, sans ROS, sans Docker, sans cache.
12. **Vérifié ce 13/11 dans l'image sim** (deux launch d'essai) : un argument passé à
    `ros2 launch` et NON déclaré par le launch de tête atteint un launch INCLUS qui le déclare —
    `ros2 launch didier_bringup robot_app.launch.py use_sim_time:=true` met donc la chaîne roues en
    horloge simulée **sans modifier `drive.launch.py` ni la ligne qui l'inclut**.
13. `web_bridge` : `rehearsal_enabled` est ignoré hors domaine 43 ; `drive_enabled` n'a PAS de
    garde de domaine (c'est un paramètre, `false` par défaut, jamais posé sur le robot).
14. Vision : source d'images par défaut = webcam ; la caméra Gazebo n'est proposée que si
    `VISION_SIM_CAMERA_TOPIC` est posé, et se choisit à chaud (`camera_source`). Sans webcam,
    `person_tracker` s'arrête (machine.yml de la vision).
15. Télécommande actuelle : nœud `controller_node`, IHM tkinter dès qu'on n'est pas sur un Pi
    (il lui faut un serveur X) ; elle ne publie aucun état, seulement ses commandes
    (`PUBLISHER_LIST`, dont `animation`).
16. L1d-2 (observateur `validation_sim`, « lancé par `sim.launch.py` SEUL ») n'est pas encore
    codé ; seul le registre `json/validations-sim.json` existe dans le contrat.
17. Chemins codés en dur `src/robot` / `src/vision` hors listes d'effacement : ≈ 20 fichiers
    (2 Dockerfiles, 4 compose, `robot_app.launch.py` ×3, `robot_config.py`, `vision_config.py`,
    `data_edit_node.py`, `donnees.py`, `machine.yml` vision ×3, `validate-data-edit.sh`, 4 fichiers
    de tests dont `test_arborescence.py` ×57). Le code lit `conf/`, `json/`, `medias/`, `db/` comme
    ENFANTS d'une racine (`DIDIER_DATA_DIR`, `DIDIER_VISION_DATA_DIR`).

---

## 1. Ce que L2 supprime (règle du dépôt)

| Supprimé | Quand | Remplacé par |
|---|---|---|
| `machines/sim/banc-robot/` entier (`Dockerfile-sim`, `docker-compose-sim.yml`, `Dockerfile-x86`, `docker-compose-x86.yml`) — **l'image sim fourre-tout** et l'ancien banc de bureau | L2b (x86 : L2a) | `machines/sim/docker-compose.yml` + `machines/sim/monde/Dockerfile` |
| `machines/sim/launch-sim-in-docker.sh`, `packages/didier_sim/launch/sim.launch.py` | L2b | `machines/sim/monde/entree.sh`, `monde.launch.py`, le vrai `robot_app.launch.py` |
| `machines/sim/banc-vision/build-x86.sh` (le `tar --transform`) et `banc-vision/docker-compose-x86.yml` | L2a / L2b | service `vision` du compose + surcouche `docker-compose.banc.yml` |
| `machines/{robot,vision}/docker/arm/Dockerfile-arm` (et `Dockerfile-arm.dockerignore`) | L2a | `machines/<machine>/docker/Dockerfile` (un seul, ARM et x86) |
| `machines/robot/docker/{Dockerfile-bak,.dockerignore,jenkins/,scripts/entrypoint-tests.sh}` (morts : `.dockerignore` jamais lu, Jenkins sorti en L1e-4a) | L2a, après `grep` de tout consommateur | rien |
| `docker/` (dossier et ligne du README racine) | L2a | rien — décision 4 |
| Les tags locaux `dadouuu/dadou-sim-x86`, `dadouuu/dadou-vision-x86`, `dadouuu/dadou-robot-x86` | L2b | `didier-sim/<service>:local` (jamais poussés) |
| Les chemins `~/ros2_ws/src/robot/{conf,json,medias,db}` et `src/vision/{conf,medias,db}` (Pi et conteneurs) | L2e | `~/ros2_ws/machine/{conf,json,medias,db}` |

L2 ne supprime PAS : `didier_sim` (il devient le package du conteneur `monde`), les scripts
`validate-*.sh`, la télécommande `legacy/dadou_control_ros/` (L4), `wheels_bridge` (L4).

---

## 2. Décisions (ne pas rouvrir)

### Découpage

1. **Quatre services dans UN compose, `machines/sim/docker-compose.yml`** (projet compose
   `didier-sim`) :

   | Service | Conteneur | Image locale | Dockerfile | Ce qui y tourne |
   |---|---|---|---|---|
   | `monde` | `didier-sim-monde` | `didier-sim/monde:local` | `machines/sim/monde/Dockerfile` (x86 seul) | Gazebo, `create`, `robot_state_publisher`, pont gz, **matériel simulé** (`servos_sim_node`, `leds_sim_node`, puis `relais_sim_node`, `audio_sim_node`), répétition (`didier_rehearsal`), sélecteur (`didier_jeu`, SIM-ONLY), **épreuves** |
   | `robot` | `didier-sim-robot` | `didier-sim/robot:local` | `machines/robot/docker/Dockerfile` (**le même que le Pi**) | `robot_app.launch.py` INCHANGÉ dans sa partie roues (16 nœuds) + `complement_sim.launch.py` (`face_sim`, plus tard `validation_sim`) ; `gaze_follower` à la demande |
   | `vision` | `didier-sim-vision` | `didier-sim/vision:local` | `machines/vision/docker/Dockerfile` (**le même que le Pi**) | `vision.launch.py`, source d'images = caméra Gazebo, `CHAT=false` |
   | `telecommande` | `didier-sim-telecommande` | `didier-sim/telecommande:local` | `legacy/dadou_control_ros/conf/docker/x86/Dockerfile-x86` (tel quel) | `controller_node` |

   Plus un service utilitaire `ecran` (profil compose `xvfb`, image `monde`, `Xvfb :99`) — décision 9.
   **Gazebo vit dans `monde`, pas dans `robot`** : le conteneur `robot` doit être ce qui part sur
   le Pi, rien de plus ; le monde est « tout ce qui n'est pas une machine de Didier » (la physique,
   le matériel, la rue, les passants, le public simulé). Écarté : Gazebo dans `robot` (le
   fourre-tout renaît) ; un conteneur par nœud de sim (rien à y gagner).
2. **Le conteneur `robot` lance le VRAI bringup.** Entrée :
   `launch-ros-in-docker.sh use_sim_time:=true camera_topic:=camera/image_raw
   camera_compressed:=false perception_topic:=camera/image_raw/compressed
   exterior_topic:=camera_ext/image_raw web_port:=${WEB_PORT:-8765} web_drive:=${WEB_DRIVE:-false}
   rehearsal:=${REHEARSAL:-false}` — les arguments sont posés par l'`entrypoint` du compose SIM,
   jamais par une variable d'environnement lue côté robot. Les nœuds matériels y sont inertes
   (fait 3) ; le matériel simulé du conteneur `monde` écoute les mêmes topics.
   Conséquences assumées : `animations_node`, `catalogue`, `data_edit`, `web_bridge`, la chaîne roues
   (`twist_mux`, `twist_deadman`, `wheels_bridge`) tournent TOUJOURS en sim (les drapeaux
   `ANIMATIONS` et `WEB` disparaissent ; restent `WEB_DRIVE`, `REHEARSAL`, `DATA_EDIT`, `FACE`,
   `HEADLESS`, `WORLD`, `WEB_PORT`, `FACE_PORT`).
3. **Contrat de simulabilité, niveau L2 = le TOPIC, pas la classe.** Chaque famille de matériel a
   un nœud « matériel simulé » dans `monde` qui (a) s'abonne au topic de commande du contrat,
   (b) **publie son état** sur `sim/etat/<famille>` (décision 12). La couture DANS le nœud réel
   (un pilote injecté, comme `Wheels(pca9685=…)` le permet déjà) n'est PAS faite en L2 : les nœuds
   du cœur sont de génération 1 (réécrits en L5), et celui des roues est interdit. Elle naît avec
   le gabarit (L3) pour le code neuf. Limite dite : en sim, la rampe des servos et les animations
   LED exécutées sont celles de `didier_sim_lib`, pas celles de `didier_core/actions`.

### Images

4. **Pas d'image de base commune ; `docker/` est supprimé.** Robot et vision n'ont en commun
   que `ros:jazzy-ros-base` (déjà partagée par le registre) ; une base maison ajouterait un ordre
   de construction sur chaque Pi et en CI pour zéro couche économisée. « Mêmes Dockerfiles que
   l'ARM » est obtenu autrement (décision 5). Écarté aussi : image multi-arch poussée (QEMU en CI
   ≈ heures pour la vision, et les Pi construisent leur image locale — fait 7).
5. **Un Dockerfile par machine, sans disposition implicite : `machines/<machine>/docker/Dockerfile`.**
   Contexte principal = ce dossier `docker/` (rien n'y est copié). TOUT arrive par contextes
   NOMMÉS : `conf` (la conf de la machine), `data` (robot seul), un par package de la liste
   `packages` du `machine.yml`. Le compose ARM (`docker/arm/docker-compose-arm.yml`, emplacement
   INCHANGÉ : Ansible et systemd le référencent) donne les chemins du Pi ; le compose sim donne
   ceux du dépôt ; le Dockerfile ne sait pas où il est. Construction x86 NATIVE sur le PC et en
   CI, ARM native sur le Pi : aucune émulation. Le `COPY medias/` de la vision disparaît (sur le
   Pi `medias/` est monté et la voix posée par Ansible ; l'image la télécharge déjà).
   Un test de structure (dans `test_arborescence.py`) grave : lignes `COPY --from=<package>` du
   Dockerfile = `packages` du `machine.yml` = contextes des deux compose = montages de sources.
6. **Secret de la vision : trois verrous, prouvés sur PC ET sur Pi avant toute poussée d'image.**
   (a) `machines/vision/.dockerignore` (racine du contexte nommé `conf`, il voyage sur le Pi avec
   la conf) contenant `secret` ; (b) dans le Dockerfile, `COPY --from=conf --exclude=secret` ;
   (c) **contrôle permanent** dans le rôle `conteneur` : après construction, pour toute machine
   ayant `secrets_hote`, `docker run --rm --entrypoint test <image> ! -e <chemin du secret>` —
   échec du playbook si le fichier est DANS l'image. Preuve de porte : construction d'essai avec
   un secret FACTICE présent, sur le PC et sur le Pi vision ; si (a) ou (b) n'est pas honoré par
   le BuildKit du Pi, on garde l'autre + (c) et on le consigne ; si aucun des deux → arrêt, rapport.
7. **Télécommande : son Dockerfile x86 legacy, tel quel.** Pas d'unification x86/ARM d'un code
   que L4 réécrit. Écart à « mêmes Dockerfiles » assumé et borné à ce service.

### Réseau, IPC, DDS, processus

8. **`network_mode: host` + `ipc: host` sur les 4 services** (FastDDS passe les données en
   mémoire partagée entre participants du même hôte : sans `ipc: host`, les topics se voient et
   rien ne traverse — vécu le 13/09). **`ROS_DOMAIN_ID=43` en LITTÉRAL** dans le compose (plus de
   `${ROS_DOMAIN_ID:-43}`), `ROBOT_NAME=${ROBOT_NAME:-didier}` identique partout.
   `GZ_IP=127.0.0.1` sur `monde` SEUL : gz-transport ne sort jamais de ce conteneur (cause d'A1
   intermittent, 11/11) ; aucun autre service ne lance de processus gz (gravé par test).
   Aucun service sim n'est `privileged`, ne monte `/dev` ni n'a de `restart:` — un `system_node`
   de conteneur ne peut donc structurellement pas éteindre le PC.
   Écarté : réseau bridge dédié (plus proche de deux Pi en UDP, mais non éprouvé, et la
   télécommande physique doit pouvoir rejoindre la sim en 43) ; `ROS_AUTOMATIC_DISCOVERY_RANGE=
   LOCALHOST` (même raison).
9. **Écran** : variable `ECRAN` du compose. `hote` (défaut, PC de David, fumée locale) : socket X
   et `XAUTHORITY` de la session, `/dev/dri` sur `monde` — comme aujourd'hui, c'est ce qui donne
   RTF ≈ 1. `xvfb` (CI) : le service `ecran` lance `Xvfb :99` dans un dossier de sockets partagé
   (`machines/sim/workspace/x11` monté sur `/tmp/.X11-unix` de `monde` et `telecommande`),
   `DISPLAY=:99`, `LIBGL_ALWAYS_SOFTWARE=1`. `xvfb` s'ajoute à l'image `monde` seulement.
10. **Espace de processus partagé pour les épreuves** : `robot`, `vision`, `telecommande` ont
    `pid: "service:monde"`. Les scripts d'épreuve tournent dans `monde` et gardent leurs
    `pgrep`/`pkill` tels quels. C'est un échafaudage de TEST (sim seulement, gravé : absent des
    compose ARM) ; il ne touche ni DDS ni les systèmes de fichiers. Écarté : réécrire les
    préconditions des 7 scripts en lectures du graphe ROS (risque de changer les épreuves).
11. **Journaux et builds** : `machines/sim/workspace/log` monté sur `/home/ros2_ws/log` de `monde`
    ET `robot` (les épreuves lisent `robot.log`, `rehearsal/`, `jeu/`, `tickets/` au même endroit) ;
    `workspace/log-vision`, `workspace/log-telecommande` pour les deux autres ;
    `COLCON_LOG_PATH=/home/ros2_ws/log/colcon-<service>` partout. `build/` et `install/` ne sont
    PAS persistés (colcon à chaque `up`, comme aujourd'hui : jamais d'install périmé). Sources
    montées par-dessus la copie de l'image, service par service, selon SA liste de packages.
    Données : `data/json` et `data/medias` montés dans `robot` aux chemins du Pi, et dans `monde`
    aux chemins d'aujourd'hui (`/home/ros2_ws/json`, `/home/ros2_ws/src/robot/{json,medias}`) —
    les nœuds de sim et les épreuves (`validate-catalogue`, `validate-data-edit`) les lisent et
    les restaurent là, sans retouche ; `machines/` monté en lecture seule dans `monde` (M1, M2).

### États et page scène

12. **Topics d'état du matériel simulé** (dans `theatre_contrats/topics.py`, payloads construits
    et validés par un module neuf `theatre_contrats/etats_sim.py`, testé, valeurs attendues
    gravées en littéral) — `StringTime`, JSON, latché (`TRANSIENT_LOCAL` + reliable, profondeur 1),
    publié à chaque changement et au plus 5 Hz :

    | Topic | Publié par | JSON |
    |---|---|---|
    | `sim/etat/servos` | `servos_sim_node` | `{"neck": 0-99, "left_arm": …, "right_arm": …, "left_eye": …, "right_eye": …}` (consigne courante) |
    | `sim/etat/leds` | `leds_sim_node` | `{"lumieres": "<séquence>"\|"", "visage": "<expression>"\|"", "luminosite": 0.0-1.0}` |
    | `sim/etat/relais` | `relais_sim_node` (neuf) | `{"<nom de relais du JSON relais>": true\|false, …}` |
    | `sim/etat/audio` | `audio_sim_node` (neuf) | `{"joue": "<nom>"\|"", "depuis_ms": N}` |

    Logique pure dans `didier_sim_lib/` (motif `servos_logic.py`), nœuds fins. Les deux nœuds
    neufs lisent les mêmes JSON que les vrais (`json/` monté dans `monde`).
13. **La page scène rend tous les états, en lecture seule** : `web_bridge` s'abonne aux 4 topics
    ci-dessus seulement en domaine 43 (même garde que `rehearsal_allowed`), et calcule un bloc
    `machines` = pour `robot`, `vision`, `telecommande`, `monde` : présentes ou non d'après les
    nœuds du graphe (`robot` = `/…/animations_node`, `vision` = `/…/vision_status`,
    `telecommande` = `/…/controller_node`, `monde` = `/…/servos_sim_node`), plus `vision/status`
    tel quel. Page : un panneau « Machines » (4 pastilles) et un panneau « Matériel simulé »
    (servos, LED, relais, son joué). Aucun nouveau topic inscriptible, aucun changement de la
    whitelist d'écriture. La télécommande actuelle ne publie pas d'état : sa présence dans le
    graphe EST son état (un vrai état viendra avec L4).
14. **Vision en sim** : argument de launch neuf `source_initiale` (`webcam` par défaut, `gazebo`
    accepté seulement si `sim_camera_topic` est non vide), alimenté par
    `VISION_SOURCE_INITIALE` dans `machines/vision/scripts/launch-ros-in-docker.sh` (même motif
    que `VISION_SIM_CAMERA_TOPIC`). En `gazebo`, `person_tracker` n'ouvre PAS la webcam et ne
    s'arrête pas faute de `/dev/video0`. Le compose sim pose `VISION_SIM_CAMERA_TOPIC=
    camera/image_raw`, `VISION_SOURCE_INITIALE=gazebo`, `CHAT=false`, aucun secret monté.
    Le banc « parole et caméra réelles » devient la surcouche `machines/sim/docker-compose.banc.yml`
    (webcam, `/dev`, `privileged`, PipeWire, `asound-pc.conf`, secret de `~/.config/didier/`,
    variables `CHAT_*`) appliquée au MÊME service `vision` — seule exception à la décision 8.

### Modifications autorisées du côté robot (bornées)

15. **`robot_app.launch.py`** gagne 7 arguments dont les défauts sont EXACTEMENT les valeurs
    d'aujourd'hui : `web_port` (8765), `web_drive` (false), `rehearsal` (false), `camera_topic`
    (`camera/image_raw/compressed`), `camera_compressed` (true), `perception_topic` (vide),
    `exterior_topic` (vide). Ils ne paramètrent QUE le nœud `web_bridge_node`.
    **Interdit dans ce fichier** : toucher
    aux blocs `wheels_node`, `drive_launch` et aux 5 servos, déclarer `use_sim_time` (il passe par
    héritage, fait 12). Test gravé : sans argument, les paramètres générés pour chaque nœud sont
    identiques à ceux d'avant (comparaison à un littéral) ; aucun `machine.yml` ni compose ARM ne
    contient `web_drive`, `rehearsal` ou `use_sim_time`.
16. **`machines/robot/scripts/launch-ros-in-docker.sh`** : (a) construit aussi si
    `install/setup.bash` manque (condition déjà en service dans celui de la vision) ; (b) finit
    par `exec ros2 launch didier_bringup robot_app.launch.py "$@"`. L'`ENTRYPOINT` du Dockerfile
    (`bash -c "source …"`) ne passe aucun argument : sur le Pi, comportement identique.
17. **`packages/didier_bringup/launch/complement_sim.launch.py`** (neuf) : `face_sim` (si
    `face:=true`), et l'emplacement prévu de `validation_sim` (L1d-2). Première action : échec si
    `ROS_DOMAIN_ID` ≠ 43. Lancé par le compose sim à côté du bringup (même conteneur), jamais par
    `machine.yml`.
18. **`packages/didier_sim/launch/monde.launch.py`** (neuf, remplace `sim.launch.py`) : gz,
    `create`, `robot_state_publisher`, pont, matériel simulé — arguments `world`, `headless`,
    `robot_name`. Même garde 43. `machines/sim/monde/entree.sh` : vérifie 43, `colcon build` de
    ses packages, lance `monde.launch.py`.
    Image `monde` = le `Dockerfile-sim` actuel, plus `xvfb`, moins `didier_bringup`, `didier_drive`,
    `didier_web` (elle garde `didier_core` comme bibliothèque de `didier_rehearsal`/`didier_jeu`,
    faits des `package.xml`) ; gravé : aucun launch de `monde` ne démarre un exécutable de
    `didier_core`, `didier_drive` ou `didier_web`. `didier_jeu` rejoindra `robot` le jour où il
    quitte SIM-ONLY (lots A) — dette dite, pas traitée ici.

### Chemins

19. **Les chemins Pi/conteneur sont renommés en L2, en DERNIÈRE sous-étape (L2e), détachable.**
    Cible : **`~/ros2_ws/machine/`** (conteneur : `/home/ros2_ws/machine/`) = la racine d'exécution
    de la machine, mêmes enfants qu'aujourd'hui (`conf/`, et selon la machine `json/`, `medias/`,
    `db/`) — donc `DIDIER_DATA_DIR=/home/ros2_ws/machine/` et `DIDIER_VISION_DATA_DIR=
    /home/ros2_ws/machine/`, **aucune logique de code ne change, seulement des constantes de
    chemin**. `~/ros2_ws/src/` ne contient plus QUE des packages (fin du piège « colcon descend
    dans `src/robot/` », vécu le 08/11) et le nom ne dépend plus du projet (le gabarit L3 naît avec).
    La télécommande reste en `src/controller/` (L4). Pourquoi en dernier : la sim multi-conteneurs,
    qui construit les mêmes Dockerfiles, est alors le filet qui essaie le renommage avant les Pi.
    Écarté : `data/` + `machine/` séparés (le code lit `conf/` sous la racine de données : il
    faudrait le modifier) ; ne rien renommer (la promesse de L1e-4 resterait due à L3).

### Fumée et CI

20. **Fumée locale** (`fumee.sh`) : mêmes épreuves, mêmes valeurs gravées (5, 4, 3, 12, 21, 14),
    même ordre, plus **`machines`** (décision 21) entre `edition` et `chantiers`. Adaptations :
    liste `CONTENEURS` (4 noms) partout où il y avait un nom (refus si l'un existe — ET l'ancien
    `dadou-sim-container` pendant la transition ; `docker update --cpuset-cpus` ; `recolter` ;
    `coeurs_reserves.py --sim` répétable) ; `ros_dans <service> <cmd>` ; démarrage vert = domaine 43
    lu dans les 4 conteneurs + colcon sans échec dans les 4 + pont gz + **`noeuds_attendus` des
    `machine.yml` robot et vision vus depuis `monde`** (délai porté à 600 s) ; `lancer_corps` ne
    lance plus la chaîne roues (elle tourne), lance `rehearsal.launch.py` dans `monde` et
    `gaze_follower` dans `robot` ; reconstruction des images si l'un de ces chemins a changé depuis
    la dernière verte : `machines/sim/`, `machines/{robot,vision}/docker/`,
    `machines/{robot,vision}/{packages-docker,requirements}.txt`,
    `legacy/dadou_control_ros/conf/`. RTF ≥ 0,8 reste la condition de tout le reste.
    Durée attendue ≈ 45-50 min (4 colcon au lieu d'un, une épreuve de plus).
21. **Épreuve neuve `machines/sim/validate-machines.sh`** (rclpy, jamais `ros2 topic echo` ;
    ligne finale `=== validate-machines : N OK, K KO`) — 5 épreuves en L2b, 10 en L2c :
    M1 les nœuds attendus du robot (lus dans `machines/robot/machine.yml`, monté en lecture seule)
    sont dans le graphe vu de `monde` ; M2 idem vision (plus `person_tracker` à partir de L2c) ; M3
    `/<robot>/controller_node` présent ; M4 `vision/status` : ≥ 2 messages en 15 s ; M5 l'image
    traverse monde → vision → robot : ≥ 5 messages sur `camera/image_raw/compressed` en 20 s
    (L2c, quand la vision démarre sur la caméra Gazebo) ;
    M6 `controller_node` a un éditeur sur `animation` (`get_publishers_info_by_topic`) ;
    M7-M10 (L2c) : une commande publiée sur `relay`, `audio`, `neck`, `robot_lights` se lit dans
    `sim/etat/{relais,audio,servos,leds}` en moins de 5 s. `ATTENDU_MACHINES=5` (M1-M4, M6)
    puis `10`.
22. **CI = deux étages, et le repli de l'étude est précisé.** Nouveau workflow
    `.github/workflows/sim.yml` (`tests.yml` inchangé) :
    - **`images`** (bloquant dès L2d) : `docker buildx` des 4 images x86, **cache de couches sur
      GHCR** (`ghcr.io/<propriétaire>/theatre-robot-cache:<service>`, `mode=max`), authentifié
      par le `GITHUB_TOKEN` du workflow (`packages: write` sur `push`, lecture seule sur les PR
      de fork) — **aucun secret ajouté au dépôt**, rien sur le Hub ; `hadolint` sur les 3
      Dockerfiles du dépôt ; première étape = libérer le disque du runner (les 4 images pèsent
      ≈ 10 Go). Le Hub garde les seules images ARM, poussées à la main depuis les Pi.
    - **`fumee-courte`** : `ECRAN=xvfb WORLD=stage HEADLESS=true docker compose up -d`, puis, par un
      script unique `machines/sim/fumee-courte.sh` (rejouable tel quel sur le PC) : domaine 43 ×4,
      colcon ×4, nœuds attendus, `validate-namespace` (5), `validate-catalogue` (4), `parle` (3),
      `validate-machines` (valeur gravée du moment : 5 ou 10). **Le RTF est mesuré et publié dans le résumé du job, il n'est PAS
      une condition** : sans GPU sur 4 vCPU il est estimé entre 0,3 et 0,6 (non mesuré — fait 10
      extrapolé). **V-R3, A1 et édition ne tournent JAMAIS en CI** (elles mesurent des durées :
      à RTF 0,4 elles seraient rouges sans régression) ; elles restent à la fumée locale.
      Journaux des 4 conteneurs en artefact. Aucun commit depuis la CI.
    - **Règle de promotion, décidée d'avance** : `fumee-courte` naît `continue-on-error: true`.
      Après ses 10 premières exécutions sur `main` : ≥ 9 vertes ET durée médiane ≤ 25 min → elle
      devient bloquante ; 7 ou 8 vertes → elle reste non bloquante sur chaque poussée ; < 7 →
      elle quitte `push` pour `workflow_dispatch` + un passage hebdomadaire (`schedule`). Elle
      n'est jamais supprimée (étude §5.10). Le résultat du comptage s'écrit dans `chantiers.md`.
    - Caractéristiques du runner gratuit (cœurs, RAM, disque, durée max) : **à lire à la source
      au début de L2d**, pas de mémoire ; aucune décision ci-dessus n'en dépend.

---

## 3. Cible (vue d'ensemble)

```
PC (ou runner CI) — domaine 43, réseau host, ipc host, pid partagé avec « monde »
┌ monde ──────────────────┐   topics de commande    ┌ robot (Dockerfile du Pi) ─────────┐
│ Gazebo  GZ_IP=127.0.0.1 │◄──(neck, face, relay…)──│ robot_app.launch.py use_sim_time  │
│ pont gz, /clock, caméras│── cmd_vel ◄─────────────│  16 nœuds (matériel inerte hors Pi)│
│ matériel simulé         │── sim/etat/* ──────────►│  web_bridge → page scène :8765    │
│ répétition, jeu         │── camera/image_raw ──┐  │ complement_sim : face_sim :8766   │
│ épreuves validate-*.sh  │                      │  └───────────────────────────────────┘
└─────────────────────────┘                      ▼            ▲ camera/image_raw/compressed
┌ telecommande (legacy x86)┐            ┌ vision (Dockerfile du Pi) ─┐  vision/status
│ controller_node (tkinter)│─ commandes►│ vision.launch.py, source   │──────────┘
└──────────────────────────┘            │ = caméra Gazebo, CHAT=false│
                                        └────────────────────────────┘
```

---

## 4. Sous-étapes — une porte chacune, fusionnées une à une

Règles communes : branche `l2` dans un worktree, fusion dans `main` sous-étape par sous-étape ;
commit d'instantané avant tout déplacement ; jamais `git add -A` ; doc dans le même lot
(`docs/operations.md`, `machines/README.md`, `machines/sim/README.md`, `docs/chantiers.md`,
README racine, `CLAUDE.md` si une commande change) ; pytest 6 suites verts ; **fumée complète
verte sur la branche avant fusion** ; aucun commit dans les plages sans commit ; toute fumée
lancée détachée (`systemd-run --user` / `setsid nohup`), jamais `--et-dodo` depuis un agent.
Dès qu'une image ARM, un compose ARM, un script de machine ou un package déployé change :
**déploiement hors robot** des Pi concernés (`192.168.1.131`, `.151`), `ecart-pi.sh` vert, avant
fusion — demander à David de les brancher.

### L2a — Un Dockerfile par machine (Opus)

Opus : secret de la vision (décision 6) et script de démarrage du robot (décision 16).

- Décisions 4, 5, 6, 16. `git mv` des deux `Dockerfile-arm` vers `docker/Dockerfile`, `conf` en
  contexte nommé, `COPY medias/` retiré ; compose ARM : `dockerfile`, `context`, contextes `conf`
  et `data` ; liste neuve `chemins_retires_l2` dans `deploy/vars/main.yml` (anciens
  `conf/docker/arm/Dockerfile-arm*`, effacement conditionnel, gravée par `test_arborescence.py`).
- Banc vision rebranché sur le Dockerfile unique (son compose gagne une section `build:` à
  contextes nommés, `build-x86.sh` supprimé) ; l'ancien banc de bureau du robot (`Dockerfile-x86`,
  `docker-compose-x86.yml`) et les fichiers morts du §1 supprimés ; `docker/` supprimé.
  **La sim reste le fourre-tout** (inchangée).
- **Porte** : (1) les deux images se construisent sur le PC depuis le dépôt ; (2) preuve du
  secret factice sur PC et sur le Pi vision (décision 6) ; (3) l'image robot x86 démarrée seule
  (domaine 43, non privilégiée, sans `/dev`) montre les 16 `noeuds_attendus` pendant 5 min,
  `RestartCount` 0 ; (4) images reconstruites SUR les deux Pi, déployées, `noeuds_attendus` verts,
  `ecart-pi.sh` vert ×2, inventaires `deploy/attendu/` regravés ; (5) fumée complète verte ;
  (6) banc vision : `person_tracker` vivant sur la webcam du PC.

### L2b — Le compose multi-conteneurs et la fumée (Opus)

Opus : `robot_app.launch.py` (décision 15) et l'ordonnancement de la chaîne roues en sim.

- Décisions 1, 2, 7 à 11, 14 (la surcouche banc seulement ; `source_initiale` attend L2c : en
  L2b la vision démarre sans webcam, `person_tracker` s'arrête, `vision_status` reste), 15, 17, 18,
  20, 21 (M1-M4, M6 : `ATTENDU_MACHINES=5`).
- L'ancien compose et le nouveau COEXISTENT dans la branche jusqu'à la porte ; l'ancien, son
  Dockerfile, `sim.launch.py`, `launch-sim-in-docker.sh` et `banc-vision/docker-compose-x86.yml`
  sont supprimés dans le DERNIER commit de la sous-étape.
- **Porte** : (1) `docker compose up` → 4 conteneurs, domaine 43 lu dans chacun ; (2) **fumée
  complète verte DEUX fois de suite** sur le nouveau compose : 5, 4, 3, 12, machines 5, 21, 14,
  RTF ≥ 0,8 — les RTF et durées des deux passes sont notés dans `chantiers.md` à côté de ceux de
  la dernière fumée mono-conteneur ; (3) `validate-rehearsal-route.sh` et `-faults.sh` rejoués à
  la main, compteurs identiques à ceux d'avant ; (4) une séance « Chantiers » ouverte par David
  sur la page scène (boutons de répétition présents, 3 vues) ; (5) robot redéployé hors robot
  (le launch a changé) : 16 nœuds, `ecart-pi.sh` vert ; (6) `grep` : plus aucune mention de
  `dadou-sim-container`, `docker-compose-sim.yml`, `sim.launch.py` hors `docs/fumee/`, études
  et historiques.

### L2c — États du matériel simulé, page scène, vision sur la caméra Gazebo (Sonnet, relu par Opus)

Aucun chemin roues ni sécurité : topics en lecture seule, nœuds SIM-ONLY, page.

- Décisions 12, 13, 14 (`source_initiale`), 21 (M5, M7-M10 → `ATTENDU_MACHINES=10`).
- **Porte** : tests unitaires (logique pure des 4 états, littéraux gravés ; contrôle par mutation :
  fausser un état fait rougir un test) ; fumée complète verte, machines 10/10 ; captures de la
  page scène (bureau + téléphone) avec les deux panneaux, validées par David ; robot ET vision
  redéployés hors robot (`didier_web` et `didier_vision` changent) : `noeuds_attendus`,
  `ecart-pi.sh` vert ×2 ; sur le Pi, vérifié que `web_bridge` ne s'abonne à AUCUN `sim/etat/*`
  (domaine 42) et que `person_tracker` reste sur la webcam.

### L2d — CI : images + fumée courte (Sonnet)

- Décisions 9 (`xvfb`), 22. `fumee-courte.sh` d'abord rejoué vert sur le PC en `ECRAN=xvfb`
  (aucune dépendance à la session graphique), puis le workflow.
- **Porte** : job `images` vert deux fois, la seconde depuis le cache (durée notée) ;
  `fumee-courte` exécutée ≥ 3 fois, durées et RTF notés dans `chantiers.md` ; aucun secret dans
  les paramètres du dépôt ni dans le workflow (`grep secrets\.` = `GITHUB_TOKEN` seul) ; le
  compteur de la règle de promotion est ouvert (0/10). Pas de Pi.

### L2e — `~/ros2_ws/machine/` (Opus) — détachable

Opus : Ansible, données et secret sur les Pi, chemins lus par le bringup.

- Décision 19. Constantes de chemin (fait 17) : défauts de `DIDIER_DATA_DIR`/`DIDIER_VISION_DATA_DIR`,
  `json_dir`/`deploy_sha_file` du launch, `data_dir` de `data_edit`, Dockerfiles, 3 compose,
  `machine.yml` (`secrets_hote`, `telechargements_hote`), rôles `synchronise`/`conteneur`/`secrets`,
  unités systemd, `validate-data-edit.sh`, tests. `project_ros_dir` disparaît des `machine.yml`
  robot et vision.
- **Ordre de déploiement (par Pi, vision d'abord, robot ensuite)** : conteneur arrêté → tâche
  Ansible unique et idempotente « si `~/ros2_ws/machine` est absent et `~/ros2_ws/src/<projet>`
  présent : `mv` » (atomique : bases SQLite, voix, secret et `DEPLOY_SHA` suivent sans copie) →
  rsync habituel → image reconstruite → `up`. `src/robot`, `src/vision` entrent dans une liste
  d'effacement conditionnel (au cas où un ancien déploiement les recrée).
- **Retour arrière** : `git revert` de la sous-étape, puis sur chaque Pi
  `mv ~/ros2_ws/machine ~/ros2_ws/src/<projet>` et un déploiement depuis le commit rétabli ;
  l'image précédente est gardée sous le tag `:avant-l2e` jusqu'à la porte.
- **Porte** : fumée complète verte ; `fumee-courte` verte en CI ; les deux Pi déployés,
  `noeuds_attendus`, catalogue 6 familles et sha publiés par le robot, `chat_node` de la vision
  trouve voix et secret (démarrage `CHAT=true` 1 min, puis remis à `false`), `ecart-pi.sh` vert ×2
  avec inventaires regravés ; **preuve à blanc sur le Pi vision** (`~/ros2_ws` effacé, une
  commande, vert) ; `grep -rn "src/robot\|src/vision"` hors listes d'effacement, études et
  historiques = 0.

---

## 5. Interdits (tout le lot)

- **Chemin roues, code intouché** : `packages/didier_drive/` (tout), `didier_core/nodes/wheels_node.py`,
  `didier_core/actions/wheels.py`, `wheels_bridge`, `config/twist_mux.yaml`, les blocs
  `wheels_node`/`drive_launch` de `robot_app.launch.py`, `WHEELS_CMD_VEL_ENABLED`. Un
  `git diff --stat main` de chaque sous-étape le prouve au rapport.
- **Domaine 42 jamais en sim** : 43 en littéral dans le compose, revérifié par chaque entrée de
  conteneur sim et par `fumee.sh` ; aucun compose de `machines/sim/` ne lit `ROS_DOMAIN_ID` dans
  l'environnement.
- **Aucun déploiement sur un robot aux roues câblées** (verrou du protocole caméra inchangé) ;
  les Pi de L2 sont hors robot.
- `web_drive`, `rehearsal`, `use_sim_time` n'apparaissent dans aucun fichier qui part sur un Pi.
- Jamais d'extinction du poste, jamais `fumee.sh --et-dodo`, jamais de commit dans une plage sans
  commit, jamais `git add -A` (Nextcloud ressuscite des fichiers après `git mv`).
- Dépôt public : aucun secret dans une image, un workflow, un journal d'artefact ; aucun nom
  d'employeur, de client, de poste ou de réseau de travail.
- Une seule sim à la fois sur le PC : ne jamais arrêter un conteneur de sim qu'on n'a pas lancé.

---

## 6. Hors L2 (pour ne pas y toucher par inadvertance)

La couture pilote DANS les nœuds du cœur (L3 pour le code neuf, L5 pour le cœur) ; la
télécommande neuve et son état publié (L4) ; la sono et son conteneur (L3 — elle s'ajoutera comme
5e service) ; `didier_jeu` dans le conteneur robot (lots A) ; l'observateur `validation_sim`
(L1d-2 — son emplacement est prêt, décision 17) ; le retrait de `didier_sim` et
`didier_rehearsal` de la liste de packages du Pi robot ; un réseau sim isolé ; la poussée
automatique d'images ARM ; ruff, mypy, pytest-cov, ansible-lint (question 3).

---

## 7. Replis décidés d'avance

| Si… | Alors |
|---|---|
| `audio_node` ou `system_node` meurt sur x86 sans carte son (porte L2a-3) | monter `machines/sim/asound-sim.conf` (`pcm.!default` de type `null`) dans le service `robot` ; s'il meurt encore : arrêt, rapport — aucune retouche de ces nœuds sans David |
| RTF < 0,8 à 4 conteneurs sur les cœurs 8-15 (porte L2b-2) | `FUMEE_COEURS` passe à 8 cœurs (valeur à graver après mesure) ; si toujours < 0,8 : caméras gz à 5 Hz pendant la fumée ; sinon arrêt, rapport |
| V-R3 ou A1 perdent des points seulement en multi-conteneurs | pas de retouche des épreuves ni des valeurs gravées : diagnostic (RTF d'abord, mémoire `feedback-sim-rtf-et-cli`), rapport ; l'ancien compose reste en place tant que la porte n'est pas passée |
| Le BuildKit d'un Pi n'honore ni `.dockerignore` de contexte nommé ni `COPY --exclude` | arrêt de L2a pour la vision : son Dockerfile garde le contexte principal actuel, et la sim reconstruit la disposition par un dossier d'assemblage — à re-spécifier, pas à improviser |
| `pid: "service:monde"` refusé ou instable | les préconditions `pgrep` visant un processus du robot sont remplacées par `docker exec` depuis `fumee.sh` AVANT l'épreuve ; le corps des épreuves reste intact |
| Gazebo ne démarre pas sous Xvfb en CI | `fumee-courte` tourne sans `monde` graphique : `gz sim -s` sans capteurs caméra (monde `stage-sans-camera.sdf`), M5 sortie du compteur CI (9) et dite sur la page |

---

## 8. Estimation (honnête)

| Sous-étape | Modèle | Travail d'agent | Machine (fumées, Pi) | Présence de David |
|---|---|---|---|---|
| L2a | Opus | 4-5 h | 2 constructions sur Pi (≈ 35 min + ≈ 20 min), 1 fumée | brancher les 2 Pi ; webcam du banc |
| L2b | Opus | 10-14 h | 3 à 5 fumées (≈ 50 min), 1 déploiement robot | une séance sur la page scène |
| L2c | Sonnet + relecture Opus | 6-8 h | 1-2 fumées, 2 déploiements | valider 2 captures |
| L2d | Sonnet | 5-7 h | ≥ 5 allers-retours CI (20-40 min à froid) | aucune |
| L2e | Opus | 4-6 h | 2 constructions sur Pi, 1 fumée, preuve à blanc | brancher les 2 Pi |

**Total ≈ 30-40 h d'agent en 5 à 7 séances.** L'incertitude est dans L2b (le vrai bringup n'a
jamais tourné en sim ; 4 colcon et 4 participants DDS de plus sur les cœurs réservés) : compter
×1,5 si une épreuve bouge. L2c et L2d sont indépendantes l'une de l'autre après L2b ; L2e peut
attendre sans bloquer L3 sur le fond, seulement sur le nommage (question 2).

---

## 9. Questions pour David (avec mon défaut)

1. **Pilote sim « au niveau du topic » en L2** (décision 3) : le robot simulé exécute tout le
   vrai bringup, mais le matériel est rejoué par des nœuds à part, pas par une variante de pilote
   dans chaque nœud réel. **Mon défaut : oui** — refaire les nœuds de génération 1 maintenant,
   c'est payer deux fois (L5 les réécrit) et s'approcher des roues. Dis non seulement si tu veux
   voir en sim la rampe et les animations du code réel avant L5.
2. **Renommer les chemins des Pi en L2e** (`~/ros2_ws/machine/`). **Mon défaut : oui, en dernier**,
   pour que le gabarit L3 naisse avec le bon nom. Si tu préfères ne plus toucher aux Pi d'ici la
   refonte électrique : L2 se clôt à L2d, et L3 hérite de la question.
3. **Outils de qualité « à porter par L2 »** (décision du 07/11 : ruff, pytest-cov, mypy sur le
   code neuf, ansible-lint, hadolint). **Mon défaut : hadolint seul dans L2d** ; le reste devient
   un petit lot « CI palier 2 » après L2 (ruff sur tout le dépôt reformaterait du code roues :
   il lui faut ses propres règles d'exclusion, pas un passager clandestin).
