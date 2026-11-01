#!/usr/bin/env python3
import logging
import logging.config

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import WHEELS, LOGGING_FILE_NAME
from robot.actions.wheels import Wheels
from robot.nodes.abstract_subscriber import SubscriberNode
from robot.robot_config import config, WHEELS_CMD_VEL_ENABLED

CMD_VEL_TOPIC = "cmd_vel"


class WheelsNode(SubscriberNode):
    """Mode legacy (défaut) : consomme le StringTime legacy sur le topic WHEELS
    et pilote directement le PWM. Comportement STRICTEMENT inchangé."""

    def __init__(self):
        self.wheels = Wheels(config)
        super().__init__(config, WHEELS, WHEELS, self.wheels)


class WheelsCmdVelNode(Node):
    """Mode /cmd_vel : dernier maillon de la chaîne twist_mux -> twist_deadman.
    S'abonne à geometry_msgs/Twist sur /cmd_vel et applique la consigne aux roues.
    Le deadman local 400 ms de Wheels reste actif comme ultime rempart si toute
    la chaîne ROS amont se tait (voir Wheels.apply_twist / check_stop)."""

    def __init__(self):
        logging.config.dictConfig(LoggingConf.get(config[LOGGING_FILE_NAME], "wheels_node"))
        super().__init__("wheels_node")

        self.wheels = Wheels(config)

        logging.info("Starting wheels_node en mode /cmd_vel (topic {})".format(CMD_VEL_TOPIC))

        self.subscription = self.create_subscription(
            Twist,
            CMD_VEL_TOPIC,
            self.cmd_vel_callback,
            10)

        self.timer = self.create_timer(0.1, self.timer_callback)

    def cmd_vel_callback(self, twist):
        self.wheels.apply_twist(twist.linear.x, twist.angular.z)

    def timer_callback(self):
        try:
            self.wheels.process()
        except Exception as e:
            logging.error(e, exc_info=True)


def main(args=None):
    rclpy.init(args=args)
    # Le mode est figé au démarrage par le drapeau de config : la bascule vers
    # /cmd_vel n'a lieu qu'après validation physique caméra.
    if config[WHEELS_CMD_VEL_ENABLED]:
        logging.info("wheels_node: mode /cmd_vel ACTIVÉ (WHEELS_CMD_VEL_ENABLED)")
        node = WheelsCmdVelNode()
    else:
        logging.info("wheels_node: mode legacy StringTime (WHEELS_CMD_VEL_ENABLED désactivé)")
        node = WheelsNode()
    try:
        while rclpy.ok():
            try:
                rclpy.spin_once(node)
            except Exception as e:
                logging.error(e, exc_info=True)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()
