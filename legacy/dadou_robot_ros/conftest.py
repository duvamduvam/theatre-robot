import os
import sys

# La racine du dépôt donne accès au package robot/ et, via le symlink
# dadou_utils_ros -> ../dadou_utils_ros, à la lib partagée.
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# robot_drive n'est pas un package installé (pas de colcon build sur l'hôte
# de dev) : on l'ajoute au path pour que les tests fassent
# `from robot_drive... import ...` comme si le package était sourcé.
sys.path.insert(0, os.path.join(ROOT, "conf", "ros2_dependencies", "robot_drive"))

# Même logique pour robot_sim_lib (logique pure du node leds_sim_node,
# paquet robot_sim) : `from robot_sim_lib... import ...` sans colcon build.
sys.path.insert(0, os.path.join(ROOT, "conf", "ros2_dependencies", "robot_sim"))

# Même logique pour robot_web (protocole/catalogue purs du pont web W0,
# web_bridge_node.py lui-même n'est PAS importé par les tests -- il a besoin
# de rclpy/aiohttp, absents de l'environnement de dev hôte).
sys.path.insert(0, os.path.join(ROOT, "conf", "ros2_dependencies", "robot_web"))

# Idem pour robot_rehearsal (salle de répétition simulée, SIM-ONLY) : logique
# pure du cheminement (route.py) et contrats ; route_driver_node.py n'est
# jamais importé par les tests (rclpy/nav_msgs absents de l'hôte).
sys.path.insert(0, os.path.join(ROOT, "conf", "ros2_dependencies", "robot_rehearsal"))

# Le firmware du Pico (odom_protocol.py) : logique PURE du décodage quadrature
# et du protocole de trame, partagée entre le Pico (MicroPython), le futur
# noeud ROS et les tests. main.py, lui, n'est JAMAIS importé sur l'hôte -- il
# a besoin de machine/rp2, qui n'existent que sur le microcontrôleur.
sys.path.insert(0, os.path.join(ROOT, "firmware", "pico_odometry"))

# Idem pour le firmware de la telecommande USB (remote_protocol.py) : logique
# PURE de la trame montante, de la zone morte et de la regle « menu inerte tant
# que l'homme-mort est tenu », partagee entre le RP2040 (CircuitPython), le
# decodeur hote et les tests. code.py / boot.py ne sont JAMAIS importes sur
# l'hote -- ils ont besoin de board/digitalio/usb_cdc.
sys.path.insert(0, os.path.join(ROOT, "firmware", "remote_usb"))
