# legacy/

Les quatre anciens dépôts, importés par `git subtree add` le 2026-11-02 (historiques conservés), côte à côte pour que leurs liens relatifs (`../dadou_utils_ros`) continuent de fonctionner. **Ne pas y faire d'architecture** : on y corrige, on en sort des morceaux vers les dossiers cibles, lot après lot.

**Les déploiements Ansible rsyncent d'ici** depuis le 02/11 (`deploy/vars/main.yml : local_projects_dir`, à la racine du dépôt depuis le lot L1e-4a du 08/11). Les anciens dossiers `~/Nextcloud/dev/didier/python/dadou_*_ros` ne servent plus qu'à l'archive.
