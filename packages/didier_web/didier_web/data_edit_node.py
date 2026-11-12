"""Nœud `data_edit` (lot L1d) : le SEUL écrivain des données du robot par ROS.

Écoute `data_edit` (demande), publie `data_edit_result` (verdict), StringTime,
qos.volatile(10) des deux côtés, jamais latché (spec L1d, décision 1). Mince : toute la
logique est dans data_edit.traiter, pure et testée sans ROS.

Nœud à part (décision 5) : pas dans catalogue_node (lecteur toujours actif, qui ne doit pas
tomber avec l'écrivain), pas dans le pont web (optionnel). Lancé TOUJOURS par
robot_app.launch.py et sim.launch.py ; désactivé (`enabled` faux, le défaut), il répond
`edition_desactivee` à chaque demande — un refus visible vaut mieux qu'un silence.

Journal ROS : INFO si ok, WARNING sinon — id, nom, code, JAMAIS le contenu.
"""
import datetime
import json

import rclpy
from rclpy.node import Node

from theatre_interfaces.msg import StringTime
from theatre_contrats import qos, topics
from didier_web.data_edit import traiter, vider_tmp


class DataEditNode(Node):
    def __init__(self):
        super().__init__("data_edit_node")
        # Racine des données : enfants json/ et medias/, même chemin en sim et sur le Pi.
        self.declare_parameter("data_dir", "/home/ros2_ws/src/robot")
        self.declare_parameter("enabled", False)
        self.data_dir = self.get_parameter("data_dir").value
        self.enabled = bool(self.get_parameter("enabled").value)

        nettoyes = vider_tmp(self.data_dir)
        if nettoyes:
            self.get_logger().warning("{} temporaire(s) d'une écriture interrompue effacé(s)".format(nettoyes))

        self.result_pub = self.create_publisher(StringTime, topics.DATA_EDIT_RESULT, qos.volatile(10))
        self.create_subscription(StringTime, topics.DATA_EDIT, self._on_demande, qos.volatile(10))
        self.get_logger().info("data_edit prêt : édition {} ({})".format(
            "ACTIVÉE" if self.enabled else "désactivée", self.data_dir))

    def _on_demande(self, ros_msg):
        resultat = traiter(ros_msg.msg, self.data_dir, self.enabled, datetime.datetime.now())
        self.result_pub.publish(StringTime(msg=json.dumps(resultat, ensure_ascii=False), time=0, anim=False))
        ligne = "data_edit id={} {} {} -> {}".format(
            resultat["id"], resultat["kind"], resultat["name"], resultat["code"])
        if resultat["code"] == "ok":
            self.get_logger().info(ligne)
        else:
            self.get_logger().warning(ligne)


def main(args=None):
    rclpy.init(args=args)
    node = DataEditNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
