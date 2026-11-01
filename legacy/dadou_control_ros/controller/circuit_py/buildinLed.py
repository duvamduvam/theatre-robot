import time

import board
import digitalio

FLASH = "flash"
BLINK = "blink"

class BuildinLed:

    def __int__(self, pin=board.LED):

        self.led = digitalio.DigitalInOut(pin)
        self.led.direction = digitalio.Direction.OUTPUT
        self.lastBlink = float(0)
        self.blinkRate = float(0.5)
        self.flashRate = float(0.05)
        self.currentRate = self.blinkRate

        flashNb = 6
        flashCount = 0
        mode = BLINK

    # print("Start Blink!")

    def blink(self):
        self.mode = BLINK
        self.currentRate = self.blinkRate

    def flash(self):
        self.mode = FLASH
        self.flashCount = 0
        self.currentRate = self.flashRate

    def process(self):
        if time.monotonic() > (self.lastBlink + self.currentRate):
            self.led.value = not self.led.value
            self.lastBlink = time.monotonic()
            if self.mode == FLASH:
                if self.flashCount >= self.flashNb:
                    self.blink()
                else:
                    self.flashCount += 1
