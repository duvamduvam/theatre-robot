#!/usr/bin/env python3
"""LE maillon sécurité de la chaîne roues : coupe le mouvement si la source
(remote/anim, arbitrées par twist_mux sur cmd_vel_mux) s'est tue.

Republie cmd_vel_mux vers cmd_vel tel quel, mais un timer à 20 Hz vérifie en
continu qu'une commande est arrivée il y a moins de timeout_ms. Passé ce délai,
un Twist nul est publié À CHAQUE TICK tant que la source reste silencieuse :
le plugin DiffDrive de Gazebo (comme le vrai hardware) garde la dernière
consigne reçue, donc il faut insister pour être sûr que le robot s'arrête et
le reste. Sans ce nœud, un twist_mux ou un client qui se fige laisse le robot
foncer indéfiniment sur sa dernière consigne — voir feedback sécurité roues.
"""

import logging

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

from robot_drive.deadman import TwistDeadman

CMD_VEL_MUX_TOPIC = "cmd_vel_mux"
CMD_VEL_TOPIC = "cmd_vel"
TICK_PERIOD_S = 0.05  # 20 Hz


class TwistDeadmanNode(Node):

    def __init__(self):
        super().__init__("twist_deadman_node")

        self.declare_parameter("timeout_ms", 400)
        self.deadman = TwistDeadman(timeout_ms=self.get_parameter("timeout_ms").value)

        self.publisher = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.subscription = self.create_subscription(Twist, CMD_VEL_MUX_TOPIC, self.listener_callback, 10)
        self.timer = self.create_timer(TICK_PERIOD_S, self.timer_callback)

    def now_ms(self):
        # Horloge du node (et non l'horloge murale) : avec use_sim_time le
        # deadman doit suivre le temps simulé, sinon pause sim = faux timeout.
        return self.get_clock().now().nanoseconds // 1_000_000

    def listener_callback(self, twist):
        self.deadman.feed(self.now_ms())
        self.publisher.publish(twist)

    def timer_callback(self):
        if self.deadman.is_expired(self.now_ms()):
            self.publisher.publish(Twist())


def main(args=None):
    rclpy.init(args=args)
    node = TwistDeadmanNode()
    try:
        rclpy.spin(node)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
