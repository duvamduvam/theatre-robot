# packages/

Un package ROS 2 par fonction, à plat.

| Package | Arrivé | Rôle |
|---|---|---|
| `theatre_contrats` | L1a (02/11) | le contrat commun : noms de topics (relatifs), clés de payload, organes, codec StringTime, profils QoS — Python pur, voir son README |
| `robot_interfaces` | L1a (02/11) | les messages (`StringTime`…) — copie UNIQUE (les copies vision/télécommande sont supprimées) ; renommé `theatre_interfaces` en L1e |

Les autres packages sont encore dans `legacy/` (robot : `legacy/dadou_robot_ros/conf/ros2_dependencies/*` et `robot/` ; vision : `legacy/dadou_vision_ros/vision` ; télécommande : `legacy/dadou_control_ros/controller`). Ils arrivent ici au lot L1e, renommés.

**Tout conteneur qui embarque `dadou_utils_ros` doit avoir `theatre_contrats` dans son `src/`** (le shim `utils_static.py` l'importe) : les compose et Dockerfiles de `legacy/` montent/copient ces deux packages depuis ici (contextes de build nommés). ⚠️ Le déploiement Ansible ne les synchronise PAS encore : verrou avant tout déploiement sur les Pi.
