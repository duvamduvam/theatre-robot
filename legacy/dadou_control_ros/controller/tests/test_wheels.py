import time
import unittest

from coverage.annotate import os

from dadou_utils_ros.com.serial_devices_manager import SerialDeviceManager
from dadou_utils_ros.com.ws_client import WsClient
from dadou_utils_ros.utils_static import WHEEL_LEFT, WHEEL_RIGHT
from controller.control_static import WS_CLIENT

from controller.files.control_json_manager import ControlJsonManager

from controller.com.robot_message import RobotMessage
from robot_config import DEVICES, JSON_DIRECTORY, JSON_CONFIG


class WheelsTests(unittest.TestCase):

    base_path = os.path.dirname(__file__)
    base_path = os.path.abspath(os.path.join(base_path, os.pardir))
    control_json_manager = ControlJsonManager(base_path, JSON_DIRECTORY, JSON_CONFIG)
    devices_manager = SerialDeviceManager(control_json_manager.get_config_item(DEVICES))
    ws_client = WsClient(control_json_manager.get_config_item(WS_CLIENT))
    robot_msg = RobotMessage(ws_client, devices_manager)

    def test_move(self):

        for x in range(20):
            msg = {WHEEL_LEFT:50, WHEEL_RIGHT:50}
            self.robot_msg.send(msg)
            time.sleep(1)