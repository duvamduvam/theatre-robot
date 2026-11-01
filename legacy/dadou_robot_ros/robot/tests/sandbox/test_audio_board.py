import time
import unittest

import adafruit_pcf8574
import board


class TestAudioBoard(unittest.TestCase):
    i2c = board.I2C()  # uses board.SCL and board.SDA
    pcf = adafruit_pcf8574.PCF8574(i2c, address=0x21)

    relay1 = pcf.get_pin(0)
    relay2 = pcf.get_pin(1)
    relay3 = pcf.get_pin(2)
    relay4 = pcf.get_pin(3)

    def test_something(self):
        for w in range(0, 3):
            for r in range(0, 4):
                print("test i2c relay {}".format(r))
                self.pcf.get_pin(r).value = True
                time.sleep(1)
                self.pcf.get_pin(r).value = False
                time.sleep(1)



if __name__ == '__main__':
    unittest.main()