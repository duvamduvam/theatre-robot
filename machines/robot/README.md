# machines/robot

Le Pi 4 du robot (hôte `r` de `deploy/hosts`). Ex `legacy/dadou_robot_ros/conf/` sans la partie
sim (lot L1e-4c, 11/11) ; copié dans `~/ros2_ws/src/robot/conf/` du Pi (chemin inchangé).

- `machine.yml` : ce qu'Ansible déploie (10 packages, données `data/`, launch, 16 nœuds attendus,
  alias mDNS) — convention dans `../README.md`.
- `docker/arm/` : compose et Dockerfile de l'image `dadouuu/dadou-robot-arm` (construite SUR le Pi ;
  chemins relatifs à la disposition du Pi).
- `scripts/` : entrée du conteneur (`launch-ros-in-docker.sh`), `collect-incident.sh`,
  `log-charge.sh`, **`validate-cmdvel-protocol.sh`** (protocole caméra des roues, exécuté dans le
  conteneur du VRAI robot — il reste ici, pas dans `machines/sim/`), outils d'atelier.
- `systemd/avahi-alias-didier.service`, `rpi/`, `logging/`, listes de paquets.

La sim Gazebo et les scripts de vérification de la sim sont dans `../sim/`.
