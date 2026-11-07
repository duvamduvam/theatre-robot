import time
import unittest

import adafruit_pcf8574
import board


class TestPCF8574(unittest.TestCase):
    i2c = board.I2C()  # uses board.SCL and board.SDA
    pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)

    dir1 = pcf.get_pin(0)

    for w in range(0, 4):
        pcf.get_pin(w).value = True

    def test_relay(self):
        for w in range(0, 4):
            self.pcf.get_pin(w).value = False
            time.sleep(5)
            self.pcf.get_pin(w).value = True
            time.sleep(5)


if __name__ == '__main__':
    unittest.main()
