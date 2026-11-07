#!/usr/bin/env python3
import logging
import time

import rclpy
from rclpy.node import Node

from dadou_utils_ros.utils_static import RELAY
from didier_core.actions.relays import RelaysManager
from didier_core.files.robot_json_manager import RobotJsonManager
from didier_core.nodes.abstract_subscriber import SubscriberNode
from didier_core.robot_config import config


class RelaysNode(SubscriberNode):
    def __init__(self):
        robot_json_manager = RobotJsonManager(config)
        self.relays = RelaysManager(config, robot_json_manager)
        super().__init__(config, RELAY, RELAY, self.relays)


def main(args=None):
    rclpy.init(args=args)
    node = RelaysNode()
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