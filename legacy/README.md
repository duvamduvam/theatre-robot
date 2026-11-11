# legacy/

Les quatre anciens dépôts, importés par `git subtree add` le 2026-11-02 (historiques conservés). **Ne pas y faire d'architecture** : on en sort des morceaux vers les dossiers cibles, lot après lot.

État au lot L1e-4e (2026-11-11) :
- `dadou_robot_ros/`, `dadou_vision_ros/`, `dadou_utils_ros/` : **archives** — leur code, données, conf, doc et outillage ont rejoint `packages/`, `data/`, `machines/`, `docs/`, `atelier/`, `deploy/`. Il n'y reste que des bandeaux (README), les `CLAUDE.md` de sécurité/vision et `ARCHITECTURE.md` de la vision.
- `dadou_control_ros/` : la télécommande, seule à vivre encore ici (réécrite au lot L4). Ansible la copie depuis `legacy/` (`local_projects_dir` de `deploy/vars/main.yml`).

Les anciens dossiers `~/Nextcloud/dev/didier/python/dadou_*_ros` ne servent plus qu'à l'archive.
