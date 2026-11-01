import board
import digitalio
import time
import unittest
import RPi.GPIO as GPIO

from controller.buttons.gp_buttons import GPButtons

class TestGamePad(unittest.TestCase):
    print(dir(board))

    """start 21
    select 4
    A 26
    B 12
    Y 20
    X 16
    Left 23
    Right 18
    """

    GPIOs = [board.D1, board.D2, board.D3, board.D4, board.D5, board.D6, board.D7, board.D8, board.D9, board.D10,
             board.D11, board.D12, board.D13, board.D14, board.D15, board.D16, board.D17, board.D18, board.D19, board.D20,
             board.D21, board.D22, board.D23, board.D24, board.D25, board.D26, board.D27]

    #X = AnalogIn(board.D16)
    #Y = AnalogIn(board.D20)

    # Setup all GPIOs to input
    buttons = []
    for gpio in GPIOs:
        button = digitalio.DigitalInOut(gpio)
        button.switch_to_input(pull=digitalio.Pull.UP)
        buttons.append({"pin": gpio, "button": button})


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
            for button in self.buttons:
                if not button["button"].value:
                    print("selected ! {}".format(button["pin"]))
            #for gpio in self.GPIOs:
            #    print("GPIO no " + str(gpio) + ": " + str(GPIO.input(gpio)))
            #print(" {} / {}".format(self.X.value, self.Y.value))
            time.sleep(0.1)

    def test_gp_class(self):
        gp_buttons = GPButtons()
        print("start test")
        while True:
            gp_buttons.check()
            time.sleep(0.1)


if __name__ == '__main__':
    unittest.main()
