import logging
from os.path import exists

from dadou_utils_ros.com.input_messages_list import InputMessagesList
from dadou_utils_ros.com.serial_device import SerialDevice
from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import NAME, TYPE, SERIAL_ID, DEVICE_MSG_SIZE, BAUD_RATE, MSG, BUTTON


class SerialDeviceManager:
    last_update = 0
    update_period = 500

    def __init__(self, expected_devices, devices_type):
        #logging.info("search devices {}".format(expected_devices))
        self.expected_devices = expected_devices
        self.existing_devices = []

        self.update_devices()
        self.device_groups = self.load_devices_type(devices_type)
        #schedule.every(10).seconds.do(self.update_devices)

    def load_devices_type(self, devices_type):
        groups = {}
        if devices_type:
            for device_type in devices_type:
                groups[device_type] = self.get_device_type(device_type)
        return groups

    def update_devices(self):
        self.update_period = TimeUtils.current_milli_time()
        for expected_device in self.expected_devices:
            expected_device_exist = exists(SerialDevice.USB_ID_PATH+expected_device[SERIAL_ID])
            new_device = True
            for existing_device in self.existing_devices:
                if expected_device[NAME] == existing_device.name:
                    if not expected_device_exist:
                        self.remove_device(existing_device.name)
                    new_device = False
                    break
            if new_device and expected_device_exist:
                self.add_device(SerialDevice(expected_device))

    def reset_devices(self):
        self.existing_devices = []
        self.update_devices()

    def add_device(self, device):
        self.existing_devices.append(device)
        logging.info("add device {}".format(device.name))

    def remove_device(self, name):
        device = self.get_device(name)
        self.existing_devices.remove(device)
        logging.warning("device {} removed".format(name))

    def get_device(self, name):
        for device in self.existing_devices:
            if device.name == name:
                return device

    def get_device_type(self, type):
        devices = []
        for device in self.existing_devices:
            if device.type == type:
                devices.append(device)
        return devices

    def input_connected(self, type, name):
        connected = False
        for input_device in type:
            if name in input_device.name:
                connected = True
        return connected

    def check_buttons(self, mapping):
        if BUTTON not in self.device_groups:
            logging.error("no button group")
            return

        for button in self.device_groups[BUTTON]:
            msg = button.get_msg_separator()
            if msg:
                if button.default_msg in mapping:
                    logging.info("serial button {} pressed, value {}".format(button.default_msg, mapping[button.default_msg]))
                    self.node.publish(mapping[button.default_msg])
