import logging
import logging.config
import time
import unittest

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME, TYPE, ANIMATION
from robot.files.robot_json_manager import RobotJsonManager
from robot.robot_config import config
from robot.sequences.animation_manager import AnimationManager


class MyTestCase(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test animation"))
    robot_json_manager = RobotJsonManager(config)
    animations_manager = AnimationManager(config, robot_json_manager)

    def test_animation(self):
        self.animations_manager.update({ANIMATION: "bug1"})
        while True:
            self.animations_manager.process()
            time.sleep(0.1)

    def test_random_type(self):
        self.animations_manager.update({ANIMATION: {TYPE: "bug"}})
        while True:
            self.animations_manager.process()
            time.sleep(0.1)

