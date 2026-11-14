# Conteneur `monde` de la sim multi-conteneurs (spec L2, décisions 1 et 18) — x86 SEUL, PC de dev
# et CI. Le monde = tout ce qui n'est pas une machine de Didier : Gazebo Harmonic, le pont gz, le
# MATÉRIEL SIMULÉ (servos, LED), la répétition (didier_rehearsal), le sélecteur de jeu (didier_jeu,
# SIM-ONLY) et les épreuves validate-*.sh. Le robot, lui, tourne dans le conteneur `robot`, construit
# avec le Dockerfile du Pi (machines/robot/docker/Dockerfile).
#
# Ex Dockerfile-sim (le fourre-tout supprimé en L2b), plus xvfb (écran virtuel de la CI, L2d), moins
# didier_bringup, didier_drive et didier_web : ils sont dans `robot`. didier_core reste, comme
# BIBLIOTHÈQUE de didier_rehearsal et didier_jeu (exec_depend de leurs package.xml) — aucun launch
# de ce conteneur ne démarre un de ses exécutables (gravé par test_compose_sim.py).
#
# Contexte principal = ce dossier (machines/sim/monde/, seul entree.sh en est copié) ; le reste
# arrive par contextes NOMMÉS, chemins donnés par machines/sim/docker-compose.yml.
FROM ros:jazzy-ros-base
LABEL authors="dadouuu"

# ros-jazzy-ros-gz installe Gazebo Harmonic (paire officielle de Jazzy)
# via les paquets vendored de packages.ros.org — pas de dépôt en plus.
RUN apt-get update && apt-get install -y \
    ros-jazzy-ros-gz \
    ros-jazzy-xacro \
    ros-jazzy-robot-state-publisher \
    ros-jazzy-joint-state-publisher-gui \
    ros-jazzy-rviz2 \
    ros-jazzy-teleop-twist-keyboard \
    ros-jazzy-twist-mux \
    python3-pip \
    python3-aiohttp \
    python3-pil \
    # imageio : lu par didier_core/visual/visual.py (chaîne d'imports de la bibliothèque du
    # cœur importée par la répétition). Paquet apt de Noble (universe).
    python3-imageio \
    # py_trees : behaviour trees du sélecteur de jeu (packages/didier_jeu, lot
    # A1). Paquet ROS officiel (2.6.0 au 02/11) ; la même version est épinglée
    # dans requirements-test.txt pour les tests hôte.
    ros-jazzy-py-trees \
    # Écran virtuel (décision 9, mode ECRAN=xvfb de la CI) : le rendu des caméras gz exige un
    # serveur X même en headless. Sur le PC, c'est la session de David (ECRAN=hote).
    xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/ros2_ws/src
WORKDIR /home/ros2_ws

# Les sources sont aussi montées en volume par le compose (itération sans
# rebuild) ; la copie permet de lancer l'image seule.
COPY --from=didier_description . /home/ros2_ws/src/didier_description
COPY --from=didier_sim . /home/ros2_ws/src/didier_sim
COPY --from=theatre_interfaces . /home/ros2_ws/src/theatre_interfaces
COPY --from=theatre_contrats . /home/ros2_ws/src/theatre_contrats
COPY --from=dadou_utils_ros . /home/ros2_ws/src/dadou_utils_ros
COPY --from=didier_jeu . /home/ros2_ws/src/didier_jeu
COPY --from=didier_rehearsal . /home/ros2_ws/src/didier_rehearsal
COPY --from=didier_core . /home/ros2_ws/src/didier_core
COPY entree.sh /home/ros2_ws/entree.sh

# json/ : robot_lights.json, lights_base.json, colors.json lus par leds_sim_node (mêmes fichiers
# que le vrai robot) ; json/ et medias/ sont aussi montés par le compose (données du dépôt, data/),
# aux deux chemins que lisent les nœuds de sim et les épreuves : /home/ros2_ws/json et
# /home/ros2_ws/src/robot/{json,medias}. Aucun audio : medias/ n'est pas copié (dossier privé
# monté en lecture seule par le compose).
COPY --from=data json/ /home/ros2_ws/json/
COPY --from=data json/ /home/ros2_ws/src/robot/json/
# log/ : logging_conf.py (bibliothèque du cœur) écrit sur ce chemin exact ; le dossier doit exister
# avant le premier dictConfig. Monté par le compose (machines/sim/workspace/log), partagé avec `robot`.
RUN mkdir -p /home/ros2_ws/log

# filetype/colorlog/psutil : dépendances pip de la chaîne d'imports de la bibliothèque du cœur
# (dadou_utils_ros.misc, logging_conf) — pas tout requirements.txt du robot (adafruit-*, PyAudio).
# --break-system-packages : Ubuntu Noble (Jazzy) refuse pip hors venv sans ce flag.
RUN pip3 install --no-cache-dir --break-system-packages filetype colorlog psutil

ENTRYPOINT ["/bin/bash", "/home/ros2_ws/entree.sh"]
