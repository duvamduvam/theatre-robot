# didier_web

Package ROS 2 du robot Didier, autonome (aucun import `robot.*` ni `dadou_utils_ros`) :

| Exécutable | Nœud | Rôle |
|---|---|---|
| `web_bridge` | `web_bridge_node` | pont HTTP + WebSocket (console `/`, page scène `/scene`) — voir `docs/interfaces.md` §API web |
| `catalogue` | `catalogue_node` | **lot L1c** : publie le catalogue du robot et sa version |

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

Tests (hôte, sans ROS) : `robot/tests/unit/test_web_catalog.py`,
`test_catalogue_node.py` ; télécommande : `test_buttons_vs_catalogue.py`.
Preuve sim : `machines/sim/validate-catalogue.sh`.
