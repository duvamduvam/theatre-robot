# Imports matériels différés (pattern wheels.py) : le module doit s'importer sans les libs Pi.
import logging
import random
import time

from dadou_utils_ros.utils_static import COLOR



class LightsAnimations:

    def __init__(self, led_count, strip):
        self.LED_COUNT = led_count
        self.strip = strip

        # La pile adafruit_led_animation n'est installable que sur le Pi. On
        # l'importe à la construction (LightsAnimations n'est instancié que par
        # Lights.__init__, côté matériel) et on garde les classes sous la main :
        # la CONSTRUCTION des objets Chase/Blink/... reste lazy, dans les méthodes.
        from adafruit_led_animation.animation.blink import Blink
        from adafruit_led_animation.animation.chase import Chase
        from adafruit_led_animation.animation.colorcycle import ColorCycle
        from adafruit_led_animation.animation.comet import Comet
        from adafruit_led_animation.animation.pulse import Pulse
        from adafruit_led_animation.animation.rainbow import Rainbow
        from adafruit_led_animation.animation.rainbowchase import RainbowChase
        from adafruit_led_animation.animation.rainbowcomet import RainbowComet
        from adafruit_led_animation.animation.rainbowsparkle import RainbowSparkle
        from adafruit_led_animation.animation.solid import Solid
        from adafruit_led_animation.animation.sparkle import Sparkle
        from adafruit_led_animation.animation.sparklepulse import SparklePulse
        from adafruit_led_animation.color import BLACK, ORANGE, MAGENTA, TEAL
        from rainbowio import colorwheel

        self._Blink = Blink
        self._Chase = Chase
        self._ColorCycle = ColorCycle
        self._Comet = Comet
        self._Pulse = Pulse
        self._Rainbow = Rainbow
        self._RainbowChase = RainbowChase
        self._RainbowComet = RainbowComet
        self._RainbowSparkle = RainbowSparkle
        self._Solid = Solid
        self._Sparkle = Sparkle
        self._SparklePulse = SparklePulse
        self._BLACK = BLACK
        self._ORANGE = ORANGE
        self._MAGENTA = MAGENTA
        self._TEAL = TEAL
        self._colorwheel = colorwheel

    def default(self, params):
        return self._Chase(self.strip, speed=0.1, color=params[COLOR], size=3, spacing=6)

    def chase(self, params):
        return self._Chase(self.strip, speed=0.1, color=params[COLOR], size=3, spacing=6)

    def blink(self, params):
        return self._Blink(self.strip, speed=0.5, color=params[COLOR])

    def color_cycle(self, params):
        return self._ColorCycle(self.strip, 0.5, colors=[self._MAGENTA, self._ORANGE, self._TEAL])

    def comet(self, params):
        return self._Comet(self.strip, speed=0.1, color=params[COLOR])

    def pulse(self, params):
        return self._Pulse(self.strip, speed=0.1,  color=params[COLOR], period=1)

    def rainbow(self, params):
        return self._Rainbow(self.strip, speed=0.1, period=2)

    def rainbow_chase(self, params):
        return self._RainbowChase(self.strip, speed=0.1, size=5, spacing=3)

    def rainbow_comet(self, params):
        return self._RainbowComet(self.strip, speed=0.1, tail_length=30, bounce=True)

    def rainbow_sparkle(self, params):
        return self._RainbowSparkle(self.strip, speed=0.1, num_sparkles=15)

    def sparkle(self, params):
        return self._Sparkle(self.strip, speed=0.05, color=params[COLOR], num_sparkles=10)

    def sparkle_pulse(self, params):
        return self._SparklePulse(self.strip, speed=1, period=3, color=params[COLOR])

    def solid(self, params):
        return self._Solid(self.strip, color=params[COLOR])

    def fade_red(self, params):
        self.strip.fill((255, 0, 0))
        time.sleep(0.5)
        self.strip.fill((0, 255, 0))
        time.sleep(0.5)
        self.strip.fill((0, 0, 255))
        time.sleep(0.5)

    def random(self, params):
        # self.strip est un PixelSubset indexé de 0 à LED_COUNT-1 (zone corps).
        # L'ancien randint(513, 600) était une plage absolue du ruban global :
        # hors bornes du sous-ensemble → IndexError. On tire dans la zone locale.
        i = random.randint(0, self.LED_COUNT - 1)

        red = random.randint(0, 255)
        green = random.randint(0, 255)
        blue = random.randint(0, 255)
        logging.debug("random strip[" + str(i) + "] blue " + str(blue) + " red " + str(red) + " green " + str(green))
        self.strip[i] = (red, green, blue)
        #self.strip.show()

    def fill(self, color):
        logging.info("fill strip with " + str(color))
        self.strip.fill(color)

    def clean(self):
        self.strip.fill(self._BLACK)

    def color_chase(self, color, wait):
        for i in range(self.LED_COUNT):
            self.strip[i] = color
            time.sleep(wait)
            self.strip.show()
            # todo delete time.sleep
        time.sleep(0.5)

    def rainbow_cycle(self, wait):
        for j in range(255):
            for i in range(self.LED_COUNT):
                rc_index = (i * 256 // self.LED_COUNT) + j
                self.strip[i] = self._colorwheel(rc_index & 255)
            self.strip.show()
            # todo delete time.sleep
            time.sleep(wait)
