#!/usr/bin/env python3
"""Node `objets_node` — l'ÉCRIVAIN du tableau des objets (lot O1, 18/11), I/O ROS SEULEMENT.

Étude docs/etudes/etude-objets-vus-et-carte.md §6. Toute la logique est dans tableau.py (pure,
testée sans ROS) ; le contrat du topic dans theatre_contrats/objets.py.

Lit   : rehearsal/objects (LATCHÉ, la carte de la régie : sim ou lieu préparé),
        ground_truth/odom (pose vérité terrain, SIM ; périmée après POSE_TTL_S -> plus de
        distance, rien d'atteignable — jamais une vieille pose prise pour vraie).
Écrit : scene/objets (LATCHÉ), toutes les `periode_s` (1 s) et à chaque changement de carte.
        Les lecteurs (bouche, réflexion) périment le tableau s'il se tait 3 s.

Pas de garde de domaine : ce nœud ne commande RIEN (aucun Twist, aucun ordre) ; il tourne
aussi sur le Pi vision, où, sans carte ni pose, il publie un tableau vide. Le chemin roues ne
passe pas ici : le tableau fournit une CIBLE, la régie et route_driver décident et bornent.
"""
import json
import math
import time

from theatre_contrats import objets as contrat
from theatre_contrats import topics

from didier_perception.tableau import CHAMP_DEMI_DEG, VUE_MAX_M, TableauObjets, carte_depuis_payload

# Littéraux gravés avec didier_rehearsal.contracts (OBJECTS_TOPIC, ODOM_TOPIC) par
# test/test_objets_node.py : pas d'import du package de la régie, absent du Pi vision.
CARTE_TOPIC = "rehearsal/objects"
ODOM_TOPIC = "ground_truth/odom"
# Pose plus vieille que ça : oubliée (la régie juge « pose fraîche » à 1 s aussi).
POSE_TTL_S = 1.0
PERIODE_S = 1.0


def cap_depuis_quaternion(q) -> float:
    """Lacet (rad) d'une orientation 2D."""
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def main(args=None):
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from theatre_interfaces.msg import StringTime
    from theatre_contrats import qos

    class ObjetsNode(Node):
        def __init__(self):
            super().__init__("objets_node")
            self.declare_parameter("champ_demi_deg", CHAMP_DEMI_DEG)
            self.declare_parameter("vue_max_m", VUE_MAX_M)
            self.declare_parameter("periode_s", PERIODE_S)
            p = lambda n: self.get_parameter(n).value  # noqa: E731
            self.tableau = TableauObjets(float(p("champ_demi_deg")), float(p("vue_max_m")))
            self._pose_t = None
            self.pub = self.create_publisher(StringTime, topics.SCENE_OBJETS, qos.latched())
            self.create_subscription(StringTime, CARTE_TOPIC, self._on_carte, qos.latched())
            self.create_subscription(Odometry, ODOM_TOPIC, self._on_odom, 10)
            self.create_timer(float(p("periode_s")), self._publier)
            self.get_logger().info(f"tableau des objets -> {topics.SCENE_OBJETS} (carte : {CARTE_TOPIC}, "
                                   f"pose : {ODOM_TOPIC})")

        def _on_carte(self, msg):
            try:
                carte = carte_depuis_payload(json.loads(msg.msg))
            except (ValueError, TypeError) as e:
                self.get_logger().warning(f"{CARTE_TOPIC} illisible, carte précédente gardée : {e!r}")
                return
            self.tableau.poser_carte(carte)
            self.get_logger().info(f"carte : {len(carte)} objet(s)")
            self._publier()

        def _on_odom(self, msg):
            pose = msg.pose.pose
            self.tableau.poser_pose("monde", pose.position.x, pose.position.y,
                                    cap_depuis_quaternion(pose.orientation))
            self._pose_t = time.monotonic()

        def _publier(self):
            now = time.monotonic()
            if self._pose_t is not None and now - self._pose_t > POSE_TTL_S:
                self.tableau.oublier_pose()
                self._pose_t = None
                self.get_logger().warning(f"{ODOM_TOPIC} muet depuis {POSE_TTL_S:g} s : pose oubliée")
            try:
                objets = self.tableau.instantane(now)
                self.pub.publish(StringTime(msg=contrat.encoder(objets, self.tableau.pose, int(time.time() * 1000)),
                                            time=0, anim=False))
            except Exception as e:  # noqa: BLE001 — un timer qui lève tuerait le node
                self.get_logger().error(f"publication du tableau : {e!r}")

    rclpy.init(args=args)
    node = ObjetsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
