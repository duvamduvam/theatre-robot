import time
import unittest
import RPi.GPIO as GPIO

class TestGamePad(unittest.TestCase):

    GPIO.setmode(GPIO.BCM)
    GPIOs = [4, 12, 16, 18, 20, 21, 23]
    # Setup all GPIOs to input
    for gpio in GPIOs:
        GPIO.setup(gpio, GPIO.IN)


    """def my_callback(channel):
        if var == 1:
            sleep(1.5)  # confirm the movement by waiting 1.5 sec
            if GPIO.input(7):  # and check again the input
                print("Movement!")
                captureImage()

                # stop detection for 20 sec
                GPIO.remove_event_detect(7)
                sleep(20)
                GPIO.add_event_detect(7, GPIO.RISING, callback=my_callback, bouncetime=300)"""

    def test_buttons(self):
        while True:
            for gpio in self.GPIOs:
                if GPIO.input(gpio):
                    print("{} GPIO {} value {}".format(time.monotonic(), gpio, GPIO.input(gpio)))
            time.sleep(0.1)


if __name__ == '__main__':
    unittest.main()
