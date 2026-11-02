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
| entrées | | `vision/person_box`, `rehearsal/poi_event`, `rehearsal/chat_move` (la bouche), `chat_situation`, `mission_state`, `route_state`, `route_goto_result`, `animation_state`, `rehearsal/objects` (avec `x`, `y` depuis A1), `/ground_truth/odom` |

Les noms `jeu/*` sont définis dans `theatre_contrats.topics`. Ceux du régisseur
viennent de `robot_rehearsal.contracts`, qui est importé et non recopié.

## Ce qui décide (dans l'ordre de l'arbre)

1. **Arrêt vocal** : un `stop` venu de la bouche ou de la console est **relayé
   dès sa réception, sans passer par le score**. Il pose un verrou sur tout
   déplacement jusqu'au `go`. Il n'y a jamais de `go` automatique après un stop de David.
2. **Superviseur absent** (mode `exigeant` seulement ; le défaut en A1 est `suppose`) :
   aucun déplacement.
3. **Ordre macro** : `va_la` vise un objet de `rehearsal/objects` (→ `aller_voir`)
   ou une piste (→ `tourner` vers elle, puis `avancer` 1 m). `joue_avec` vise la
   piste regardée. `ignore` coupe les offres de la cible pendant 30 s et annule
   une lubie en attente ou une reprise. `reviens` envoie `go`. `plus_lent`
   multiplie les réfractaires par 2 pendant 60 s (interprétation A1 : il n'y a
   pas de topic de vitesse côté sélecteur).
4. **Action engagée** : elle se finit. Seule une offre de valeur ≥ 0,9 (la
   bouche) peut l'interrompre.
5. **Choisir** : le score de chaque candidat (immobilité comprise), puis
   l'hystérésis (+15 % pendant 300 ms), et jamais deux changements à moins de 2 s.

**Lubie** : un `poi_event enter` fait naître une offre `objet`. Didier réclame
l'arrêt (par l'intention) **et** l'amorce (`look` vers l'objet, angle calculé
depuis l'odométrie vérité terrain, donc SIM-ONLY). Il ne demande `stop` que si
la console n'a dit ni `ignore` ni `va_la` dans les 3 s. Il propose ensuite
« repartir ? » et envoie `go` de lui-même 90 s plus tard. Au plus un arrêt de
sa part toutes les 120 s.

**Répertoire** : les séquences qui ont une clé `types`, **sauf** celles de `bugs/`
et **sauf toute séquence à piste `wheels`** (A1 n'a pas de corps sûr). Les types
`bonjour` donnent un « accueil » (réponse à une personne) ; `random` et `little
move` donnent une expression spontanée (servie par l'ennui). Les déplacements
sont dans `config/deplacements.yaml` ; `reculer` en est absent, car le régisseur
refuse tout `avancer` négatif.

Tous les chiffres sont dans `config/reglages.yaml` (« réglage de départ, se
règle au journal »), et **gravés** dans `test/test_reglages.py`.

## Lancer (conteneur sim)

```bash
ros2 launch robot_rehearsal rehearsal.launch.py route:=chantiers scenario:=jeu-a1 jeu:=true
ros2 run didier_jeu jeu_node
```

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
