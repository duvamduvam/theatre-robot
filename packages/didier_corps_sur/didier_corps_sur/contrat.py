"""Contrat ROS du nœud corps_sur (spec A0 §3.2) — PUR : ni rclpy ni numpy.

Noms de topics (RELATIFS : le nœud vit sous /<ROBOT_NAME>/), types et QoS, écrits UNE fois ici
et lus par `corps_sur_node.py`, qui n'en code aucun en dur. Gravés par test/test_contrat_node.py :
changer un nom, un type ou une QoS exige de toucher ce test.

Les noms neufs du lot A0 (scan, sorties `_sur`, battement, état, réarmement) viennent de
theatre_contrats.topics ; les trois DEMANDES gardent leur nom historique (publieurs inchangés :
wheels_bridge, person_follower, route_driver/fault_relay, web_bridge) et sont égales aux
constantes de ces publieurs (gravé aussi).
"""
from dataclasses import dataclass

from theatre_contrats import topics

# Nom du nœud (sous le namespace du robot : /didier/corps_sur). machines/robot/machine.yml
# l'exige parmi les noeuds_attendus.
NOM_NOEUD = "corps_sur"

# Défaut du lancement : la conf de la MACHINE (machines/robot/corps_sur.yaml, copiée dans
# src/robot/conf/ par Ansible). La sim passe la sienne par machines/sim/robot/entree.sh.
CONFIG_DEFAUT = "/home/ros2_ws/src/robot/conf/corps_sur.yaml"


@dataclass(frozen=True)
class Qos:
    """Une QoS décrite sans rclpy (le nœud la traduit). `latche` = TRANSIENT_LOCAL."""
    fiable: bool
    profondeur: int
    latche: bool = False


# Les trois DEMANDES (entrée) et leurs SORTIES filtrées, canal par canal (un pour un, §3.1).
ENTREES = {"anim": "cmd_vel_anim", "follow": "cmd_vel_follow", "web": "cmd_vel_web"}
SORTIES = {"anim": topics.CMD_VEL_ANIM_SUR, "follow": topics.CMD_VEL_FOLLOW_SUR,
           "web": topics.CMD_VEL_WEB_SUR}
SCAN = topics.SCAN
E_STOP = "e_stop"            # le même que le verrou de twist_mux (source future : W1)
BATTEMENT = topics.SUPERVISEUR_BATTEMENT
REARMER = topics.CORPS_SUR_REARMER
ETAT = topics.CORPS_SUR_ETAT
DIAGNOSTICS = "diagnostics"  # relatif : /didier/diagnostics, comme celui de twist_mux

TWIST = "geometry_msgs/msg/Twist"
TYPES = {
    SCAN: "sensor_msgs/msg/LaserScan",
    E_STOP: "std_msgs/msg/Bool",
    BATTEMENT: "std_msgs/msg/Empty",
    REARMER: "std_msgs/msg/Empty",
    ETAT: "theatre_interfaces/msg/StringTime",
    DIAGNOSTICS: "diagnostic_msgs/msg/DiagnosticArray",
    **{nom: TWIST for nom in ENTREES.values()},
    **{nom: TWIST for nom in SORTIES.values()},
}

# QoS du §3.2. Le scan en best effort accepte le pilote (fiable) comme le pont Gazebo ; seul le
# plus récent compte. Les demandes : fiables, profondeur 1 (la dernière consigne seule compte).
QOS = {
    SCAN: Qos(fiable=False, profondeur=1),
    E_STOP: Qos(fiable=True, profondeur=10),
    BATTEMENT: Qos(fiable=False, profondeur=1),
    REARMER: Qos(fiable=True, profondeur=10),
    ETAT: Qos(fiable=True, profondeur=1, latche=True),   # = theatre_contrats.qos.latched()
    DIAGNOSTICS: Qos(fiable=True, profondeur=10),
    **{nom: Qos(fiable=True, profondeur=1) for nom in ENTREES.values()},
    **{nom: Qos(fiable=True, profondeur=10) for nom in SORTIES.values()},
}
ABONNEMENTS = (SCAN, E_STOP, BATTEMENT, REARMER, *ENTREES.values())
PUBLICATIONS = (ETAT, DIAGNOSTICS, *SORTIES.values())

# Minuterie de surveillance (§3.3) : péremptions, état publié ; diagnostics une fois sur 20.
PERIODE_TIC_S = 0.05
TICS_PAR_DIAGNOSTIC = 20
