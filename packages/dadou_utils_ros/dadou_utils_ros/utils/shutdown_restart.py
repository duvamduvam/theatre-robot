import logging
import os

from digitalio import DigitalInOut, Direction, Pull

from dadou_utils_ros.utils.time_utils import TimeUtils

import time

SHUTDOWN_CMD = 'sudo shutdown now -h'
RESTART_CMD = 'sudo restart'
STATUS_LED_INTERVAL = 500


class ShutDownRestart:
    def __init__(self, shutdown_pin, restart_pin, status_pin):

        self.shutdown_button = DigitalInOut(shutdown_pin)
        self.shutdown_button.direction = Direction.INPUT
        self.shutdown_button.pull = Pull.UP

        self.restart_button = DigitalInOut(restart_pin)
        self.restart_button.direction = Direction.INPUT
        self.restart_button.pull = Pull.UP

        self.status_led = DigitalInOut(status_pin)
        self.status_led.direction = Direction.OUTPUT

        self.last_led_status_check = 0

    def update(self, msg):
        pass

    def process(self):
        self.check_button(self.shutdown_button, SHUTDOWN_CMD)
        self.check_button(self.restart_button, RESTART_CMD)
        self.led_status()

    def check_button(self, button, command):
        #logging.debug("{} {}".format(button, button.value))
        if not button.value:
            # Check to see if button is pressed
            time.sleep(1)
            # wait for the hold time
            if not button.value:
                # check to see if button is pressed
                logging.warning("exec command_root {}".format(command))
                os.system(command)
                time.sleep(1)

    def led_status(self):
        if TimeUtils.is_time(self.last_led_status_check, STATUS_LED_INTERVAL):
            self.status_led.value = not self.status_led.value
            self.last_led_status_check = TimeUtils.current_milli_time()

