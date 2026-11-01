#!/usr/bin/env python3
"""Bridge entre le topic roues legacy (robot_interfaces/StringTime) et cmd_vel.

S'abonne au même topic que robot/nodes/wheels_node.py (constante WHEELS), pour
que la télécommande / les séquences JSON existantes puissent aussi piloter la
base ROS (ros2_control / Gazebo) sans toucher au vrai robot (PWM PCA9685).
Publie sur cmd_vel_anim si le message vient d'une animation (StringTime.anim),
sinon sur cmd_vel_remote ; ces deux flux sont arbitrés par twist_mux.
"""

import json
import logging

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

from robot_drive.diff_drive import DiffDrive
from robot_drive.wheels_payload import WHEELS, payload_to_pair, payload_to_speed
from robot_interfaces.msg import StringTime

CMD_VEL_ANIM_TOPIC = "cmd_vel_anim"
CMD_VEL_REMOTE_TOPIC = "cmd_vel_remote"


class WheelsBridgeNode(Node):

    def __init__(self):
        super().__init__("wheels_bridge_node")

        self.declare_parameter("wheel_separation", 0.58)
        self.declare_parameter("max_wheel_speed", 1.0)  # m/s à consigne 1.0, calibration physique à venir

        self.diff_drive = DiffDrive(
            wheel_separation=self.get_parameter("wheel_separation").value,
            max_wheel_speed=self.get_parameter("max_wheel_speed").value,
        )

        # Facteur vitesse issu du slider "vitesse" de la télécommande
        # ({WHEELS: {SPEED: pct}}). Il approxime, au niveau du Twist, le plafond
        # PWM (max_pwm) que le robot legacy appliquait : 1.0 = pleine échelle.
        self.speed_factor = 1.0

        self.anim_pub = self.create_publisher(Twist, CMD_VEL_ANIM_TOPIC, 10)
        self.remote_pub = self.create_publisher(Twist, CMD_VEL_REMOTE_TOPIC, 10)

        self.subscription = self.create_subscription(StringTime, WHEELS, self.listener_callback, 10)

    def listener_callback(self, ros_msg):
        try:
            raw = json.loads(ros_msg.msg)
        except (TypeError, json.JSONDecodeError) as e:
            logging.warning("payload roues illisible ({}) : {}".format(ros_msg.msg, e))
            return

        # Sur le fil, StringTime.msg ne porte que la VALEUR de la clé WHEELS
        # (main_no_gui.publish fait json.dumps(v)). On ré-emballe {WHEELS: valeur}
        # exactement comme abstract_subscriber.SubscriberNode côté robot, pour
        # réutiliser payload_to_pair / payload_to_speed sans divergence.
        payload = {WHEELS: raw}

        # Réglage vitesse : met à jour l'état interne, aucune consigne roue à publier.
        speed = payload_to_speed(payload)
        if speed is not None:
            self.speed_factor = speed
            return

        pair = payload_to_pair(payload)
        if pair is None:
            return

        twist = Twist()
        if isinstance(pair, tuple):
            linear_x, angular_z = self.diff_drive.wheels_to_twist(pair[0], pair[1])
            # Le facteur vitesse plafonne linéaire et angulaire (approx. du max_pwm legacy).
            twist.linear.x = linear_x * self.speed_factor
            twist.angular.z = angular_z * self.speed_factor
        # pair == STOP : on publie un Twist nul (déjà la valeur par défaut).

        if ros_msg.anim:
            self.anim_pub.publish(twist)
        else:
            self.remote_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = WheelsBridgeNode()
    try:
        rclpy.spin(node)
    except Exception as e:
        logging.error(e, exc_info=True)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
