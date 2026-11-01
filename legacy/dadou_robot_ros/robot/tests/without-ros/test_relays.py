import time
import unittest

import adafruit_pcf8574
import board
from digitalio import DigitalInOut, Direction


class TestRelays(unittest.TestCase):

    def test_kalxon(self):
        i2c = board.I2C()  # uses board.SCL and board.SDA
        pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)
        self.test_reset()

        klaxon = pcf.get_pin(2)
        for x in range(0, 5):
            klaxon.value = False
            time.sleep(5)
            klaxon.value = True
