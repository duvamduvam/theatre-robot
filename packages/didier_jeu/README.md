# didier_jeu — le sélecteur de jeu de Didier (lot A1, SIM-ONLY)

Ce package répond à « pourquoi et quand Didier agit » : un **arbre py_trees**
décide de ce qui est permis, et un **score** choisit l'action. Les offres, les
pistes de personnes et les pulsions alimentent ce choix ; chaque décision est
journalisée avec son `pourquoi`. Spec :
`docs/spec-A1-selecteur-de-jeu.md` (décisions §8 du 02/11) ; le pourquoi se
trouve dans `legacy/dadou_robot_ros/docs/etude-autonomie-improvisation.md` §4.1-4.2.

**SIM-ONLY** : `jeu_node` refuse de démarrer hors `ROS_DOMAIN_ID=43`. Il utilise
le garde-fou `check_domain` de `robot_rehearsal`, importé tel quel ; son message
d'erreur dit donc « robot_rehearsal refuse de démarrer », ce qui est connu. Le
refus a lieu **avant** `rclpy.init`. **Aucun Twist** : les roues ne bougent que
par des demandes au régisseur (`jeu/chat_move`), qui les arbitre, puis par
`route_driver`.

## Le contrat

| Topic | Sens | Format |
|---|---|---|
| `jeu/console` | page scène → sélecteur | StringTime JSON `{"cmd": "va_la"\|"joue_avec"\|"ignore"\|"reviens"\|"plus_lent"\|"stop"\|"go", "cible"?, "presence": true}` ; la page envoie `{"presence": true}` à 2 Hz (battement) |
| `jeu/intention` | sélecteur → page | **latché**, republié toutes les 0,5 s : `{"action", "cible", "pourquoi", "t_ms", "fin_prevue_ms", "reste_ms", "verrou", "jauges", "proposition"?}` ; `"action": "rien"` au repos, jamais vide |
| `jeu/chat_move` | sélecteur → régisseur | même payload que `rehearsal/chat_move` ; le régisseur y est remappé par `rehearsal.launch.py jeu:=true` |
| `jeu/journal` | sélecteur → page (+ fichier) | une ligne JSONL (format boîte noire `robot.diagnostic.journal`) par message |
| `animation` | sélecteur → animations_node | nom de séquence (JSON chaîne) |
| `look` | sélecteur → gaze_follower | `{"angle_deg", "hold_ms"}` (« regarder », spec-aller-voir §7.1) |
| entrées | | `vision/person_box`, `rehearsal/poi_event`, `rehearsal/chat_move` (la bouche), `chat_transcript` (rôle `david` = parole entendue), `chat_situation`, `mission_state`, `route_state`, `route_state_cause`, `route_goto_result`, `animation_state`, `rehearsal/objects` (avec `x`, `y` depuis A1), `/ground_truth/odom` |

Les noms `jeu/*` sont définis dans `theatre_contrats.topics`. Ceux du régisseur
viennent de `robot_rehearsal.contracts`, qui est importé et non recopié.

## Ce qui décide (dans l'ordre de l'arbre)

1. **Arrêt vocal** : un `stop` venu de la bouche ou de la console est **relayé
   dès sa réception, sans passer par le score**. Il pose un verrou sur tout
   déplacement jusqu'au `go` **de celui qui l'a posé** : un `go` de la console
   (David) lève tout ; un `go` de la bouche ne lève que le stop de la bouche,
   jamais un stop de David. STOP CONTENUS de la page envoie aussi ce `stop`.
   Une Route OFF par David (`route_state_cause = cmd`) compte comme un stop de
   David. Il n'y a jamais de `go` automatique après un stop de David.
2. **Superviseur absent** (mode `exigeant` seulement ; le défaut en A1 est `suppose`) :
   aucun déplacement.
3. **Ordre macro** : `va_la` vise un objet de `rehearsal/objects` (→ `aller_voir`)
   ou une piste (→ `tourner` vers elle, puis `avancer` 1 m). `joue_avec` vise la
   piste regardée, approches répétées permises. `ignore` coupe les offres de
   la cible pendant 30 s et annule une lubie en attente ou une reprise.
   `reviens` envoie `go`. `plus_lent` = **moins souvent** (décision de David du
   02/11) : toutes les périodes réfractaires sont multipliées par 2 pendant 60 s.
   Ce n'est pas une vitesse de roues : le sélecteur n'en a aucune.
   **Garde de distance** de toute approche : jamais si la hauteur de boîte de
   la piste atteint `approche.hauteur_max` (0,55, soit environ 2,7 m).
4. **Action engagée** : elle se finit. Seule une offre de valeur ≥ 0,9 (la
   bouche) peut l'interrompre.
5. **Choisir** : le score de chaque candidat (immobilité comprise), puis
   l'hystérésis (+15 % pendant 300 ms), et jamais deux changements à moins de 2 s.

**Lubie** : un `poi_event enter` fait naître une offre `objet`. Didier réclame
l'arrêt (par l'intention) **et** l'amorce (`look` vers l'objet, angle calculé
depuis l'odométrie vérité terrain, donc SIM-ONLY ; à défaut de pose, il s'en
tient à l'intention). Il ne demande `stop` que si la console n'a dit ni `ignore`
ni `va_la` dans les 3 s. Il propose ensuite « repartir ? » et envoie `go` de
lui-même après **90 s de silence** : toute parole entendue (`chat_transcript`,
rôle `david`) remet le compteur à zéro (décision de David du 02/11).

**Un arrêt de Didier par 2 min** couvre tout arrêt de route qu'il cause : lubie,
approche de sa propre initiative, demande de mouvement de la bouche. Un ordre
de David n'en est jamais un.

**Metteur en scène** : un mot-clé d'expression ou de regard biaise le score. Un
mot-clé de **déplacement** (« approche ») ne fait bouger Didier que si le texte
nomme une piste (« p3 »). Dans ce cas, c'est au plus **un pas par piste nommée**,
et jamais au-delà de la garde de distance.

Chaque offre née, personne ou objet, reçoit en ≤ 1 s une ligne de décision :
un choix, ou un « il continue … : » qui dit pourquoi il ne réagit pas.

**Répertoire** : les séquences qui ont une clé `types`, **sauf** celles de `bugs/`
et **sauf toute séquence à piste `wheels`** (A1 n'a pas de corps sûr). Les types
`bonjour` donnent un « accueil » (réponse à une personne) ; `random` et `little
move` donnent une expression spontanée (servie par l'ennui). Les déplacements
sont dans `config/deplacements.yaml` ; `reculer` en est absent, car le régisseur
refuse tout `avancer` négatif. Deux séquences du même nom dont l'une est jouable
sont refusées au chargement ; des homonymes sans emploi sont seulement listés.

**Journal** : les phrases sont écrites pour David (`phrases.py`), par exemple
« il s'ennuie (0,40) → une expression spontanée « aurore » ». Pulsions et offres
sont photographiées à l'instant du choix. Une ligne sans `pourquoi` n'est jamais
perdue : elle part avec « (absent — bug) » et un compteur.

**Mode dégradé** (`relais.RelaisSeul`) : si le répertoire, les réglages ou le
vocabulaire sont illisibles, `jeu_node` démarre quand même. Il relaie alors
`stop`/`go` (bouche et console) sans aucune initiative et écrit `degrade` au
journal. Le chemin d'arrêt vocal ne dépend jamais d'un JSON.

Tous les chiffres sont dans `config/reglages.yaml` (« réglage de départ, se
règle au journal »), et **gravés** dans `test/test_reglages.py`.

## Lancer (conteneur sim)

```bash
ros2 launch robot_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
```

Ce launch démarre **lui-même** `jeu_node` (respawn), sous la même condition que
le remap de la bouche. Il ne faut jamais le lancer à part : un remap sans relais
perdrait le `stop` de la bouche.

Le journal est écrit dans `/home/ros2_ws/log/jeu/<horodatage>_<pid>_jeu.jsonl`.
Vérification rejouable : `validate-jeu-a1.sh` (voir `legacy/dadou_robot_ros/docs/operations.md`).

## Tester

```bash
legacy/dadou_robot_ros/.venv/bin/python -m pytest packages/didier_jeu/test -q
```

Chaque règle chiffrée est testée avec une valeur écrite en dur, et accompagnée
d'un test de **mutation** : la même scène, rejouée avec le réglage cassé, doit
violer la règle. Les mutations du code faites le 02/11 rougissent toutes (voir
le message du commit).
