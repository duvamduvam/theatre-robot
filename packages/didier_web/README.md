# didier_web

Package ROS 2 du robot Didier, autonome (aucun import `robot.*` ni `dadou_utils_ros`) :

| Exécutable | Nœud | Rôle |
|---|---|---|
| `web_bridge` | `web_bridge_node` | pont HTTP + WebSocket (console `/`, page scène `/scene`) — voir `docs/interfaces.md` §API web |
| — | `static/` | pages servies telles quelles, sans build : console `index.html` + `app.js`, scène `scene.html` + `scene.js` + `scene.css`, communs `commun.js` + `style.css` (ne pas y mettre de style propre à la scène) |
| `catalogue` | `catalogue_node` | **lot L1c** : publie le catalogue du robot et sa version |
| `data_edit` | `data_edit_node` | **lot L1d** : le SEUL écrivain des données du robot (désactivé par défaut) |
| `validation_sim` | `validation_sim_node` | **lot L1d-2**, SIM SEULEMENT : l'observateur de la porte sim, qui tamponne `json/validations-sim.json` |

## `catalogue_node` (L1c)

Deux topics StringTime **latchés** (`qos.latched()` des deux côtés), noms dans
`theatre_contrats.topics` :

- `catalogue` : JSON `{faces, audios, animations, relays, robot_lights, visuals}`,
  construit par `web_catalog.build_catalog(json_dir)` (la même fonction sert
  `GET /api/catalog`). Reconstruit toutes les `refresh_period_s` (2 s) et
  **republié seulement s'il a changé** (`web_catalog.next_publication`).
- `deploy_sha` : chaîne JSON, le sha git écrit par Ansible dans `conf/DEPLOY_SHA`
  (`-dirty` si l'arbre rsyncé n'était pas propre) ou `"dev"` si le fichier est
  absent (sim). Lu une fois au démarrage.

Paramètres : `json_dir` (`/home/ros2_ws/json`), `deploy_sha_file` (`""` = `dev`),
`refresh_period_s` (`2.0`). Lancé par `robot_app.launch.py` (robot) et
`sim.launch.py` (sim), sous le namespace `/<ROBOT_NAME>/`.

Le pont web lit `deploy_sha` (`TOPICS_LECTURE`) pour le badge version ; il ne lit
PAS `catalogue` (la page garde `/api/catalog`).

Tests (hôte, sans ROS) : `packages/didier_core/test/unit/test_web_catalog.py`,
`test_catalogue_node.py` ; télécommande : `test_buttons_vs_catalogue.py`.
Preuve sim : `machines/sim/validate-catalogue.sh`.

## `data_edit_node` (L1d)

Écoute `data_edit` (demande), publie `data_edit_result` (verdict) — StringTime,
`qos.volatile(10)` des deux côtés, **jamais latché**. Mince : toute la logique est dans
`data_edit.traiter(brut, data_dir, enabled, maintenant)` (stdlib + `theatre_contrats`),
testée sans ROS. Contrat des données : `theatre_contrats.donnees` (jamais recopié ici).
Format des demandes, codes, ordre d'écriture : `docs/interfaces.md` § « Data editing through
the robot ».

Paramètres : `data_dir` (`/home/ros2_ws/src/robot`, enfants `json/` et `medias/` — même chemin
en sim et sur le Pi), `enabled` (`false`). Lancé TOUJOURS par `robot_app.launch.py` (variable
`DATA_EDIT`) et `sim.launch.py` (argument `data_edit`, variable `DATA_EDIT` du compose sim) :
désactivé, il répond `edition_desactivee` à chaque demande. **Sur le vrai robot, l'activer est
une décision de David** (spec L1d, décision 10). Au démarrage, il vide ses temporaires
(`json/backup/.tmp/`, `medias/.tmp/`).

Ce qu'il écrit : la cible (séquence, entrée d'`expressions.json` / `robot_lights.json` /
`lights_base.json`, image), la sauvegarde `json/backup/<date>/…`, une ligne du journal
`json/backup/EDITIONS-EN-ATTENTE.jsonl` (avant l'écriture). Rien d'autre.

Tests (hôte) : `packages/didier_core/test/unit/test_data_edit.py` (octets et sha gravés, un cas
par code), `test_rechargement.py` ; contrat : `packages/theatre_contrats/test/test_donnees.py`.
Preuve sim : `machines/sim/validate-data-edit.sh` (13 épreuves, aussi jouée par la fumée).

## `validation_sim_node` (L1d-2, sim seulement)

L'observateur de la porte sim : il regarde ce qui se joue (`animation_state` latché, `face`,
`robot_lights`, `cmd_vel`), quel que soit le déclencheur, et pose le tampon `rejeu` du registre
`json/validations-sim.json` quand un élément a été joué jusqu'au bout sans incident ; il répond
aux demandes de validation des roues (`validation_sim_demande`). Verdicts sur `validation_sim`.
Critères et codes : `docs/interfaces.md` § « Sim gate ». Mince : la logique est dans
`validation_sim.Observateur` (pure, horloge injectée), qui **refuse de se construire hors domaine
43** — le registre ne s'écrit qu'en sim. Lancé par `sim.launch.py` seul, jamais sur le robot.

Paramètres : `data_dir` (`/home/ros2_ws/src/robot`), `journal` (`/home/ros2_ws/log/robot.log`,
le `LOGGING_FILE_NAME` de `didier_core`, égalité gravée). Écriture atomique (temporaire sous
`json/backup/.tmp/`), propriétaire de `json/` rendu, orphelines retirées à chaque écriture.
Ne lit pas `/rosout` (règle gravée : aucun abonnement à un nom absolu).

Tests (hôte) : `packages/didier_core/test/unit/test_validation_sim.py` (un tampon posé / refusé
par critère, bornes à leur valeur limite), `test_validations_sim.py` (le registre de `data/` est
complet). Par lot : `machines/sim/rejouer-modifiees.sh`.
