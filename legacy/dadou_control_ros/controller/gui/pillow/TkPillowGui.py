import logging
import os
import sys
import time
import spidev as SPI

import board
from controller.lib.LCD_2inch4 import LCD_2inch4
from controller.circuit_py.glove_keys import GloveKeys
from controller.circuit_py.vibrator import Vibrator

import PIL
from PIL import ImageTk

if 'unittest' in sys.modules:
    import tkinter as tk

from controller.gui.pillow.ImageGenerator import ImageGenerator
#from controller.gui.pillow.KeyboardListener import KeyboardListener

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240


class PillowGuiApp:
    def __init__(self, node):
        self.node = node
        self.image_generator = ImageGenerator()

        self.last_image = None
        self.new_key = False

        #if os.environ.get('DISPLAY'):
        #
        #    self.root = tk.Tk()
        #    self.init_tkinter()
        #    self.process_test()
        #    self.root.mainloop()

        #else:
        #import board
        #from controller.lib.LCD_2inch4 import LCD_2inch4
        #from controller.circuit_py.glove_keys import GloveKeys
        #from controller.circuit_py.vibrator import Vibrator

        #print(dir(board))
        #self.glove_keys = GloveKeys((("x", "w", "v"), ("r", "q", "p"), ("o", "n", "m"), ("u", "t", "s")),
        self.glove_keys = GloveKeys(((11, 12, 13), (14, 15, 16), (17, 18, 19), (20, 21, 22)),
                    (board.D16, board.D20, board.D21),
                     (board.D6, board.D13, board.D19, board.D26))
        self.control_keys = GloveKeys(((2, 4, 6), (9, 8, 7)),
                    (board.D17, board.D27, board.D22),
                    (board.D15, board.D18))

        self.vibrator = Vibrator(board.D14)
        self.oled = self.init_oled()
        self.process_oled()

    def get_key(self):
        key = self.glove_keys.check()
        if not key:
            key = self.control_keys.check()
        return key

    def init_tkinter(self):
        self.canvas = tk.Canvas(self.root, width=SCREEN_WIDTH, height=SCREEN_HEIGHT)
        self.canvas.pack()

        #self.keyboard_listener = KeyboardListener(self.image_generator)

    def init_oled(self):
        RST = 24
        DC = 25
        BL = 9
        bus = 0
        device = 0
        oled = LCD_2inch4(spi=SPI.SpiDev(bus, device), spi_freq=10000000, rst=RST, dc=DC, bl=BL)

        oled.Init()
        oled.clear()
        oled.bl_DutyCycle(100)
        return oled

    def process(self):
        #if os.environ.get('DISPLAY'):
        #    self.process_test()
        #else:
        self.process_oled()

    def update(self):
        self.process()
        #pass


    def process_test(self):
        try:
            self.new_key = False
            key = self.keyboard_listener.get_key()
            if key:
                logging.info("new key: %s" % key)
                self.image_generator.set_last_key(key)
                self.new_key = True

            if self.new_key or not self.last_image:
                self.last_image = self.image_generator.process()
                self.last_image.save("/home/dadou/tmp/pil-image.jpg", "JPEG")
                photo = ImageTk.PhotoImage(self.last_image)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                self.canvas.image = photo
            self.root.after(100, self.process_test)
        except Exception as e:
            logging.error(e, exc_info=True)

    def process_oled(self):
        try:
            key = self.get_key()
            if key:
                self.vibrator.click()
                self.image_generator.set_last_key(key[0])

            image = self.image_generator.process()
            self.vibrator.process()
            if image:
                self.oled.ShowImage(image)

        except Exception as e:
            logging.error(e, exc_info=True)


if __name__ == "__main__":

    #vibrator
    #keyboard button boitier
    #battery indicator
    #9 dof

    app = PillowGuiApp(None)
    while True:
        app.process()
        time.sleep(0.1)
