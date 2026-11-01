import logging

import board
import digitalio
import time


class GamePad:

    buttons = {"1": board.D1, "select": board.D4, "3": board.D3, "5": board.D5, "6": board.D6, "7": board.D7, "8": board.D8, "9": board.D9, "10": board.D10, "11": board.D11,
             "B": board.D12, "13": board.D13, "14": board.D14, "15": board.D15, "right": board.D18, "19": board.D19, "start": board.D21, "23": board.D23, "A": board.D26}

    for b in buttons.keys():
        button = digitalio.DigitalInOut(b)
        button.switch_to_input(pull=digitalio.Pull.UP)
    #    buttons.append({"pin":gpio, "button":button})

    def check(self):
        for b in self.buttons.keys():
            if digitalio.DigitalInOut(b).value:
                logging.info("button {} pressed".format(self.buttons[b]))

    """start 21
    select 4
    A 26
    B 12
    Y 20
    X 16
    Left 23
    Right 18
    """

    #X = AnalogIn(board.D16)
    #Y = AnalogIn(board.D20)

    # Setup all GPIOs to input
    #buttons = []
    #for gpio in GPIOs:
    #    button = digitalio.DigitalInOut(gpio)
    #    button.switch_to_input(pull=digitalio.Pull.UP)
    #    buttons.append({"pin":gpio, "button":button})