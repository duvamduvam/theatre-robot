#!/usr/bin/env python3
import json
import logging
import logging.config

from robot.robot_config import config
import rclpy
from std_msgs.msg import String
from adafruit_led_animation.helper import PixelSubset
from rclpy.node import Node
import time
from robot_interfaces.msg._string_time import StringTime


from dadou_utils_ros.misc import Misc
from robot.files.robot_json_manager import RobotJsonManager
from robot.robot_static import LIGHTS_START_LED, LIGHTS_LED_COUNT, LIGHTS_PIN, LIGHTS_END_LED, \
    I2C_ENABLED, DIGITAL_CHANNELS_ENABLED, TICK_PERIOD_S
from dadou_utils_ros.utils_static import BRIGHTNESS, ROBOT_LIGHTS, FACE, JSON_LIGHTS, LIGHTS, \
    LOGGING_FILE_NAME, DURATION
from robot.actions.face import Face
from robot.actions.lights import Lights
from robot.nodes.payload import decode
from robot.robot_config import config
from dadou_utils_ros.logging_conf import LoggingConf


class LightsNode(Node):
    def __init__(self):
        node_name = 'lights_node'
        logging.config.dictConfig(LoggingConf.get(config[LOGGING_FILE_NAME], node_name))
        super().__init__(node_name)

        self.enabled = Misc.is_raspberrypi()
        logging.info("init  {} lights i2c enabled {}".format(node_name, self.enabled))

        if not self.enabled:
            return

        # Import différé (lib Pi absente sur x86), dans la branche `enabled`
        # uniquement. FastNeoPixel = chemin DIRECT vers _rpi_ws281x : la
        # résolution de backend du neopixel stock est cassée dans le conteneur
        # (ruban noir silencieux), et le sleep de fin de trame est CONSERVÉ
        # (sa suppression corrompait les trames : « deux signaux entrelacés »).
        # Voir docs/incidents/2026-07-13-glitch-visage-driver-led.md.
        from robot.visual.fast_neopixel import FastNeoPixel

        robot_json_manager = RobotJsonManager(config)
        pixels = FastNeoPixel(config[LIGHTS_PIN], config[LIGHTS_LED_COUNT], auto_write=False,
                              brightness=config[BRIGHTNESS])

        self.face = Face(config=config, json_manager=robot_json_manager, strip=pixels)
        self.lights = Lights(config=config, start=config[LIGHTS_START_LED], end=config[LIGHTS_END_LED],
            json_manager=robot_json_manager, global_strip=pixels, light_type=ROBOT_LIGHTS, json_light=config[JSON_LIGHTS])

        self.lights_subscription = self.create_subscription(
            StringTime, ROBOT_LIGHTS, self.lights_callback, 10)

        self.face_subscription = self.create_subscription(
            StringTime, FACE, self.face_callback, 10)

        self.timer = self.create_timer(TICK_PERIOD_S, self.timer_callback)

    def face_callback(self, ros_msg):
        msg = decode(ros_msg, FACE)
        if msg is None:
            return
        duration = ros_msg.time
        logging.info('Face: "%s"' % msg)
        self.face.update({FACE: msg, DURATION: duration})

    def lights_callback(self, ros_msg):
        msg = decode(ros_msg, ROBOT_LIGHTS)
        if msg is None:
            return
        duration = ros_msg.time
        logging.info('Lights: "%s"' % msg)
        self.lights.update({ROBOT_LIGHTS: msg, DURATION: duration})

    def generic_callback(self, lights_type, ros_msg):
        msg = decode(ros_msg, lights_type)
        if msg is None:
            return
        action_msg = {lights_type: msg}
        if ros_msg.time != 0:
            action_msg[DURATION] = ros_msg.time
        logging.info("{} send : {}".format(lights_type, ros_msg))
        self.lights.update(action_msg)

    def timer_callback(self):
        try:
            self.face.process()
            self.lights.process()
        except Exception as e:
            logging.error(e, exc_info=True)



def main(args=None):
    rclpy.init(args=args)
    node = LightsNode()
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
