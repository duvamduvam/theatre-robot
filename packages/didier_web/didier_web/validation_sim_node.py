"""Nœud `validation_sim` (lot L1d-2) : l'observateur de la porte sim, SIM SEULEMENT.

Lancé par sim.launch.py seul (jamais par robot_app.launch.py) ; hors domaine 43 il refuse de
démarrer (même garde que rehearsal_enabled) : le registre des validations ne s'écrit qu'en sim.
Mince : toute la logique est dans validation_sim.Observateur, pure et testée sans ROS.

Écoute ce qui se joue, quel que soit le déclencheur : animation_state (latché), face,
robot_lights, cmd_vel et validation_sim_demande (bouton « Valider les roues pour le robot »). Publie chaque verdict sur
validation_sim (StringTime, qos.volatile(10)). Journal ROS : INFO si ok, WARNING sinon.
"""
import json
import os
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist

from theatre_interfaces.msg import StringTime
from theatre_contrats import qos, topics
from didier_web.validation_sim import JOURNAL_ROBOT, Journal, Observateur, domaine_autorise

PERIODE_TIC_S = 0.1


def _maintenant_ms():
    return int(time.monotonic() * 1000)


class ValidationSimNode(Node):
    def __init__(self):
        super().__init__("validation_sim_node")
        self.declare_parameter("data_dir", "/home/ros2_ws/src/robot")
        self.declare_parameter("journal", JOURNAL_ROBOT)
        data_dir = self.get_parameter("data_dir").value
        self.observateur = Observateur(data_dir, Journal(self.get_parameter("journal").value),
                                       self._noeuds, os.environ)

        self.pub = self.create_publisher(StringTime, topics.VALIDATION_SIM, qos.volatile(10))
        # animation_state est LATCHÉ côté animations_node : TRANSIENT_LOCAL ici aussi (piège du 12/07).
        latche = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                            reliability=ReliabilityPolicy.RELIABLE)
        self.create_subscription(StringTime, topics.ANIMATION_STATE, self._on_etat, latche)
        self.create_subscription(StringTime, topics.FACE, lambda m: self._on_commande(topics.FACE, m), 10)
        self.create_subscription(StringTime, topics.ROBOT_LIGHTS,
                                 lambda m: self._on_commande(topics.ROBOT_LIGHTS, m), 10)
        self.create_subscription(Twist, "cmd_vel", self._on_cmd_vel, 10)
        self.create_subscription(StringTime, topics.VALIDATION_SIM_DEMANDE, self._on_demande, qos.volatile(10))
        self.create_timer(PERIODE_TIC_S, lambda: self._sur(self.observateur.tic, _maintenant_ms()))
        self.get_logger().info("validation_sim prêt : registre {}/json/validations-sim.json".format(data_dir))

    def _noeuds(self):
        ns = self.get_namespace()
        return [nom for nom, espace in self.get_node_names_and_namespaces() if espace == ns]

    def _on_etat(self, msg):
        try:
            nom = json.loads(msg.msg)
        except ValueError:
            return
        if isinstance(nom, str):
            self._sur(self.observateur.etat_animation, _maintenant_ms(), nom)

    def _on_commande(self, topic, msg):
        try:
            valeur = json.loads(msg.msg)
        except ValueError:
            valeur = msg.msg
        self._sur(self.observateur.commande, _maintenant_ms(), topic, valeur)

    def _on_cmd_vel(self, msg):
        nul = abs(msg.linear.x) < 1e-6 and abs(msg.angular.z) < 1e-6
        self.observateur.cmd_vel(_maintenant_ms(), nul)

    def _on_demande(self, msg):
        self._sur(lambda brut: [self.observateur.valider_roues(brut)], msg.msg)

    def _sur(self, fonction, *args):
        """Une donnée illisible (JSON cassé à la main) ne fait pas tomber l'observateur : ERROR
        au journal ROS, rien de tamponné."""
        try:
            self._publier(fonction(*args))
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as e:
            self.get_logger().error("validation_sim : {} : {}".format(type(e).__name__, e))

    def _publier(self, verdicts):
        for v in verdicts:
            self.pub.publish(StringTime(msg=json.dumps(v, ensure_ascii=False), time=0, anim=False))
            ligne = "validation_sim {} {} -> {}".format(v["kind"], v["name"], v["code"])
            if v["ok"]:
                self.get_logger().info(ligne)
            else:
                self.get_logger().warning(ligne + " " + "; ".join(v["detail"])[:300])


def main(args=None):
    rclpy.init(args=args)
    if not domaine_autorise(os.environ):
        # Refus LOGGUÉ, jamais silencieux ; le lancement sim continue sans l'observateur.
        print("validation_sim refuse de démarrer : ROS_DOMAIN_ID={!r}, réservé à la simulation (43)".format(
            os.environ.get("ROS_DOMAIN_ID")), flush=True)
        rclpy.shutdown()
        return
    node = ValidationSimNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
