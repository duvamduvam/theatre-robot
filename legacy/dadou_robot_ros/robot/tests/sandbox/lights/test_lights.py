import logging
import os

from dadou_utils_ros.utils.time_utils import TimeUtils
from robot.actions.lights import Lights
from robot.files.robot_json_manager import RobotJsonManager
from robot.robot_config import JSON_DIRECTORY, JSON_CONFIG
from robot.tests.sandbox.conf_test import TestSetup

TestSetup()

import unittest



class LightsTest(unittest.TestCase):
    RED = (255, 0, 0)
    YELLOW = (255, 150, 0)
    GREEN = (0, 255, 0)
    CYAN = (0, 255, 255)
    BLUE = (0, 0, 255)
    PURPLE = (180, 0, 255)
    BLACK = (0, 0, 0)

    base_path = os.getcwd()
    robot_json_manager = RobotJsonManager(base_path, "/.."+JSON_DIRECTORY, JSON_CONFIG)
    config = RobotConfig(robot_json_manager)

    pixel_pin = board.D18

    # The number of NeoPixels
    num_pixels = 30

    # The order of the pixel colors - RGB or GRB. Some NeoPixels have red and green reversed!
    # For RGBW NeoPixels, simply change the ORDER to RGBW or GRBW.
    ORDER = neopixel.GRB

    pixels = neopixel.NeoPixel(
        pixel_pin, num_pixels, brightness=0.2, auto_write=False, pixel_order=ORDER
    )

    lights = Lights(config, robot_json_manager, pixels)

    def test_lights_key(self):
        current_time = TimeUtils.current_milli_time()
        while not TimeUtils.is_time(current_time, 2000):
            self.lights.process()

        keys = {"C2", "C3", "C10"}
        for k in keys:
            logging.info("test lights key " + k)
            self.lights.update(k)
            current_time = TimeUtils.current_milli_time()
            while not TimeUtils.is_time(current_time, 10000):
                self.lights.process()

    def test_lights_default(self):
        # self.lights.update("B1")
        while True:
            self.lights.process()
