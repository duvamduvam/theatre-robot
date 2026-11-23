# machines/robot

Le Pi 4 du robot (hôte `r` de `deploy/hosts`). Ex `legacy/dadou_robot_ros/conf/` sans la partie
sim (lot L1e-4c, 11/11) ; copié dans `~/ros2_ws/src/robot/conf/` du Pi (chemin inchangé).

- `machine.yml` : ce qu'Ansible déploie (10 packages, données `data/`, launch, 16 nœuds attendus,
  alias mDNS) — convention dans `../README.md`.
- `docker/Dockerfile` : l'image du robot, la même sur le Pi et le PC (L2a ; contextes nommés,
  audios privés exclus ; depuis A0-6 le pilote du lidar `sllidar_ros2`, compilé au commit épinglé
  dans `/opt/lidar_ws`) ; `docker/arm/` : le compose du Pi, `dadouuu/dadou-robot-arm` construite
  SUR le Pi, chemins relatifs à la disposition du Pi. Voir `../README.md` § Les images Docker.
- `scripts/` : entrée du conteneur (`launch-ros-in-docker.sh`), `collect-incident.sh`,
  `log-charge.sh`, **`validate-cmdvel-protocol.sh`** (protocole caméra des roues, exécuté dans le
  conteneur du VRAI robot — il reste ici, pas dans `machines/sim/`), outils d'atelier.
- `udev/99-didier-lidar.rules` (A0-6, 23/11) : lien stable `/dev/didier-lidar` vers l'adaptateur
  CP2102N de CE lidar (numéro de série gravé ; un autre lidar = relever le sien et le changer
  ici). Posé par Ansible (`fichiers_etc`), udev rechargé quand la règle change.
- `scripts/rearmer-corps-sur.sh`, `scripts/relancer-lidar.sh` (A0-6) : à lancer sur le Pi (hôte),
  ils parlent au conteneur ; réarmer le corps sûr, relancer le pilote du lidar (respawn 5 s).
- `systemd/avahi-alias-didier.service`, `rpi/`, `logging/`, listes de paquets.

La sim Gazebo et les scripts de vérification de la sim sont dans `../sim/`.
