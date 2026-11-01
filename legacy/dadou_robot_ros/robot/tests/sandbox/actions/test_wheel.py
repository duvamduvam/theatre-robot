import logging
import time
import unittest

from dadou_utils_ros.utils_static import WHEELS, LEFT, RIGHT, FORWARD, BACKWARD
from robot.actions.wheels import Wheels
from robot.robot_config import config
from robot.tests.sandbox.conf_test import TestSetup


class WheelTest(unittest.TestCase):
    test_setup = TestSetup()
    wheel = Wheels(config)

    logging.info("start wheels test")
    def test_run(self):

        logging.info("start test run")

        for w in range(0, 2):
            self.wheel.update({WHEELS: {LEFT: 20, RIGHT: 20}})
            #self.dir1.value = True
            time.sleep(5)
            self.wheel.update({WHEELS: {LEFT: -20, RIGHT: -20}})
            #self.dir1.value = False
            time.sleep(5)
        self.wheel.stop()

    def test_run2(self):

        logging.info("start test run")

        for w in range(0, 2):
            self.wheel.update({WHEELS: [0.2, 0.2]})
            #self.dir1.value = True
            time.sleep(5)
            self.wheel.update({WHEELS: [-0.2, -0.2]})
            #self.dir1.value = False
            time.sleep(5)
        self.wheel.stop()

    def test_run2(self):

        logging.info("start test run")

        self.wheel.update({WHEELS: FORWARD})
        time.sleep(1)

        self.wheel.update({WHEELS: BACKWARD})
        time.sleep(1)

        self.wheel.update({WHEELS: LEFT})
        time.sleep(1)

        self.wheel.update({WHEELS: RIGHT})

        time.sleep(1)

        self.wheel.stop()

    def test_wheel_stop(self):
        self.wheel.stop()