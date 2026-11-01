import logging
import time
import unittest

#from buttons.gp_buttons import GPButtons
from controller.control_config import config, BUTTONS_MAPPING
#from control_factory import ControlFactory
from dadou_utils_ros.com.input_messages_list import InputMessagesList
from dadou_utils_ros.com.serial_devices_manager import SerialDeviceManager
from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import DEVICES
from controller.control_static import INPUT_KEY, BUTTON, GLOVE_LEFT
from controller.input.serial_inputs import SerialInputs


class TestInputDevices(unittest.TestCase):

    def test_glove_plugged(self):
        serial_inputs = SerialInputs()
        #input_device = serial_inputs.get_group(INPUT_KEY)
        if serial_inputs.device_connected(GLOVE_LEFT):
            print("glove plugged")
        else:
            print("glove unplugged")

        #if self.devices_manager.input_connected(serial_inputs.serial_devices[SLIDERS], "slider"):
        #    self.slider_label, self.slider_icon, self.hand_image = self.create_label_icon("sliders.png")


    def test_buttons(self):

        current_time = TimeUtils.current_milli_time()

        while not TimeUtils.is_time(last_time=current_time, time_out=60000):

            self.devices_manager.check_buttons(BUTTONS_MAPPING)
            while InputMessagesList().has_msg():
                print(InputMessagesList().pop_msg())
            time.sleep(0.01)

    #def test_buttons2(self):

    #    devices_manager = SerialDeviceManager(config[DEVICES], [BUTTON])
    #    input_buttons = GPButtons(devices_manager)

    #    current_time = TimeUtils.current_milli_time()
    #    while not TimeUtils.is_time(last_time=current_time, time_out=60000):

    #        input_buttons.check_internal()
    #        input_buttons.check_external()

    #        messages = InputMessagesList().pop_dict()
    #        if messages:
    #            logging.info(messages)
    #            InputMessagesList().add_msg(messages)

    #        time.sleep(0.02)

if __name__ == '__main__':
    unittest.main()

