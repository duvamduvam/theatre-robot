# data/

Le **contenu du robot**, une seule famille (les JSON référencent les médias ; le catalogue les
publie ensemble) — arrivé ici de `legacy/dadou_robot_ros/` au lot L1e-4b (08/11) :

| Dossier | Contenu |
|---|---|
| `json/` | séquences (`sequences/**`), expressions du visage, lumières, couleurs, relais, mappings |
| `medias/` | `audios/` (sons des séquences et des boutons), `visuals/{mouth,eye}/` (PNG du visage) |
| `db/` | bases SQLite audio/séquences (`audios.db`, `sequences.db`) |

**Qui le lit.** Le cœur `packages/didier_core` (`robot_config.py`, racine `DIDIER_DATA_DIR` :
`json/`, `medias/`, `db/` en enfants directs) ; le catalogue du robot (`didier_web`, depuis
`json/`) ; la sim (`docker-compose-sim.yml` monte `json/` et `medias/`, `Dockerfile-sim` copie
`json/` par le contexte nommé `data`) ; le banc x86 du robot (même motif) ; les tests hôte (cœur,
jeu, télécommande : `test_buttons_vs_catalogue.py` compare ses boutons au catalogue construit
depuis `json/`).

**Où il arrive sur le Pi.** Le rôle Ansible `synchronise` copie `data/json`, `data/medias`,
`data/db` dans `~/ros2_ws/src/robot/{json,medias,db}` (machine robot seule, variable `donnees_dir`
de `machines/robot/machine.yml` depuis L1e-4c) — chemin Pi et conteneur **inchangés** (`/home/ros2_ws/src/robot/`,
`DIDIER_DATA_DIR`) ; l'image ARM du robot les copie depuis ce même dossier (contexte nommé
`data`). Le reste de `data/` (ce README) ne part pas.

**Vérité unique, éditée à travers le robot** : c'est le lot L1d, à venir — on éditera une
séquence par le robot (qui publie le catalogue), pas en recopiant des JSON ailleurs. Les copies
de JSON de la télécommande (`legacy/dadou_control_ros/json/`) sont périmées et partent avec elle (L4).
