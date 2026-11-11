# dadou_utils_ros — la lib partagée du parc Didier

Communication (série, WebSocket, LoRa), fichiers JSON, écrans LCD, journalisation et
utilitaires importés par le robot, la vision et la télécommande (120 fichiers l'importent).
Python pur, importable sur le PC sans ROS. **Elle disparaît au lot L5** (59 % de code mort) :
d'ici là elle garde son nom et reste stable — ne pas y ajouter de code neuf, utiliser
`theatre_contrats` pour le contrat.

Package ament_python depuis le lot L1e-3a (07/11) : avant, c'était le dépôt `dadou_utils_ros`
entier, embarqué dans chaque projet par un lien symbolique (`legacy/<dépôt>/dadou_utils_ros`).
Ces liens sont supprimés ; `conf/`, `docs/`, `scripts/` sont restés dans `legacy/dadou_utils_ros/`
(ménage L1e-4e) ; `ansible/` est devenu `deploy/` et `jenkins/` a été supprimé au lot L1e-4a (08/11).

## Contrat

- **Nom** : `dadou_utils_ros` (module et package). Code dans `dadou_utils_ros/dadou_utils_ros/`.
- **Dépend de** `theatre_contrats` : `utils_static.py` en ré-exporte le contrat (shim). Sans ce
  package dans le même `src/`, tout import de la lib échoue.
- **Données attendues** : aucune dans le package (les chemins de données — `json/`, `medias/` —
  sont résolus par `robot_config.py`, côté cœur). Les polices LCD (`fonts/`) sont dans le module.
- **Variables d'environnement** : aucune.
- **Dépendances pip** non déclarées au package (`filetype`, `colorlog`, `psutil`,
  `requirements-test.txt`) : fournies par les images (voir les Dockerfiles de `legacy/`).

## Où elle entre

| Contexte | Comment |
|---|---|
| Hôte (tests) | `conftest.py` de chaque dépôt legacy et de `packages/didier_jeu` : `packages/dadou_utils_ros` dans `sys.path` |
| Sim, x86, ARM (images) | contexte nommé `dadou_utils_ros` du compose + `COPY --from=dadou_utils_ros . /home/ros2_ws/src/dadou_utils_ros` |
| Conteneurs (volumes) | `packages/dadou_utils_ros` → `/home/ros2_ws/src/dadou_utils_ros` (sur le Pi : `../../../../dadou_utils_ros`) |
| Pi (Ansible) | `packages_default` + liste de l'hôte robot ; `chemins_retires_lib` efface les anciennes copies embarquées |

## Tester

```bash
cd packages/dadou_utils_ros && ../../.venv/bin/python -m pytest -q -o addopts=
```
