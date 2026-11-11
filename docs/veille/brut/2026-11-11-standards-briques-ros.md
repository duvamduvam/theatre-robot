# Briques standard ROS 2 pour un petit robot — rapport de collecte brut

Date de consultation : 2026-11-11. Rapport de collecte, pas un livrable : aucune conclusion ni recommandation.

Légende : **[LU]** = lu sur la page chargée ; **[EXTRAIT]** = vient du résumé d'un moteur de recherche, page non chargée (à vérifier avant usage).

## 0. Couverture

Budget : mandat de 7 questions pour un plafond de 12 pages. 11 pages chargées (dont 3 en 404 et 1 bloquée par Anubis). Le reste vient d'extraits de recherche.

Couvert (partiellement) : Q1 (changements Lyrical, topic-based), Q2 (collision_monitor, tutoriel suivi), Q3 (RP2040, linorobot2), Q4 (rosbag2, Foxglove), Q6 (Groot2, py_trees_ros), Q7 (OTA, Isaac ROS).

NON couvert : `diagnostic_updater`/`diagnostic_aggregator`, `ros2doctor`, Lichtblick/PlotJuggler/Rerun (Q4) ; nœuds lifecycle, launch_testing, composition, supervision systemd/respawn (Q5, entièrement) ; Nav2 route server/docking/MPPI/EasyNav (Q2) ; TurtleBot 4, Andino, ROSbot, articubot (Q1) ; `industrial_ci`, `setup-ros`, buildx cross-compilation, Ansible, Mender/RAUC/balena (prix et retours) ; ROSCon 2025/2026 (aucune vidéo/slide ROSCon lue) ; prix Groot2 Pro.

## 1. Tableau de synthèse

| Sujet | Fait | Type | Source |
|---|---|---|---|
| Lyrical : API handles/export dépréciées depuis Jazzy supprimées | oui | LU | discourse 59593 (06/11/2026) |
| diff_drive_controller Lyrical | `publish_rate` supprimé ; `tf_frame_prefix_enable` déprécié | LU | idem |
| Interface matérielle Python | aucune mention | LU (absence) | idem |
| topic_based_ros2_control / joint_state_topic_hardware_interface | existe (C++, via topics) | EXTRAIT | docs.ros.org |
| rosbag2 stockage par défaut | mcap | LU | README rosbag2 jazzy |
| rosbag2 snapshot | tampon circulaire mémoire, `--snapshot-mode`, `--max-cache-size`, service `~/snapshot` | LU | idem |
| Foxglove Free | 0 $/mois ; 10 Go ; 3 utilisateurs ; 5 appareils ; 1 projet | LU | foxglove.dev/pricing |
| Foxglove Pro | 20 $/mois + usage | LU | idem |
| Collision Monitor | LaserScan/PointCloud2/Range ; contourne le costmap ; ~4-5 ms/frame pour 360 pts | LU | api.nav2.org jazzy |
| linorobot2_hardware | micro-ROS série, Pico/Pico 2/ESP32 ; pas de ros2_control | LU | github |
| micro-ROS pico sdk | branche kilted ; 685 commits ; 11 issues ; pas d'archive | LU | github |
| Groot2 | dernière version 1.8.1 (2026-01-18) ; prix non public sur la page | LU | github Groot2 |
| Isaac ROS 5.0 | 22/09/2026, Lyrical ; Pixi non mentionné | LU | aicybr |

## 2. Q1 — ros2_control

### Source A — Annonce "ros2_control in Lyrical Luth: what's new"
- URL : https://discourse.openrobotics.org/t/ros2-control-in-lyrical-luth-whats-new/59593.md
- Consultée le 2026-11-11 ; nature : post officiel de la communauté ROS (Discourse), daté du 2026-11-06. **[LU]**
- Lyrical marqué « stable/released » dans ros2_control, ros2_controllers, control_toolbox, realtime_tools ; date de sortie exacte de Lyrical non donnée par la page.
- Supprimés : API handles/export dépréciées depuis Jazzy. Les composants matériels n'utilisent plus `export_state_interfaces()` / `export_command_interfaces()` : le framework crée les interfaces depuis la balise `<ros2_control>` ; accès par `set_state/get_state/set_command/get_command`. `StateInterface`/`CommandInterface` ne se construisent plus depuis un pointeur double brut.
- Contrôleurs chaînables : `on_export_*_interfaces_list()` (shared pointers).
- ros2_controllers : `action_execution_timeout` retiré de joint_trajectory_controller ; diff_drive_controller : `publish_rate` retiré ; `tf_frame_prefix_enable` déprécié (`tf_frame_prefix: ""` ou `"~"`), idem mecanum et omni.
- Autres : `switch_controller` strict par défaut ; `configure_controller` n'accepte que des contrôleurs non configurés ; le spawner saute les contrôleurs déjà configurés sauf `--reconfigure` ; un contrôleur en échec désactive toute sa chaîne ; fréquences d'update arrondies ; joint_state_broadcaster ne publie plus `dynamic_joint_states` ; contrôleurs JointGroup position/velocity/effort dépréciés au profit de `forward_command_controller`.
- Voie Python : la page n'en mentionne aucune.

### Source B — Migration Jazzy→Kilted (diff_drive)
- Extrait de recherche **[EXTRAIT]**, pages https://control.ros.org/kilted/doc/ros2_controllers/doc/migration.html et PR https://github.com/ros-controls/ros2_controllers/pull/1653 non chargées : les paramètres `has_velocity_limits`, `has_acceleration_limits`, `has_jerk_limits` auraient été supprimés (valeurs NaN à la place). Section Kilted vide dans l'extrait ; non vérifié.

### Source C — topic_based_ros2_control
- URLs : https://www.github.com/PickNikRobotics/topic_based_ros2_control ; https://docs.ros.org/en/jazzy/p/joint_state_topic_hardware_interface (la page a retourné un blocage Anubis, rien lu). **[EXTRAIT]**
- Interface matérielle `SystemInterface` pilotant un robot par topics (`joint_commands_topic`, `joint_states_topic`) ; paquets binaires existent pour Humble ; aucune interface matérielle purement Python trouvée (dépôts « Python bindings pybind11 » signalés mais non vérifiés).
- Coût CPU sur Pi 4 : **non trouvé**.

### Source D — linorobot2_hardware
- URL : https://www.github.com/linorobot/linorobot2_hardware ; consultée 2026-11-11 ; dépôt de code officiel du projet, date non affichée. **[LU]**
- Microcontrôleurs : Pico W (RP2040), Pico 2 W (RP2350), ESP32/-S2/-S3, Waveshare gendrv. micro-ROS en USB série par défaut, Wi-Fi UDP déconseillé sur Pico (bande passante). Firmware : abonné `/cmd_vel`, publie `/odom/unfiltered`, `/imu/data`.
- Branches : lyrical et jazzy supportées ; humble non supportée. Drivers : 2-entrées, 1-entrée, BTS7960, ESC. ros2_control : non mentionné.
- Teensy déprécié : **[EXTRAIT]** (docs linorobot2, https://linorobot.github.io/linorobot2).
- TurtleBot 4, Andino, ROSbot, articubot : **non trouvé** (non cherchés faute de budget).

## 3. Q2 — Nav2

### Source E — README Collision Monitor (Nav2 Jazzy)
- URL : https://api.nav2.org/nav2-jazzy/html/md_nav2_collision_monitor_README.html ; consultée 2026-11-11 ; documentation officielle. **[LU]**
- Filtre sur `cmd_vel` du Controller Server, « contourne le costmap et les planificateurs », niveau arrêt d'urgence ; CPU, pas de certification de sécurité temps réel.
- Entrées : LaserScan, PointCloud2, Range. Zones : polygone, footprint (approach seulement), cercle, VelocityPolygon. Actions : stop, slowdown, approach (limit listée sans définition).
- Performance : ~4-5 ms/frame pour un scan 360 points ; ~4-20 ms pour 24 000 points. Nœud séparé Collision Detector (topic `collision_detector_state`, `action_type: none`).
- Nécessité d'une carte : la page ne le dit pas. Noms de topics et Twist/TwistStamped : non précisés sur cette page.
- **[EXTRAIT]** (Nav2 docs, discourse) : défaut Twist en Jazzy, TwistStamped en Kilted+ ; un blogueur Foxglove place le monitor en aval du sélecteur de modes (https://foxglove.dev/blog/autonomous-navigation-with-lekiwi-part-2) ; un fil Robotics StackExchange signale un échec des nœuds lifecycle de Nav2 quand le collision_monitor n'a pas de lidar (https://backiee.wasmer.app/https_robotics_stackexchange_com/a/114631), sans réponse acceptée vue.
- `collision_monitor` seul devant un twist_mux sans le reste de Nav2 : **non trouvé** comme retour documenté.

### Source F — Suivi dynamique
- URL https://docs.nav2.org/tutorials/docs/navigation2_dynamic_point_following.html : 404 au chargement. **[EXTRAIT]** : le tutoriel indique que la détection de la personne est hors périmètre ; plus le détecteur est rapide plus le robot est réactif ; une issue GitHub signale le tutoriel périmé (https://www.github.com/ros-navigation/docs.nav2.org/issues).

### Retours Pi 4 / lidar **[EXTRAIT]**
- Aucun benchmark Nav2 + slam_toolbox sur Pi 4 4 Go + lidar sous Jazzy trouvé.
- Pi 4, Ubuntu 22.04, Gazebo+RViz+slam_toolbox : 4 cœurs à 95-98 % (https://forum.hello-robot.com/t/odom-drifting-far-away-when-using-slam-toolbox/1440, date non lue) — charge incluant la simulation.
- Pi 5 Jazzy : 35-75 % CPU total (https://discourse.openrobotics.org/t/designing-a-mobile-rover-with-a-top-mounted-manipulator-without-degrading-2d-lidar-based-slam-and-nav2-performance/51703 ; https://groups.google.com/g/hbrobotics/c/Rrh5IJ3zsAU), dates non lues.
- Exigences matérielles minimales officielles, route server, docking, MPPI 2025-26, EasyNav : **non trouvé / non cherché**.

## 4. Q3 — micro-ROS

### Source G — micro_ros_raspberrypi_pico_sdk
- URL : https://github.com/micro-ROS/micro_ros_raspberrypi_pico_sdk ; consultée 2026-11-11 ; dépôt officiel. **[LU]**
- Branche affichée : kilted (images Docker `...:kilted`) ; 685 commits ; aucune release listée ; non archivé ; aucun avis de dépréciation ; 11 issues ouvertes, 9 PR ouvertes. Date du dernier commit : non affichée.
- Page https://micro.ros.org/docs/overview/hardware/ : 404 au chargement. **[EXTRAIT]** : RP2040 listé avec USB et Wi-Fi UDP (264 ko RAM).
- Alternatives **[EXTRAIT]** : rmw_zenoh Tier-1 depuis Kilted (https://discourse.openrobotics.org/t/wire-breaking-change-in-rmw-zenoh-for-ros-2-jazzy/44367) ; Zenoh-pico dans micro-ROS = fork communautaire expérimental eSOL (https://github.imc.re/esol-community/rmw_zenoh_pico) ; aucune déclaration officielle eProsima sur la maintenance de micro-ROS trouvée. `rosserial` « mort » : non cherché.

## 5. Q4 — Observabilité

### Source H — README rosbag2 (branche jazzy)
- URL : https://raw.githubusercontent.com/ros2/rosbag2/jazzy/README.md ; consultée 2026-11-11 ; documentation officielle. **[LU]**
- Plugin par défaut : mcap (`get_default_storage_id()`) ; plugins fournis : mcap, sqlite3.
- Snapshot : `--snapshot-mode` / `StorageOptions.snapshot_mode`, tampon circulaire en mémoire, taille `--max-cache-size` (exemple YAML `max_cache_size: 20000000`), vidage par le service `~/snapshot`.
- Compression désactivée par défaut ; zstd seul format. Des paquets peuvent être perdus à fort débit (CPU, réseau, stockage lent). Coût mesuré sur Pi : **non trouvé**.
- **[EXTRAIT]** : MCAP défaut à partir d'Iron (https://foxglove.dev/blog/mcap-as-the-ros2-default-bag-format ; changelog https://docs.ros.org/en/iron/p/rosbag2_cpp/standard_docs/CHANGELOG.html) ; `--max-cache-duration` mentionné, non confirmé.

### Source I — Page de tarifs Foxglove
- URL : https://foxglove.dev/pricing ; consultée 2026-11-11 ; page de prix de l'éditeur. **[LU]** Devise « $ » (monnaie non nommée, taxes non précisées ; HT/TTC non précisé).
- Free : 0 $/mois ; 10 Go stockage ; 3 utilisateurs de visualisation ; 5 appareils ; 1 projet ; query 1 h ; indexation 100 Go ; bande passante 100 Go ; 10 layouts d'organisation ; rétention non indiquée ; « will remain free forever ».
- Pro : 20 $/mois + usage, mensuel résiliable ; 3 sièges dev inclus puis 42 $/utilisateur/mois ; sièges basic illimités 0 $ ; 5 appareils inclus puis 20 $/appareil/mois ; IA 5 $/utilisateur/mois inclus ; inclus : 1 To stockage, 1 To indexation, 100 Go bande passante, 3 projets.
- Enterprise : sur devis ; on-premises, données auto-hébergées, BYO storage = Enterprise seulement. Academic : 0 $ (adresse .edu/.ac).
- Hors ligne : la FAQ dit que les fichiers locaux fonctionnent « sans connectivité Internet » ; la page n'indique pas de restriction par plan sur l'application desktop.
- Lichtblick, PlotJuggler, Rerun, Rviz web, diagnostic_updater/aggregator, ros2doctor : **non trouvé / non cherché**.

## 6. Q5 — Robustesse d'exécution
Non couvert (aucune recherche menée).

## 7. Q6 — Arbres de comportement

### Source J — Groot2 (GitHub)
- URL : https://github.com/BehaviorTree/Groot2 ; consultée 2026-11-11 ; page de dépôt avec changelog. **[LU]**
- Dernière version 1.8.1, 2026-01-18. Licence PRO avec EULA (1.1.1, 2023-08-12), activation hors ligne, licences flottantes (1.8.0). Termes de licence, fonctions gratuites vs PRO, prix : non indiqués sur la page. Prix Groot2 Pro : **non trouvé** (page behaviortree.dev/groot non chargée).
- **[EXTRAIT]** BehaviorTree.CPP sous licence MIT, 4.10.0 sur l'index ROS (https://index.ros.org/p/behaviortree_cpp) ; un fil évoque une licence PRO flottante par siège (https://identichosting.duckdns.org/BehaviorTree/Groot2/discussions/38).

### Source K — py_trees_ros (GitHub)
- URL : https://www.github.com/splintered-reality/py_trees_ros ; consultée 2026-11-11. **[LU]**
- Matrice : Rolling, Lyrical, Kilted, Jazzy, Humble ; badge branche 2.6.x ; branche devel 1 255 commits ; 19 issues ; aucun avis de non-maintenance ; aucune release listée ; licence non nommée sur la page.
- **[EXTRAIT]** index.ros.org (https://index.ros.org/p/py_trees_ros/) : version 2.5.0 Jazzy, mise à jour 2026-07-16 (voir contradictions).

## 8. Q7 — Build / CI / déploiement

### Source L — Fil Discourse « Is OTA for ROS 2 robots a solved problem? »
- URL : https://discourse.openrobotics.org/t/is-ota-for-ros-2-robots-a-solved-problem/58933.md ; consultée 2026-11-11 ; forum communautaire, fil du 2026-10-18 au 2026-10-23. **[LU]**
- Auteur du fil : aucun outil OTA propre à ROS 2 trouvé ; updater maison Pi (images conteneur depuis releases GitHub, health checks, rollback) ; difficulté : l'updater ne peut pas se mettre à jour lui-même.
- Réponses : un vendeur (Agency Tool Company) dit que l'OTA n'est pas résolu (promotion) ; Toradex : OSTree/Uptane (Torizon). Mender, balena, RAUC, snaps, Ansible : nommés mais aucun retour d'expérience dans le fil.
- Un utilisateur dit utiliser Pixi + RoboStack sur Ubuntu et macOS (labos étudiants), avec des problèmes de discovery sur macOS.

### Source M — Isaac ROS 5.0
- URL : https://aicybr.com/blog/nvidia-isaac-ros-5-agentic-robotics-ros-lyrical ; consultée 2026-11-11 ; article tiers, pas la doc NVIDIA. **[LU]**
- Annoncé le 2026-09-22 à ROSCon (Toronto) ; distro supportée Lyrical (Ubuntu 24.04 selon l'article) ; paquets buildfarm ; caméra RealSense « Docker-only » ; **Pixi et RoboStack non mentionnés**.
- **[EXTRAIT]** : la doc Isaac Sim indique une installation ROS 2 via Pixi, Jazzy seulement (https://docs.isaacsim.omniverse.nvidia.com/latest/migration_guides/isaac_sim_6_0/ros2_workspace_package_migration.html). Aucune source trouvée sur « Isaac ROS 5.0 passé à Pixi ».
- **[EXTRAIT]** diapos FOSDEM 2026 (Docker arm64, Mender) : https://fosdem.org/2026/events/attachments/MUXVUK-prod-ros-bazel/slides/266995/slides-p_luhl499.html ; Mender Hub (buildx arm64 en artefact) : https://hub.mender.io/t/ota-updates-to-kubernetes-workloads-at-the-edge/8322.
- `industrial_ci`, `setup-ros`, prix Mender/balena : **non trouvé / non cherché**. ROSCon 2025/2026 retours flotte : seuls des articles fournisseurs Canonical (https://canonical.com/blog/roscon-2025) en extrait.

## 9. Contradictions et incertitudes

- py_trees_ros : index.ros.org (extrait) annonce 2.5.0 (mise à jour 2026-07-16) ; la page GitHub affiche un badge 2.6.x ; le miroir OpenEmbedded affiche 2.4.0-1. Version courante non tranchée.
- Isaac ROS 5.0 : l'article lit Ubuntu 24.04 + Lyrical ; la doc Lyrical/NVIDIA primaire non lue. Lyrical est généralement associé à Ubuntu 26.04 (linorobot2 le dit pour sa branche lyrical) : à vérifier, contradiction apparente.
- Pixi dans Isaac ROS : question de départ non confirmée ; seul Isaac Sim est documenté sur Pixi.
- Foxglove : devise « $ » sans taxe précisée ; plan Free « forever » selon l'éditeur, mais un extrait tiers (pricingsaas.com) suggère un historique de changements de tarif, non lu.
- Dépréciations Jazzy→Kilted de diff_drive (limites) : seulement en extrait.
- 404/blocages au chargement : docs.nav2.org (collision monitor node, tutoriel suivi), micro.ros.org/docs/overview/hardware, docs.ros.org joint_state_topic_hardware_interface (Anubis).
- Date du dernier commit des dépôts micro-ROS pico, linorobot2_hardware, py_trees_ros : non affichée.
- "APIs dépréciées supprimées à l'automne 2026" : confirmé pour Lyrical (post du 2026-11-06) ; calendrier exact de sortie de Lyrical non lu.

## 10. Non trouvé / douteux
Cf. section 0. En plus : coût CPU de ros2_control sur Pi 4 ; ordre de grandeur de ressources minimales Nav2 officielles ; fonctionnement du collision_monitor derrière un twist_mux sans Nav2 complet ; prix Groot2 Pro ; prix Mender/balena/RAUC ; état de maintenance officiel de micro-ROS en 2026 ; rosserial ; lifecycle/launch_testing/supervision (Q5).
