# packages/

Un package ROS 2 par fonction, à plat.

| Package | Arrivé | Rôle |
|---|---|---|
| `theatre_contrats` | L1a (02/11) | le contrat commun : noms de topics (relatifs), clés de payload, organes, codec StringTime, profils QoS — Python pur, voir son README |
| `robot_interfaces` | L1a (02/11) | les messages (`StringTime`…) — copie UNIQUE (les copies vision/télécommande sont supprimées) ; renommé `theatre_interfaces` en L1e |
| `robot_bringup`, `robot_description`, `robot_drive`, `robot_rehearsal`, `robot_sim`, `robot_web` | L1e-1 (06/11) | les 6 packages ROS autonomes du robot (launch du Pi, URDF, chaîne cmd_vel, sim Gazebo, salle de répétition, console web), déménagés de `legacy/dadou_robot_ros/conf/` **sans renommage** ; deviennent `didier_*` en L1e-2. Compose/Dockerfiles les montent par `packages/<nom>` ; Ansible les pousse par la liste `packages` de l'hôte robot (`hosts`) |
| `didier_jeu` | A1 (02/11) | le sélecteur de jeu (arbre py_trees + score), **SIM-ONLY** : `jeu_node` refuse de démarrer hors domaine 43 ; monté/copié par la sim seulement — voir son README. Ansible ne le pousse sur aucun Pi (L1e-1 : listes `packages` explicites par machine, `hosts`) |

**Catalogue + version (lot L1c, 04/11)** : `theatre_contrats.topics.CATALOGUE` (`catalogue`) et `DEPLOY_SHA` (`deploy_sha`), StringTime latchés publiés par `catalogue_node` (package `robot_web`) ; inventaire gravé dans `test_inventaire.py` / `test_topics_relatifs.py`. Détail : `legacy/dadou_robot_ros/docs/interfaces.md` et `packages/robot_web/README.md`.

**Namespace (lot L1b, 04/11)** : tout nœud de ces packages tourne sous `/<ROBOT_NAME>/` (défaut `/didier/`), posé par les launch (`GroupAction` + `PushRosNamespace` absolu) ou, pour un `ros2 run`, par `--ros-args -r __ns:=/didier`. Conséquence pour le code : **noms de topics relatifs, toujours** (`theatre_contrats.topics` le grave) ; seuls `/clock`, `/tf`, `/tf_static`, `/rosout`, `/parameter_events` restent globaux. Un nouveau launch doit suivre le même gabarit — `legacy/dadou_robot_ros/robot/tests/unit/test_namespace_contract.py` le vérifie (inventaire gravé des launch : en ajouter un exige de l'y inscrire).

Les autres packages sont encore dans `legacy/` (robot : `legacy/dadou_robot_ros/robot/` ; vision : `legacy/dadou_vision_ros/vision` ; télécommande : `legacy/dadou_control_ros/controller`). Ils arrivent ici au lot L1e, renommés.

**Tout conteneur qui embarque `dadou_utils_ros` doit avoir `theatre_contrats` dans son `src/`** (le shim `utils_static.py` l'importe) : les compose et Dockerfiles de `legacy/` montent/copient ces deux packages depuis ici (contextes de build nommés). Ansible les rsync vers `ros2_ws/src/` de chaque Pi (rôle `synchronise` : liste `packages` de l'hôte, à défaut `packages_default` = ces deux-là, depuis L1e-1). ⚠️ Verrous restants avant déploiement : poser la sentinelle `colcon build` sur chaque Pi (sinon l'ancien code tourne en silence) ; aucune image ARM n'a encore été compilée avec ces packages — robot d'abord.
