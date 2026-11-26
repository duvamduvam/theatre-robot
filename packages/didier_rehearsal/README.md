# didier_rehearsal — salle de répétition simulée (SIM-ONLY)

Package **autonome** (aucun import `robot.*` ni `dadou_utils_ros`) qui n'existe
que dans le conteneur de simulation. Il n'est **jamais** lancé par
`didier_bringup` : un test (`robot/tests/unit/test_rehearsal_contract.py`)
refuse toute référence à ce package dans le code embarqué.

Étude : [`docs/etude-repetition-simulee.md`](../../docs/etude-repetition-simulee.md)
(§11 architecture et tests, §12 variante retenue).

## Lot R1 — Didier chemine seul

| Fichier | Rôle |
|---|---|
| `didier_rehearsal/contracts.py` | topics, plafonds durs (= ceux du suivi), hystérésis POI |
| `didier_rehearsal/route.py` | logique PURE : validation d'itinéraire, suiveur de waypoints, veilleur de POI |
| `didier_rehearsal/route_driver_node.py` | node fin : `/odom` → Twist sur `cmd_vel_follow` (mux prio 20), événements `rehearsal/poi_event` |
| `config/rue.yaml` | le trajet vers le Hangar à Bananes + les points d'intérêt |
| `launch/rehearsal.launch.py` | lance `route_driver`, OFF par défaut |

## Lot R2 — le régisseur de pannes (canal technique)

| Fichier | Rôle |
|---|---|
| `didier_rehearsal/scenario.py` | logique PURE : validation d'un scénario YAML (refus explicite), expansion des `t: random` avec la graine → timeline déterministe |
| `didier_rehearsal/director.py` | ordonnanceur PUR : start/stop/skip/end, exclusion par cible, re-bornage des durées, abort |
| `didier_rehearsal/fault_relay.py` | relais PUR : pass / drop / delay / freeze / zero, échéance, **chien de garde** (sans battement du régisseur > 1 s → passant) |
| `didier_rehearsal/process_faults.py` | pause (SIGSTOP/SIGCONT) et kill (SIGTERM) de la **liste blanche** (`contracts.PAUSABLE/KILLABLE`) — jamais la chaîne de sécurité |
| `didier_rehearsal/director_node.py` | node fin : exécute la timeline, bat à 5 Hz, journalise (JSONL, `robot.diagnostic.journal`) dans `/home/ros2_ws/log/rehearsal/` |
| `didier_rehearsal/fault_relay_node.py` | node fin générique : un point de relais de `contracts.RELAYS` |
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

**Vérification V-R2** : `docker exec didier-sim-monde bash /home/ros2_ws/validate-rehearsal-faults.sh`
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
ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=chantiers
```

## Lot A1 — le sélecteur de jeu décide (02/11)

```bash
ros2 launch didier_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
```

`jeu:=true` remappe le régisseur sur **`jeu/chat_move`** (publié par le sélecteur
`packages/didier_jeu` du mono-dépôt) au lieu de `rehearsal/chat_move` : un seul
décideur du corps (lot S1 : la bouche transmet les ordres de David, son `stop` est
toujours relayé). Le launch démarre **lui-même** `jeu_node` (respawn),
sous la même condition que le remap : jamais de remap sans relais du `stop` (si
le répertoire est illisible, le sélecteur ne fait que relayer stop/go). Il passe
aussi `jeu:=true` au régisseur (paramètre `jeu`, lot S1) : **les lubies du
scénario ne partent pas** (`fault_skip`, `reason: "jeu"`), le sélecteur a les
siennes. Défaut `false` = séance Chantiers inchangée (V-R3). `scenario:=jeu-a1` :
scénario VIDE (0 bug, 0 lubie), qu'il faut quand même **starter** (hors séance, la
reprise du sélecteur, d'origine `didier`, est ignorée). `rehearsal/objects` porte depuis A1 `x`, `y`
de chaque objet (le sélecteur oriente le regard d'une lubie).

## Lot I1 — mouvement à la voix (étude §13.11, 22/10)

Didier peut demander à repartir ou à s'arrêter : la clé `"marche": "go"|"stop"`
de son JSON de fin part de `chat_node` (dépôt vision, seulement si
`CHAT_MOUVEMENT` est posé — banc de répétition) sur **`rehearsal/chat_move`**.
Contrat depuis le lot S1 (25/11, `docs/spec-S1-ordres-propositions.md`) :
`{"cmd": "go"|"stop"|"pause", "origine": "david"|"didier"}` — `david` pour un mot
d'arrêt et ce que David demande, `didier` pour le `marche: stop` interprété par le
LLM (et, en `jeu:=true`, les reprises et lubies du sélecteur) ; les anciennes formes
(`json.dumps("go"|"stop")`, objet sans `origine`) sont lues `david`
(`contracts.lire_chat_move`). Le régisseur décide (`director.VoiceMove`, pur) et
agit par `route` / `route_speed`, comme pour les lubies. Tout ordre est journalisé
`voice_move` avec son `origine` (`effect` : `close_lubie` | `resume` | `relaunch` |
`hold` | `ignored` + `reason`).

- **Séance (règle symétrique, lot S1)** : hors séance, toute marche d'origine
  `didier` est ignorée (`hors_seance`), `stop` comme `go` — Didier suit sa route ;
  celle de David est appliquée, `stop` comme `go`. En séance, les deux s'appliquent.
  Origine inconnue : `stop` lu `david`, `go` ignoré (`origine_inconnue`). Supprimé :
  l'ancienne asymétrie (tout stop appliqué, tout go ignoré hors séance).

- **go** : ferme la lubie active (`closed_by: "voix"`, la vitesse en vigueur
  EST rendue), sinon lève l'arrêt vocal (vitesse d'avant, plafonnée), sinon
  relance une route OFF **par reboot** — `route_state` latché `off` ET
  `route_state_cause` latchée `boot` (salve de 3 `on`, confirmée par
  `route_state`). **Jamais** après une extinction par commande (cause `cmd`,
  ou `off`/`false`/`0` vu sur `route`) : `route_off_par_david` ; cause jamais
  reçue : `cause_inconnue`. Anti-rebond 2 s.
- **stop** : `route_speed 0` **toujours** republié (même pendant une lubie ;
  hors séance, s'il vient de David), arrêt vocal **toujours** posé sans jamais
  écraser une vitesse déjà retenue ; pas d'anti-rebond.
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

« Va voir les anneaux » : Didier roule jusqu'à ~1,5 m de l'objet — plus loin d'un gros objet,
voir **Ordre** (demi-tour s'il l'a dépassé), pivote face à lui, s'arrête. SIM-ONLY (vérité terrain).

- **Vocabulaire** : au démarrage, le régisseur publie LATCHÉ
  `rehearsal/objects` = `[{"name", "desc"}]` (ordre de l'itinéraire). Champs
  YAML par POI : `desc` (≤ 6 mots, ce qu'on voit ; absent = le nom) et `alias`
  (mots de David). Un nom/alias normalisé (minuscules, sans accents ni
  article de tête) ne désigne qu'UN POI : refus au chargement sinon.
- **Tableau des objets (lot O1, 18/11)** : `rehearsal/objects` porte aussi `alias` et, pour
  un POI qui a un tour, `cx`, `cy` (centre de collision) et `emprise` (orbite − 1 m, majorant de
  l'emprise au sol ; revue O1 du 19/11, à la place du rayon d'orbite) ; son lecteur est
  `didier_perception/objets_node`, qui publie `scene/objets`. La régie s'y abonne : un geste
  vers un objet le désigne par son **`id`** (`carte/<poi>`), résolu une fois par la bouche ou
  le sélecteur ; elle vise la position du TABLEAU (le centre de l'objet) et ne résout plus
  aucun nom. Sans `id` connu, ou tableau muet depuis 3 s (`theatre_contrats.objets.PEREMPTION_S`,
  la péremption commune aux lecteurs) : `unknown` ; objet sans position en repère monde : `no_position`.
  Ses refus propres restent (route coupée par David, pose, 40 m).
- **Demande** : `rehearsal/chat_move` porte aussi `{"cmd": "aller_voir",
  "objet": …, "id": …}`. Arbitrage journalisé `aller_voir` (avec l'`id`) : `accepted` | `unknown` |
  `no_position` | `route_off_by_david` | `no_pose` (pose vérité terrain > 600 ms) |
  `too_far` (> 40 m). Accepté en séance comme hors séance ; l'arrêt vocal
  est levé à la vitesse du « go » (jamais au-dessus du fader ni d'une
  batterie), une lubie active est fermée (`closed_by: "voix"`).
- **Ordre** : `route_goto` (`{"name","x","y","standoff"}` ou `"cancel"`). **Standoff**
  (`director.standoff_pour`) = `max(1,5 ; emprise + 0,5 + 0,5 ; emprise + garde + 0,5)` du CENTRE
  de l'objet : emprise (`emprise_m` du tableau), rayon balayé de Didier (`GOTO_DIDIER_RAYON_M`,
  roulette arrière, revue O1), **garde du corps sûr** (A0-4, 22/11 : `caisse.x_avant` +
  `zones.marge_arret_m`, lus au démarrage dans le fichier du corps sûr de la machine,
  paramètre `corps_sur_config` du régisseur, 0,30 + 0,60 = 0,90 en sim), marge (`GOTO_MARGE_M` :
  tolérance d'arrivée 0,3 + 0,2 de jeu). Taille inconnue : emprise présumée
  `GOTO_EMPRISE_INCONNUE_M` = 1,5 m, soit 2,9 m ; borné à 40 m. Banc 2,5 m, table basse 2,1 m.
  Garé plus près (1,7 m, CONV D5 du 21/11), Didier était dans sa propre bande ARRET et ne
  repartait plus. Configuration absente ou refusée : le régisseur ne démarre pas.
  `route_driver` reste la SEULE sortie Twist (`cmd_vel_follow`, prio 20) :
  il suspend le suivi et joue `didier_rehearsal/goto.py` (ALIGN -> DRIVE ->
  FACE -> ARRIVED, pivots ≤ 0,6 rad/s, v ≤ fader × la croisière du suivi
  (0,4 m/s), abandon à 60 s, à 1,5 × la distance initiale ou au CALAGE
  (consigne > 0,1 m/s sans 5 cm de déplacement en 2 s), zéro si odométrie
  périmée, pose non finie ou fader à 0). Standoff accepté : 0,8 à 40 m. Le
  même objet redemandé pendant la manœuvre : rien (le délai ne repart pas).
  `route_state` : `on` / `off` / `goto` / `arrived`.
- **Fader à 0** (manœuvre ET suivi d'itinéraire) : zéro franc, aucun pivot,
  publié à chaque tick (le créneau 20 du mux reste tenu).
- **Lubie de la cible** : son « enter » arrive pendant l'approche (quand le
  standoff est sous le rayon du POI) ; pendant la manœuvre et à l'arrivée, le régisseur la SAUTE
  (`lubie_skipped`, `reason: goto_target`) — Didier joue l'objet lui-même.
  Les autres lubies restent possibles.
- **Arrêt** : « stop » vocal et abort publient `cancel` ; `cancel`,
  `route off`, `route on` -> zéro franc immédiat. Ceinture : route_driver
  refuse aussi un ordre tant que la route est OFF par David.
- **Reprise** : « go », Route ON ou geste du fader devant l'objet -> la route
  rejoint D'ABORD le point du chemin le plus proche (projection sur le segment courant,
  `RouteFollower.rejoin_point`, décision du 22/11), puis repart vers le waypoint le plus proche
  DEVANT (le long du chemin).
- Journal : `goto_arrived`, `goto_cancelled` (`by`), `goto_abort` (d'après
  l'état latché), `goto_result` (détail publié par route_driver sur
  `route_goto_result` : `timeout`, `max_travel`, `stalled`, `cancelled`…),
  `goto_rejoin`.
- **Réponse au geste** (15/11) : CHAQUE geste arbitré (aller_voir, tourner,
  avancer, tour_de ; jamais go/stop) publie sur `rehearsal/chat_move_reply`
  `{"demande": <le dict reçu>, "effect": <celui du journal>, "reason":
  <sous-raison d'invalid | null>, "name": <nom de l'ordre si accepté, celui
  que route_goto_result renverra | null>, "source": "director"}` (VOLATILE),
  publiée AVANT l'ordre sur route_goto. Le chat
  en fait une fin de geste ÉCHOUÉE dite en personnage (sinon Didier affirmait
  un tour refusé) ; le sélecteur de jeu y clôt son engagement.

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
  `python3 tools/compute_tours.py ../didier_sim/worlds/chantiers.sdf config/chantiers.yaml > config/chantiers_tours.yaml`.
  Centre = milieu des collisions de l'objet (pas l'ancre du POI), rayon = rayon
  objet + 1 m arrondi au 0,1 supérieur (1,5 à 6 m) ; pas de tour si un autre
  objet frôle l'anneau — bordure de quai et façades comprises (seul le sol
  `esplanade` est ignoré, `GROUND_MODELS`). Fichier frère absent (itinéraire `rue`) = aucun tour.
- **Intention** : `{"cmd": "tour_de", "objet": "<texte>", "sens": "gauche"|"droite"}`
  (absent = gauche = trigo, l'objet à gauche de Didier). Journal `tour_de`
  (`accepted`, `unknown`, `no_tour`, `invalid` + `reason` sens,
  `route_off_by_david`, `no_pose`, `too_far` jugé au CENTRE du tour), même
  réponse au geste que M1. `rehearsal/objects` porte `"tour": true|false`
  (15/11) : le chat dit au LLM de quels objets il peut faire le tour.
  Acceptation : celle d'« aller voir » (lubie de l'objet tourné sautée).
- **Ordre** `route_goto` : `{"name": "tour de <poi>", "orbit_x", "orbit_y",
  "orbit_r", "orbit_dir": 1|-1}` -> approche du point du cercle le plus proche
  (ALIGN/DRIVE), ORBIT (croisière 0,35 m/s, correction radiale, angle balayé
  intégré), FACE vers le centre. Abandons : `off_track` (|d − r| > 1 m),
  délais (16/11) : approche max(60 s, |pose − E| / 0,1) depuis l'ordre, puis
  orbite 60 s + 2πr / 0,1 depuis l'ENTRÉE sur le cercle ; distance ≤ 1,5 ×
  (approche + 2πr), calage, fader 0, cancel. Le même tour (même sens)
  redemandé est ignoré.

Tests : `test_goto_tour.py`, `test_tours.py`, `test_director_tour.py`,
`test_route_driver_tour.py`.

## Regarder une séance en direct

- **Vue 3D** : la sim tourne en headless ; on y branche une fenêtre à chaud,
  sans rien redémarrer : `docker exec -d didier-sim-monde bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && gz sim -g'`.
  Clic droit sur Didier → « Follow ». ⚠️ Ne pas fermer la fenêtre pendant une séance.
- **Caméra de Didier + régie** : http://localhost:8765 (pont web du conteneur robot, toujours lancé) ; **visage LED** : http://localhost:8766 (`FACE=true`).
- **Après la séance** : `machines/robot/scripts/rehearsal/capture_seance.py` (images caméra aux
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

**Dans la sim multi-conteneurs** (`machines/sim/`, domaine 43 ; la chaîne roues tourne dans le
conteneur robot, la répétition se lance dans `monde`) :
```bash
# 1. la sim avec la rue (HEADLESS=true recommandé) :
WORLD=rue FACE=true docker compose up -d
# 2. la route (journal dans /tmp/rehearsal.log : V-R1 le lit) :
docker exec -d didier-sim-monde bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 launch didier_rehearsal rehearsal.launch.py > /tmp/rehearsal.log 2>&1'
# 3. partir :
docker exec didier-sim-monde bash -c 'source /opt/ros/$ROS_DISTRO/setup.sh && source /home/ros2_ws/install/setup.bash && ros2 topic pub -1 /didier/route theatre_interfaces/msg/StringTime "{msg: \"on\"}"'
```

**Vérification d'intégration V-R1** (rejouable, dans `monde`, rehearsal lancé comme ci-dessus — sortie
dans `/tmp/rehearsal.log`, sinon T2/T5 ne lisent rien —, route OFF) :
```bash
docker exec didier-sim-monde bash /home/ros2_ws/validate-rehearsal-route.sh
```
(départ, POI enter/exit, la télécommande écrase, zéro franc à `route off`, arrivée au hangar — seuils gravés dans le script.)

**Tests** : `.venv/bin/pytest robot/tests/unit/test_route_follower.py robot/tests/unit/test_rehearsal_contract.py`
(valeurs gravées ; chaque lot inclut une passe de mutation, cf. étude §11.4).
