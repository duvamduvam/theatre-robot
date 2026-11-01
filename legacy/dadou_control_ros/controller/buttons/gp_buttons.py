import logging

import board
import digitalio

from controller.buttons.button_config import GLOVE_MAPPING
from controller.control_config import BUTTONS_MAPPING
from controller.control_factory import ControlFactory
from dadou_utils_ros.com.input_messages_list import InputMessagesList
from dadou_utils_ros.com.serial_devices_manager import SerialDeviceManager
from dadou_utils_ros.utils_static import X, A, RIGHT, LEFT, Y, B, DOWN, UP, DEVICES, KEY
from controller.control_static import SELECT, START, BL, INPUT_KEY, BUTTON, BR

mapping = {SELECT: board.D4, UP: board.D5, DOWN: board.D6, B: board.D12, LEFT: board.D13,
           X: board.D16, BR: board.D18, RIGHT: board.D19, Y: board.D20,
         START: board.D21, BL: board.D23, A: board.D26}

#mapping = {board.D1, board.D2, board.D3, "SELECT": board.D4, "UP": board.D5, "DOWN": board.D6, board.D7, board.D8, board.D9, board.D10,
#         board.D11, "B": board.D12, "LEFT": board.D13, board.D14, board.D15, "X": board.D16, board.D17, "BR: board.D18, "RIGHT": board.D19, "Y": board.D20,
#         "START": board.D21, board.D22, "BL": board.D23, board.D24, board.D25, "A": board.D26, board.D27}


class GPButtons:

    def __init__(self, devices_manager):
        self.devices_manager = devices_manager

    buttons = []
    for key in mapping.keys():
        button = digitalio.DigitalInOut(mapping[key])
        button.switch_to_input(pull=digitalio.Pull.UP)
        buttons.append({KEY: key, BUTTON: button})
        print("key {} pin {}".format(key, mapping[key]))

    def check_internal(self, mode):
        for button in self.buttons:
            current_mapping = BUTTONS_MAPPING[mode]
            if not button[BUTTON].value and button[KEY] in current_mapping:
                self.node.publish(current_mapping[button[KEY]])
                logging.info("{} pressed with value {}".format(button[KEY], current_mapping[button[KEY]]))

    def check_external(self, mode):
        self.devices_manager.check_buttons(BUTTONS_MAPPING[mode])


