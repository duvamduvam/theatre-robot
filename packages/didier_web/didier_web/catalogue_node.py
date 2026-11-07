"""Nœud `catalogue` (L1c) : le robot PUBLIE ce qu'il sait jouer, et sa version.

Deux topics StringTime LATCHÉS (theatre_contrats.topics) :
 - `catalogue`  : JSON des 6 familles de web_catalog.build_catalog() ;
 - `deploy_sha` : sha git déployé (fichier écrit par Ansible) ou "dev".

Nœud à part, PAS dans web_bridge_node : le catalogue sert aussi la télécommande,
et le pont web est optionnel (sim). Le nœud reste mince -- toute la logique
(construction, lecture du sha, décision de republier) est dans web_catalog.py,
pur et testé sans ROS.

Le catalogue est reconstruit à chaque période mais REPUBLIÉ seulement s'il a
changé : écrire une séquence dans json/ suffit pour que les abonnés la voient
(c'est ce qui rendra l'édition à travers le robot, L1d, triviale). Le sha, lui,
ne change jamais en cours de vie : lu une fois au démarrage.
"""
import json
import pathlib

import rclpy
from rclpy.node import Node

from theatre_interfaces.msg import StringTime
from theatre_contrats import qos, stringtime, topics
from didier_web.web_catalog import build_catalog, next_publication, read_deploy_sha


class CatalogueNode(Node):
    def __init__(self):
        super().__init__("catalogue_node")
        self.declare_parameter("json_dir", "/home/ros2_ws/json")
        # "" = pas de fichier = "dev" (sim). Sur le robot : conf/DEPLOY_SHA, écrit par Ansible.
        self.declare_parameter("deploy_sha_file", "")
        self.declare_parameter("refresh_period_s", 2.0)

        self.json_dir = pathlib.Path(self.get_parameter("json_dir").value)
        # QoS latchée des DEUX côtés (piège du 2026-07-12) : un abonné tardif reçoit le dernier.
        self.catalogue_pub = self.create_publisher(StringTime, topics.CATALOGUE, qos.latched())
        self.sha_pub = self.create_publisher(StringTime, topics.DEPLOY_SHA, qos.latched())

        sha = read_deploy_sha(self.get_parameter("deploy_sha_file").value)
        self.sha_pub.publish(stringtime.encode(sha, msg_type=StringTime))
        self.get_logger().info("deploy_sha publié : {}".format(sha))

        self.last_json = None
        self._refresh()  # publication initiale sans attendre la première période
        self.create_timer(self.get_parameter("refresh_period_s").value, self._refresh)

    def _refresh(self) -> None:
        current = json.dumps(build_catalog(self.json_dir))
        to_publish = next_publication(self.last_json, current)
        if to_publish is None:
            return
        self.last_json = to_publish
        self.catalogue_pub.publish(StringTime(msg=to_publish, time=0, anim=False))
        self.get_logger().info("catalogue publié ({} octets)".format(len(to_publish)))


def main(args=None):
    rclpy.init(args=args)
    node = CatalogueNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
