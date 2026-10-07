# robot_rehearsal — salle de répétition simulée (SIM-ONLY)

Package **autonome** (aucun import `robot.*` ni `dadou_utils_ros`) qui n'existe
que dans le conteneur de simulation. Il n'est **jamais** lancé par
`robot_bringup` : un test (`robot/tests/unit/test_rehearsal_contract.py`)
refuse toute référence à ce package dans le code embarqué.

Étude : [`docs/etude-repetition-simulee.md`](../../../docs/etude-repetition-simulee.md)
(§11 architecture et tests, §12 variante retenue).

## Lot R1 — Didier chemine seul

| Fichier | Rôle |
|---|---|
| `robot_rehearsal/contracts.py` | topics, plafonds durs (= ceux du suivi), hystérésis POI |
| `robot_rehearsal/route.py` | logique PURE : validation d'itinéraire, suiveur de waypoints, veilleur de POI |
| `robot_rehearsal/route_driver_node.py` | node fin : `/odom` → Twist sur `cmd_vel_follow` (mux prio 20), événements `rehearsal/poi_event` |
| `config/rue.yaml` | le trajet vers le Hangar à Bananes + les points d'intérêt |
| `launch/rehearsal.launch.py` | lance `route_driver`, OFF par défaut |

## Lot R2 — le régisseur de pannes (canal technique)

| Fichier | Rôle |
|---|---|
| `robot_rehearsal/scenario.py` | logique PURE : validation d'un scénario YAML (refus explicite), expansion des `t: random` avec la graine → timeline déterministe |
| `robot_rehearsal/director.py` | ordonnanceur PUR : start/stop/skip/end, exclusion par cible, re-bornage des durées, abort |
| `robot_rehearsal/fault_relay.py` | relais PUR : pass / drop / delay / freeze / zero, échéance, **chien de garde** (sans battement du régisseur > 1 s → passant) |
| `robot_rehearsal/process_faults.py` | pause (SIGSTOP/SIGCONT) et kill (SIGTERM) de la **liste blanche** (`contracts.PAUSABLE/KILLABLE`) — jamais la chaîne de sécurité |
| `robot_rehearsal/director_node.py` | node fin : exécute la timeline, bat à 5 Hz, journalise (JSONL, `robot.diagnostic.journal`) dans `/home/ros2_ws/log/rehearsal/` |
| `robot_rehearsal/fault_relay_node.py` | node fin générique : un point de relais de `contracts.RELAYS` |
| `config/scenarios/demo.yaml` | chaque type de panne une fois, instants fixes — le scénario de V-R2 |

Types de pannes : `relay` (sur `cmd_vel_follow` : freeze = continue sur sa
dernière consigne, zero = arrêt net, drop = à-coups, delay = réagit en retard),
`pause` (visage figé, servos muets, route coupée → deadman), `kill` de
`route_driver` (respawn par le launch après 5 s, puis `route on` = le
reboot-prétexte), `speed` (batterie faible), `instruction` (canal joué,
publié sur `rehearsal/instruction` — consommateur au lot R3).

Commandes : `rehearsal/cmd` = `start` | `stop` | `abort`. Le journal de la
séance est la **source de vérité du débrief** (ce qui a été tiré, quand) — à
lire **après**, jamais pendant (étude §4.3).

**Vérification V-R2** : `docker exec dadou-sim-container bash /home/ros2_ws/validate-rehearsal-faults.sh`
(start, chien de garde en gelant le régisseur pendant un `zero`, reboot →
respawn → `route on`, couverture du scénario au journal).

**Règles de séance**
- La télécommande (prio 100) écrase toujours la route ; le deadman 400 ms reste derrière.
- Le suivi de personne (`follow`) doit être **OFF** pendant la route : même créneau du mux.
- `route` : `on` / `off` / `restart` (StringTime). `route_speed` : nombre 0..1 (le fader).
- **La vraie télécommande** (dépôt `dadou_control_ros`) pilote la séance : lancer son
  compose avec `ROS_DOMAIN_ID=43 SLIDERS_PROFILE=repetition` — le joystick reste
  les roues (prio 100, écrase la route), **le fader 1 du boîtier devient
  `route_speed`** (fader à zéro = Didier s'arrête), le fader 2 le cou. Profils
  décrits dans `dadou_control_ros/docs/interfaces.md`.

**Dans le conteneur sim** (`conf/docker/sim`, domaine 43) :
```bash
# 1. la sim avec la rue (HEADLESS=true recommandé) :
WORLD=rue ANIMATIONS=true FACE=true WEB=true docker compose -f docker-compose-sim.yml up -d
# 2. la chaîne roues, puis la route :
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch robot_drive drive.launch.py use_sim_time:=true'
docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch robot_rehearsal rehearsal.launch.py'
# 3. partir :
docker exec dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 topic pub -1 route robot_interfaces/msg/StringTime "{msg: \"on\"}"'
```

**Vérification d'intégration V-R1** (rejouable, dans le conteneur, chaîne roues + rehearsal lancés, route OFF) :
```bash
docker exec dadou-sim-container bash /home/ros2_ws/validate-rehearsal-route.sh
```
(départ, POI enter/exit, la télécommande écrase, zéro franc à `route off`, arrivée au hangar — seuils gravés dans le script.)

**Tests** : `.venv/bin/pytest robot/tests/unit/test_route_follower.py robot/tests/unit/test_rehearsal_contract.py`
(valeurs gravées ; chaque lot inclut une passe de mutation, cf. étude §11.4).
