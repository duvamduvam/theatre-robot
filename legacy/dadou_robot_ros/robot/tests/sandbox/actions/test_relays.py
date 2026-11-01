import time
import unittest

import adafruit_pcf8574
import board
from digitalio import DigitalInOut, Direction


class TestRelays(unittest.TestCase):

    def test_direct(self):
        relay = DigitalInOut(board.D5)
        relay.direction = Direction.OUTPUT

        relay_on = False

        for x in range(0, 50):

            print("switch "+str(relay_on))
            relay.value = relay_on
            relay_on = not relay_on
            time.sleep(5)

    def test_kalxon(self):
        i2c = board.I2C()  # uses board.SCL and board.SDA
        pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)
        self.test_reset()

        klaxon = pcf.get_pin(2)

        klaxon.value = False
        time.sleep(10)
        klaxon.value = True


    def test_reset(self):
        i2c = board.I2C()  # uses board.SCL and board.SDA
        pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)

        for x in range(0, 4):
            pcf.get_pin(x).value = True

    def test_i2c(self):
        i2c = board.I2C()  # uses board.SCL and board.SDA
        pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)

        relay = pcf.get_pin(0)

        for x in range(0, 3):
            relay.value = True
            time.sleep(5)
            relay.value = False
            time.sleep(5)
