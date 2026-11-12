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

**Contrat.** Tout ce qui entre ici — par git comme par le robot — est jugé par
`theatre_contrats.donnees` (lot L1d) : format des séquences, références (expressions, lumières,
audios), **bornes des pistes roues** (consigne ≤ 0.89, tenue ≤ 60 s, durée ≤ 300 s, dernière
image `[0, 0]`), expressions (images présentes, 24x16 / 8x8), lumières et briques, images PNG
(RVB 8 bits ; 21 images héritées en exception gravée, `test_visuels_png.py`). Les tests de
`didier_core` appellent ce module sur tout `data/`.

**Vérité unique, éditée à travers le robot** (lot L1d, en cours) : `data_edit_node` écrit une
séquence, une entrée d'expression, de lumière ou de brique, ou une image, après contrat et
sauvegarde (`json/backup/`, non versionné). En sim, la retouche tombe directement ici (le
conteneur monte `data/json` et `data/medias`) : `git diff` la montre. Désactivé par défaut
(`DATA_EDIT`) ; sur le vrai robot, l'activer est une décision de David. Les copies
de JSON de la télécommande (`legacy/dadou_control_ros/json/`) sont périmées : 61 partent à L1d, les
10 qu'elle lit encore partent avec elle (L4) — conception du 12/11, spec L1 § L1d.
