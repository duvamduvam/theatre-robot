# machines/sim

Le PC de David : la simulation et ses épreuves (lot L1e-4c, 11/11 ; sim multi-conteneurs depuis
L2b, 14/11). Rien d'ici ne part sur un Pi. Domaine ROS **43** (le vrai robot est sur 42), posé en
littéral dans le compose et revérifié par chaque entrée de conteneur.

**Un conteneur par machine de Didier, construit avec le MÊME Dockerfile que son Pi**, plus le
`monde` (spec `docs/spec-L2-sim-multi-conteneurs.md`) :

| Service (conteneur `didier-sim-<service>`) | Image locale | Ce qui y tourne |
|---|---|---|
| `monde` | `monde/Dockerfile` (x86 seul) | Gazebo, pont gz, matériel simulé (servos, LED), répétition, sélecteur de jeu, **épreuves** ; `GZ_IP=127.0.0.1` (A1 intermittent, 11/11) ; depuis A0-2 (19/11) le **lidar C1 simulé** (`scan`, 10 Hz, 500 rayons, son propre pont `pont_lidar`) et, dans le monde `stage`, l'obstacle (`sim/obstacle_pose`) et le passant (`passant_sim_node`, `sim/passant`) des épreuves du corps sûr |
| `robot` | `machines/robot/docker/Dockerfile` | le VRAI `robot_app.launch.py` (18 nœuds, chaîne roues en `use_sim_time`, corps sûr `corps_sur` devant `twist_mux` depuis A0-4) + `complement_sim.launch.py` (`face_sim`, `validation_sim_node`) |
| `vision` | `machines/vision/docker/Dockerfile` | `vision.launch.py`, `CHAT=false`, aucun secret ; sans webcam `person_tracker` s'arrête (L2c : caméra Gazebo) |
| `telecommande` | Dockerfile x86 legacy | `controller_node` **sans interface** (`TELECOMMANDE_SANS_IHM=1`, 18/11) : ses éditeurs de topics tournent, aucune fenêtre sur le bureau |

```
cd machines/sim
docker compose build                                   # 1re fois, ≈ 15 min (puis cache)
HEADLESS=true WORLD=chantiers REHEARSAL=true FACE=true docker compose up -d
docker compose down
```

| Chemin | Rôle |
|---|---|
| `docker-compose.yml` | les 4 services ; variables : `HEADLESS`, `WORLD`, `WEB_PORT`, `FACE`, `FACE_PORT`, `DATA_EDIT`, `DIDIER_LIDAR_POSE` (« x y z lacet » du lidar dans `base_link`, vide = face avant à 25 cm ; seul `couverture_poses.py` la change), et SIM-ONLY `WEB_DRIVE`, `REHEARSAL` |
| `docker-compose.banc.yml` | surcouche « Didier à l'arrêt » sur le service `vision` : webcam, son, secret de `~/.config/didier/`, variables `CHAT_*` (`docker compose -f docker-compose.yml -f docker-compose.banc.yml up -d`) |
| `docker-compose.tete.yml` | surcouche « tête » (16/11) sur le service `vision`, pour l'épreuve de conversation : chat sans micro ni son, mouvement à la voix, réflexion coupée, les deux secrets de la tête (`vision-conf-secret`, `secrets.env` → Anthropic en direct) en lecture seule ; la fumée ne la pose qu'après avoir trouvé les deux fichiers (`docker compose -f docker-compose.yml -f docker-compose.tete.yml up -d`) |
| `monde/` | Dockerfile et entrée du conteneur `monde` (garde 43, colcon de ses packages, `monde.launch.py`) |
| `robot/entree.sh` | entrée SIM du conteneur `robot` : garde 43, ménage SHM, arguments de la sim (dont `corps_sur_config:=/home/ros2_ws/sim/corps_sur.yaml`, A0-4), complément sim |
| `robot/corps_sur.yaml` | configuration du corps sûr pour la SIM (A0-4, colonne « sim » de la spec A0 §5.4), montée en lecture seule dans le conteneur `robot` ; refusée hors domaine 43 |
| `menage-shm.sh` | ménage de la mémoire partagée Fast DDS (18/11), appelé en tête des entrées de `monde` et `robot` : ports SHM vides de plus d'une minute (un seul bloquait sans fin un nœud du robot à chaque démarrage) puis `fastdds shm clean` (`docs/operations.md` § Mémoire partagée Fast DDS) |
| `banc-vision/` | `asound-pc.conf` (alias ALSA du banc) et `audio_banc.py` (choix micro/sortie, automatique à chaque séance) |
| `validate-*.sh`, `pub.sh` | épreuves rejouables, montées dans `/home/ros2_ws/` du conteneur `monde` : `docker exec didier-sim-monde bash /home/ros2_ws/<script>` ; `validate-corps-sur.sh` (CS, A0-4, 25 verdicts) exige le monde `stage` (`WORLD=stage`) ; `validate-conversation.sh` (CONV, 16/11) exige la surcouche tête |
| `capture_topics.py`, `captures.sh` | mesures des épreuves (16/11) : enregistreur rclpy (PRÊT avant l'épreuve, JSONL + dernières valeurs, arrêt propre) et sa bibliothèque bash, montés dans `monde` ; captures sous `$DIDIER_SIM_JOURNAUX/log/captures/` — plus aucune mesure par `ros2 topic echo` (`docs/operations.md` § Mesures des épreuves) |
| `corps_sur_bringup.py` | contrôle de la fumée (A0-4, 21/11), lancé dans `monde` (montage `machines/`) : le corps sûr DU BRINGUP est ARME avant chaque épreuve qui fait rouler Didier ; réarme un VERROU `capteur_perdu` spontané, deux fois au plus par épreuve, jamais une autre cause |
| `fumee.sh`, `fumee_page.py`, `coeurs_reserves.py` | fumée nocturne (lot F) : rejoue tout sur main ; pages et `historique.jsonl` dans `docs/fumee/`, journaux bruts LOCAUX (`~/tmp/didier-fumee/`) |
| `didier-fumee.{service,timer}`, `installer-fumee.sh` | minuterie systemd utilisateur ; **relancer `installer-fumee.sh` depuis le checkout de main** après un déménagement |
| *(hors dépôt)* `$DIDIER_SIM_JOURNAUX`, défaut `~/tmp/didier-sim/` | journaux de la sim depuis le 16/11 (ni dans git ni sur Nextcloud) : `log/` partagé par `monde` et `robot` (`robot.log`, `rehearsal/`, `jeu/`, `tickets/`, `captures/`), `log-vision/`, `log-telecommande/` ; `fumee.sh` et `seance-chantiers.sh` le créent, à la main : `mkdir -p` avant `up` (sinon Docker le crée root) |

Les épreuves tournent dans `monde`, qui partage son espace de processus avec les trois autres
(`pid: "service:monde"`, sim seulement) : leurs `pgrep`/`pkill` voient les nœuds du robot.

Mode d'emploi : `docs/operations.md` (sections Sim, Séance « Chantiers », Fumée automatique).
