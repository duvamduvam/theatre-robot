import time
import unittest
import logging
import logging.config

from controller.control_config import config
from controller.input.usb_gamepad import USBGamepad, BUTTON_KEYS, JOYSTICK_KEYS
from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME


class TestUSBGamePad(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test animation"))

    usb_gamepad = USBGamepad()

    def test_get_normalized_state(self):
        state = self.usb_gamepad.get_normalized_state()
        if state is None:
            # Retry once in case of transient headless pump error
            state = self.usb_gamepad.get_normalized_state()

        self.assertIsInstance(state, dict)
        for key in (
            "connected",
            "A",
            "B",
            "X",
            "Y",
            "L1",
            "L2",
            "R1",
            "R2",
            "START",
            "SELECT",
            "UP",
            "DOWN",
            "LEFT",
            "RIGHT",
            "LX",
            "LY",
            "RX",
            "RY",
        ):
            self.assertIn(key, state)

        self.assertIn(state["connected"], (0, 1))
        # Buttons are on/off
        for btn in ("A", "B", "X", "Y", "L1", "L2", "R1", "R2", "START", "SELECT", "UP", "DOWN", "LEFT", "RIGHT"):
            self.assertIn(state[btn], (0, 1))
        for axis_key in ("LX", "LY", "RX", "RY"):
            self.assertIsInstance(state[axis_key], int)
            self.assertGreaterEqual(state[axis_key], 0)
            self.assertLessEqual(state[axis_key], 99)

    def test_check(self):
        # Should not raise and should log a normalized state or a one-time notice
        for _ in range(100):
            result = self.usb_gamepad.check_inputs()
            time.sleep(0.1)

    def test_active_inputs(self):
        for _ in range(200):
            result = self.usb_gamepad.check_inputs()
            time.sleep(0.1)

