# packages/

Un package ROS 2 par fonction, à plat.

| Package | Arrivé | Rôle |
|---|---|---|
| `theatre_contrats` | L1a (02/11) | le contrat commun : noms de topics (relatifs), clés de payload, organes, codec StringTime, profils QoS — Python pur, voir son README |
| `robot_interfaces` | L1a (02/11) | les messages (`StringTime`…) — copie UNIQUE (les copies vision/télécommande sont supprimées) ; renommé `theatre_interfaces` en L1e |
| `didier_jeu` | A1 (02/11) | le sélecteur de jeu (arbre py_trees + score), **SIM-ONLY** : `jeu_node` refuse de démarrer hors domaine 43 ; monté/copié par la sim seulement — voir son README. ⚠️ Le rsync Ansible de `packages/` le pousserait aussi vers les Pi (inerte, mais à exclure : décision de déploiement non prise) |

Les autres packages sont encore dans `legacy/` (robot : `legacy/dadou_robot_ros/conf/ros2_dependencies/*` et `robot/` ; vision : `legacy/dadou_vision_ros/vision` ; télécommande : `legacy/dadou_control_ros/controller`). Ils arrivent ici au lot L1e, renommés.

**Tout conteneur qui embarque `dadou_utils_ros` doit avoir `theatre_contrats` dans son `src/`** (le shim `utils_static.py` l'importe) : les compose et Dockerfiles de `legacy/` montent/copient ces deux packages depuis ici (contextes de build nommés). Ansible les rsync vers `ros2_ws/src/` de chaque Pi (rôle `synchronise`, corrigé le 02/11). ⚠️ Verrous restants avant déploiement : poser la sentinelle `colcon build` sur chaque Pi (sinon l'ancien code tourne en silence) ; aucune image ARM n'a encore été compilée avec ces packages — robot d'abord.
