import json
import logging
import logging.config
import os
import socket
import sys

import rclpy
from rclpy.node import Node
from robot_interfaces.msg._string_time import StringTime
import tkinter as tk

from controller.control_config import config, PUBLISHER_LIST

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils_static import (
    AUDIO, FACE, ROBOT_LIGHTS, RELAY, LEFT_EYE, NECK, RIGHT_EYE, LEFT_ARM, RIGHT_ARM, ANIMATION,
    LOGGING_CONFIG_FILE, WHEELS, DURATION, LOGGING_FILE_NAME, WHEEL_LEFT, WHEEL_RIGHT, RANDOM, TYPE,
    LOGGING_TEST_FILE_NAME,
)
from controller.control_static import RANDOM_ANIMATION
from controller.gui.small_gui import SmallGui


class Ros2TkinterApp(Node):
    def __init__(self):
        if 'unittest' in sys.modules:
            logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "controller"))
        else:
            logging.config.dictConfig(LoggingConf.get(config[LOGGING_FILE_NAME], "controller"))
        super().__init__("controller_node")
        hostname = socket.gethostname()
        logging.info("start controller node {}".format(hostname))

        self.action_publishers = {}
        for p in PUBLISHER_LIST:
            if not RANDOM in p:
                self.action_publishers[p] = self.create_publisher(StringTime, p, 10)

        # Choix de l'interface : un DISPLAY X11 disponible => GUI Tkinter (écran
        # HDMI, cas du Pi "control" et du PC). Sans DISPLAY => rendu Pillow sur
        # LCD SPI (ancien setup OS Lite sans bureau). Les gants ("gl") gardent
        # leur petite GUI.
        if "gl" in hostname or not Misc.is_raspberrypi() or os.environ.get('DISPLAY'):
            logging.info("start small gui (tkinter, DISPLAY={})".format(os.environ.get('DISPLAY')))
            self.gui = SmallGui(self)
        else:
            logging.info("start pillow gui (LCD SPI, pas de DISPLAY)")
            from controller.gui.pillow.TkPillowGui import PillowGuiApp
            self.gui = PillowGuiApp(self)

        self.timer = self.create_timer(0.1, self.timer_callback)

    def timer_callback(self):
        #pass
        self.gui.update()

    def publish(self, animations_msg):
        if animations_msg and isinstance(animations_msg, dict):
            for k, v in animations_msg.items():
                if k in PUBLISHER_LIST:
                    msg = StringTime()
                    if RANDOM in k:
                        msg.msg = json.dumps({TYPE: v})
                        k = k.replace("{} ".format(RANDOM), "")
                    else:
                        msg.msg = json.dumps(v)
                    if(DURATION in animations_msg):
                        msg.time = animations_msg[DURATION]
                    self.action_publishers[k].publish(msg)
                    logging.info("published in {} => {}".format(k, msg))

def main(args=None):
    try:
        rclpy.init(args=args)
        ros_tk_app = Ros2TkinterApp()
        rclpy.spin(ros_tk_app)
        rclpy.shutdown()
    except Exception as e:
        logging.error(e, exc_info=True)

if __name__ == '__main__':
    main()