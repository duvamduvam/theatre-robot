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
publié sur `chat_instruction` depuis le lot R3 — ex-`rehearsal/instruction`).

Commandes : `rehearsal/cmd` = `start` | `stop` | `abort`. Le journal de la
séance est la **source de vérité du débrief** (ce qui a été tiré, quand) — à
lire **après**, jamais pendant (étude §4.3).

**Vérification V-R2** : `docker exec dadou-sim-container bash /home/ros2_ws/validate-rehearsal-faults.sh`
(start, chien de garde en gelant le régisseur pendant un `zero`, reboot →
respawn → `route on`, couverture du scénario au journal).

## Lot R3 — « chantiers » : 20 bugs, 30 lubies (étude §13)

| Nouveauté | Contrat |
|---|---|
| déclencheur POI | `t: poi` + `poi: <nom>` : part sur l'`enter` du POI (`rehearsal/poi_event`), **une seule fois** (sauté pour cible occupée = pas de seconde chance). `p` (0..1) = tirage **au chargement** avec la graine, après les `t: random` ; les écartés sont listés `undrawn` dans `scenario_loaded`. Jamais atteint = `skipped` à la fin |
| type `lubie` | `{poi, text?, stop?: true, restore?: 1.0}`, cible `speed`, max 120 s : consigne sur `chat_instruction` (`text`, sinon champ `lubie` du POI) + `route_speed` 0 ; à la fin `""` + la vitesse en vigueur (seulement si `stop`, voir plus bas) |
| type `chat` | `{op: delay\|garble\|deaf\|mute\|phantom, params}`, cible `chat`, max 60 s (`phantom` ponctuel) : JSON `{"op", "params", "until_ms"}` sur `rehearsal/chat_fault`, `{"op": "pass"}` à la fin (sauf `phantom` : ponctuel, cible propre `chat:phantom`, rien à lever). Durée 0 refusée hors phantom (0 = plafond 60 s côté chat_node). Pas de chien de garde : chat_node borne aussi à 60 s |
| `instruction` | bornée (max 120 s) : `""` publié à la fin si durée > 0 ; à 0, ponctuelle comme en R2 |
| `route_file` (régisseur) | le MÊME itinéraire que `route_driver` : un POI inconnu ou une lubie sans texte = refus au démarrage, tirés ou non |

Les messages EXACTS (instruction, lubie, chat) sortent de `director.messages()`,
pur et gravé par test — mêmes chaînes que les tests du dépôt vision.

**Fermeture au fader, vitesse rendue, reset** (revue adversariale du 14/10, tests `test_director_node.py`) :
- Pendant une lubie `stop`, une consigne `route_speed` EXTERNE (fader, page) qui s'écarte de plus de 0,05 de la vitesse d'avant la lubie la **ferme aussitôt** : `fault_stop` avec `closed_by: fader`, consigne levée, vitesse **non rendue** (David vient de la fixer). Ré-émissions du boîtier et jitter ≤ 0,05 ne ferment rien ; le régisseur reconnaît l'écho de ses propres publications.
- Fin d'un `speed` ou d'une lubie : la vitesse rendue est la dernière consigne externe, sinon `speed:=` du launch, sinon `restore` du scénario (dernier recours).
- `stop`/`abort` avant `start` ne fait rien ; `start` après la fin **rejoue** la séance (même timeline, `scenario_reset` au journal).
- POI franchi hors séance : journalisé `poi_enter_ignored` (`before_start`/`ended`), pas mémorisé — envoyer `start` AVANT `route on`.

`config/chantiers.yaml` : 30 POI dans l'ordre réel de la marche (Nefs → Titan
grise), chacun avec `lubie` (envoyée telle quelle au chat) et `fermeture` (pour
David au débrief, lue par personne en machine). ⚠️ Positions **provisoires**
(polyligne droite) : le lot monde (`chantiers.sdf`) les recale.
`config/scenarios/chantiers.yaml` : les 20 bugs du §13.5 en `t: random` + une
lubie `t: poi` par POI (`p: 0.4`, la Titan grise toujours).

```bash
ros2 launch robot_rehearsal rehearsal.launch.py route:=chantiers scenario:=chantiers
```

## Lot I1 — mouvement à la voix (étude §13.11, 22/10)

Didier peut demander à repartir ou à s'arrêter : la clé `"marche": "go"|"stop"`
de son JSON de fin part de `chat_node` (dépôt vision, seulement si
`CHAT_MOUVEMENT` est posé — banc de répétition) sur **`rehearsal/chat_move`**
(StringTime, `json.dumps("go"|"stop")`). Le régisseur est le **seul**
consommateur ; il décide (`director.VoiceMove`, pur) et agit par `route` /
`route_speed`, comme pour les lubies. Tout ordre est journalisé `voice_move`
(`effect` : `close_lubie` | `resume` | `relaunch` | `hold` | `ignored` + `reason`).

- **go** : ferme la lubie active (`closed_by: "voix"`, la vitesse en vigueur
  EST rendue), sinon lève l'arrêt vocal (vitesse d'avant, plafonnée), sinon
  relance une route OFF **par reboot** — `route_state` latché `off` ET
  `route_state_cause` latchée `boot` (salve de 3 `on`, confirmée par
  `route_state`). **Jamais** après une extinction par commande (cause `cmd`,
  ou `off`/`false`/`0` vu sur `route`) : `route_off_par_david` ; cause jamais
  reçue : `cause_inconnue`. Hors séance : ignoré. Anti-rebond 2 s.
- **stop** : `route_speed 0` **toujours** republié (même hors séance, même
  pendant une lubie), arrêt vocal **toujours** posé sans jamais écraser une
  vitesse déjà retenue ; pas d'anti-rebond.
- **Règle générale** (défaut trouvé en sim le 22/10) : tant qu'un arrêt vocal
  est posé, le régisseur ne publie **jamais** de vitesse non nulle, sauf par
  « go » ou levée au fader — une lubie qui finit ne rend rien, une panne
  `speed` ne publie rien (`"suppressed_by": "voice_hold"` au journal).
- Vitesse en vigueur : celle d'une panne `speed` active, sinon le fader.
  Le fader lève l'arrêt vocal sans rien publier ; abort / fin de séance aussi
  (Didier reste à l'arrêt) et annulent une salve de relance.

`route_driver` publie `route_state_cause` (latché, JSON `"boot"` | `"cmd"`) :
`boot` au démarrage, `cmd` à chaque extinction par commande, tout format.

Tests : `test_director.py` (logique pure) et `test_director_node.py` (node), section I1.

## Lot M1 — « aller voir » (spec `docs/spec-aller-voir.md`, 31/10)

« Va voir les anneaux » : Didier roule jusqu'à ~1,5 m de l'objet (demi-tour
s'il l'a dépassé), pivote face à lui, s'arrête. SIM-ONLY (vérité terrain).

- **Vocabulaire** : au démarrage, le régisseur publie LATCHÉ
  `rehearsal/objects` = `[{"name", "desc"}]` (ordre de l'itinéraire). Champs
  YAML par POI : `desc` (≤ 6 mots, ce qu'on voit ; absent = le nom) et `alias`
  (mots de David). Un nom/alias normalisé (minuscules, sans accents ni
  article de tête) ne désigne qu'UN POI : refus au chargement sinon.
- **Demande** : `rehearsal/chat_move` porte aussi `{"cmd": "aller_voir",
  "objet": …}`. Arbitrage journalisé `aller_voir` : `accepted` | `unknown` |
  `route_off_by_david` | `no_pose` (pose vérité terrain > 600 ms) |
  `too_far` (> 40 m). Accepté en séance comme hors séance ; l'arrêt vocal
  est levé à la vitesse du « go » (jamais au-dessus du fader ni d'une
  batterie), une lubie active est fermée (`closed_by: "voix"`).
- **Ordre** : `route_goto` (`{"name","x","y","standoff"}` ou `"cancel"`).
  `route_driver` reste la SEULE sortie Twist (`cmd_vel_follow`, prio 20) :
  il suspend le suivi et joue `robot_rehearsal/goto.py` (ALIGN -> DRIVE ->
  FACE -> ARRIVED, pivots ≤ 0,6 rad/s, v ≤ fader × la croisière du suivi
  (0,4 m/s), abandon à 60 s, à 1,5 × la distance initiale ou au CALAGE
  (consigne > 0,1 m/s sans 5 cm de déplacement en 2 s), zéro si odométrie
  périmée, pose non finie ou fader à 0). Standoff accepté : 0,8 à 40 m. Le
  même objet redemandé pendant la manœuvre : rien (le délai ne repart pas).
  `route_state` : `on` / `off` / `goto` / `arrived`.
- **Fader à 0** (manœuvre ET suivi d'itinéraire) : zéro franc, aucun pivot,
  publié à chaque tick (le créneau 20 du mux reste tenu).
- **Lubie de la cible** : son « enter » arrive pendant l'approche (standoff <
  rayon) ; pendant la manœuvre et à l'arrivée, le régisseur la SAUTE
  (`lubie_skipped`, `reason: goto_target`) — Didier joue l'objet lui-même.
  Les autres lubies restent possibles.
- **Arrêt** : « stop » vocal et abort publient `cancel` ; `cancel`,
  `route off`, `route on` -> zéro franc immédiat. Ceinture : route_driver
  refuse aussi un ordre tant que la route est OFF par David.
- **Reprise** : « go », Route ON ou geste du fader devant l'objet -> la route
  repart vers le waypoint le plus proche DEVANT (le long du chemin).
- Journal : `goto_arrived`, `goto_cancelled` (`by`), `goto_abort` (d'après
  l'état latché), `goto_result` (détail publié par route_driver sur
  `route_goto_result` : `timeout`, `max_travel`, `stalled`, `cancelled`…),
  `goto_rejoin`.

Tests : `test_goto.py`, `test_route_objects.py`, `test_director_goto.py`
(purs), `test_route_driver_goto.py`, `test_director_node_goto.py` (nodes,
rclpy simulé). Passe de mutation listée en tête de chaque fichier.

## Lot M2 — gestes chiffrés (spec `docs/spec-aller-voir.md` §7, 31/10)

Décision de David : des gestes GÉNÉRAUX CHIFFRÉS (composables plus tard par
un planificateur), angle **+ = gauche** (ROS). Même canal que M1.

- **Intentions** (`rehearsal/chat_move`) : `{"cmd": "tourner", "angle_deg": a}`
  (0 < |a| ≤ 180, compat `"sens"` gauche/droite/demi_tour = +90/−90/+180) ;
  `{"cmd": "avancer", "metres": m}` (0,1 ≤ m ≤ 5, négatif refusé : pas de recul).
  Journal `tourner` / `avancer` (`accepted`, `invalid` + `reason`
  illisible|hors_bornes|recul, `route_off_by_david`, `no_pose`).
- **Acceptation** : exactement celle d'« aller voir » (arrêt vocal levé, lubie
  fermée, salve annulée, `stop`/abort -> `cancel`, reprise au « go »).
- **Ordres** `route_goto` : `{"turn_rad"}` (pivot seul, rotation intégrée,
  15 s, translation ≤ 1 m, calage en rotation) et `{"forward_m"}` (DRIVE à
  cap tenu, arrivée à la projection, sans FACE, 10 s + 4 s/m, ≤ 1,5 × m
  parcourus, calage 2 s). Pivots (y compris ceux d'« aller voir ») : |ω| ≤
  0,6 × fader, plancher 0,15. Un geste redemandé = nouvel ordre (pas de cumul). Noms d'état
  communs aux deux nodes : `pivot +90°`, `avancer 2 m` (`goto.turn_name` /
  `forward_name`).
- « Regarder » (tête) n'est PAS ici : topic `look`, consommé par
  `gaze_follower_node` (prod, `robot/nodes`).

Tests : `test_goto_gestes.py`, `test_director_gestes.py`,
`test_route_driver_gestes.py` ; regarder : `robot/tests/unit/test_gaze_look.py`.

## Lot M3 — « faire le tour de X » (spec `docs/spec-aller-voir.md` §8, 01/11)

Un tour en UN geste (David : pivot + 1 m + relance à chaque réplique, « super
laborieux »). Même canal que M1/M2.

- **Géométrie** : `config/chantiers_tours.yaml`, GÉNÉRÉ — ne pas éditer.
  Regénérer après toute retouche du monde ou de l'itinéraire (le test
  `test_tours.py` rougit sinon) :
  `python3 tools/compute_tours.py ../robot_sim/worlds/chantiers.sdf config/chantiers.yaml > config/chantiers_tours.yaml`.
  Centre = milieu des collisions de l'objet (pas l'ancre du POI), rayon = rayon
  objet + 1 m arrondi au 0,1 supérieur (1,5 à 6 m) ; pas de tour si un autre
  objet frôle l'anneau — bordure de quai et façades comprises (seul le sol
  `esplanade` est ignoré, `GROUND_MODELS`). Fichier frère absent (itinéraire `rue`) = aucun tour.
- **Intention** : `{"cmd": "tour_de", "objet": "<texte>", "sens": "gauche"|"droite"}`
  (absent = gauche = trigo, l'objet à gauche de Didier). Journal `tour_de`
  (`accepted`, `unknown`, `no_tour`, `invalid` + `reason` sens,
  `route_off_by_david`, `no_pose`, `too_far` jugé au CENTRE du tour).
  Acceptation : celle d'« aller voir » (lubie de l'objet tourné sautée).
- **Ordre** `route_goto` : `{"name": "tour de <poi>", "orbit_x", "orbit_y",
  "orbit_r", "orbit_dir": 1|-1}` -> approche du point du cercle le plus proche
  (ALIGN/DRIVE), ORBIT (croisière 0,35 m/s, correction radiale, angle balayé
  intégré), FACE vers le centre. Abandons : `off_track` (|d − r| > 1 m),
  délai 60 s + 2πr / 0,1, distance ≤ 1,5 × (approche + 2πr), calage, fader 0,
  cancel. Le même tour (même sens) redemandé est ignoré.

Tests : `test_goto_tour.py`, `test_tours.py`, `test_director_tour.py`,
`test_route_driver_tour.py`.

## Regarder une séance en direct

- **Vue 3D** : la sim tourne en headless ; on y branche une fenêtre à chaud,
  sans rien redémarrer : `docker exec -d dadou-sim-container bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && gz sim -g'`.
  Clic droit sur Didier → « Follow ». ⚠️ Ne pas fermer la fenêtre pendant une séance.
- **Caméra de Didier + régie** : http://localhost:8765 (`WEB=true`) ; **visage LED** : http://localhost:8766 (`FACE=true`).
- **Après la séance** : `conf/scripts/rehearsal/capture_seance.py` (images caméra aux
  instants choisis + trajectoire, à lancer DANS le conteneur) puis `carte_seance.py`
  (rue vue de dessus + vitesse aux roues, pannes du journal en couleur). Exemple :
  `docs/pictures/repetition-simulee/2026-10-08_carte-seance-demo.png`.

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
