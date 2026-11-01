# SPDX-FileCopyrightText: Copyright (c) 2022 ladyada for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import time
import unittest

import board
import adafruit_pcf8575

class TestPCF8575(unittest.TestCase):

    print("PCF8575 16 output LED blink test")

    i2c = board.I2C()  # uses board.SCL and board.SDA
    # i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
    pcf = adafruit_pcf8575.PCF8575(i2c)

    def test_simple(self):

        led = self.pcf.get_pin(7)

        while True:
            led.value = True
            time.sleep(1)
            led.value = False
            time.sleep(1)

    def test_stepper(self):

        step = self.pcf.get_pin(0)
        dir = self.pcf.get_pin(1)
        enable = self.pcf.get_pin(2)
        enable.value = True

        durationFwd = 5000  # This is the duration of the motor spinning. used for forward direction
        durationBwd = 5000  # This is the duration of the motor spinning. used for reverse direction
        #
        delay = 0.001  # This is actualy a delay between PUL pulses - effectively sets the mtor rotation speed.
        print('Speed set to ' + str(delay))
        #
        cycles = 500  # This is the number of cycles to be run once program is started.
        cyclecount = 0  # This is the iteration of cycles to be run once program is started.
        print('number of Cycles to Run set to ' + str(cycles))


        #
        time.sleep(.5)  # pause due to a possible change direction

        print('DIR set to LOW - Moving Forward at ' + str(delay))
        print('Controller PUL being driven.')
        for x in range(durationFwd):
            step.value = True
            time.sleep(delay)
            step.value = False
            time.sleep(.05)

        enable.value = False
        time.sleep(.5)  #