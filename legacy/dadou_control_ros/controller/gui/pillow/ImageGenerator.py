import logging
import random
from PIL import Image, ImageOps, ImageDraw, ImageFont
from dadou_utils_ros.utils_static import TYPE, NAME, SPEED, RANDOM, NECK, BRIGHTNESS, DEFAULT, LIGHTS
from controller.control_static import (
    X1, Y1, X2, Y2, BUTTON, RESTART, SLIDE, COORD, CONFIG, WINDOW, CELL, OUT_CELL, IN_CELL, KEYBOARD, PLAYLIST,
    START, CMD,
)

CONFIG_ELEMENTS = [{NAME: RESTART, TYPE: BUTTON},
                   {NAME: SPEED, TYPE: SLIDE, DEFAULT: 30},
                   {NAME: RANDOM, TYPE: BUTTON},
                   {NAME: LIGHTS, TYPE: SLIDE, DEFAULT: 0.3},
                   {NAME: NECK, TYPE: SLIDE, DEFAULT: 50},
                   {NAME: "truc", TYPE: BUTTON}]

CONFIG_BUTTONS = {11: {NAME: "test1"},
                  12: {NAME: "test2"},
                  13: {NAME: "test3"},
                  14: {NAME: "test4"},
                  15: {NAME: "test5"},
                  16: {NAME: "test6"},
                  17: {NAME: "test7"},
                  18: {NAME: "test8"},
                  19: {NAME: "test9"},
                  20: {NAME: "test10"},
                  21: {NAME: "test11"},
                  22: {NAME: "test12"}}

BUTTON_DEFAULT_COLOR = "blue"
SLIDER_DEFAULT_COLOR = "yellow"

MODES = [KEYBOARD, CONFIG, PLAYLIST]

class ImageGenerator:
    def __init__(self, width=320, height=240, rows=3, cols=2):
        self.width = width
        self.height = height
        self.rows = rows
        self.cols = cols
        self.last_key = ""
        self.font_size = 30  # Taille de police augmentée

        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        self.font = ImageFont.truetype(font_path, self.font_size)
        self.font_big = ImageFont.truetype(font_path, 45)

        self.mode = 0
        self.selection = WINDOW

        self.pos = 0
        self.has_change = True
        self.image = self.generate()

    def set_last_key(self, key):
        self.last_key = key
        self.has_change = True

    def generate(self):
        logging.info("generate mode {} {}".format(self.mode, MODES[self.mode]))
        if MODES[self.mode] == CONFIG:
            return self.generate_config()
        elif MODES[self.mode] == KEYBOARD:
            return self.generate_keyboard()
        elif MODES[self.mode] == PLAYLIST:
            return self.generate_playlist()

    def generate_keyboard(self):
        image = Image.new("RGB", (self.width, self.height), "red")
        draw = ImageDraw.Draw(image)

        #header
        draw.rectangle([0, 0, self.width, 40], fill="yellow")
        draw.rectangle([self.width-40, 0, self.width, self.height], fill="yellow")

        if self.last_key:
            text_position = (50, 110)
            draw.text(xy=text_position, text=str(self.get_key()), fill="black", font=self.font_big)

        #self.node.publish(self.get_key(CMD))

        self.create_border(draw)
        return image

    def get_key(self):
        #if isinstance(self.last_key, dict) and key in self.last_key:
        #    return self.last_key[key]
        #else:
        if self.last_key in CONFIG_BUTTONS:
            return CONFIG_BUTTONS[self.last_key][NAME]
        else:
            return self.last_key


    def generate_playlist(self):
        image = Image.new("RGB", (self.width, self.height), "white")
        draw = ImageDraw.Draw(image)

        #side
        draw.rectangle([self.width-40, 0, self.width, self.height], fill="yellow")

        self.create_border(draw)
        return image

    def generate_config(self):
        image = Image.new("RGB", (self.width, self.height), "blue")
        draw = ImageDraw.Draw(image)

        largeur_cellule = self.width // self.cols
        hauteur_cellule = self.height // self.rows

        count = 0

        for i in range(self.rows):
            for j in range(self.cols):

                coord = {}
                coord[X1] = j * largeur_cellule
                coord[Y1] = i * hauteur_cellule
                coord[X2] = coord[X1] + largeur_cellule
                coord[Y2] = coord[Y1] + hauteur_cellule

                CONFIG_ELEMENTS[count][COORD] = coord

                self.create_rectangle(draw, coord, CONFIG_ELEMENTS[count])

                count += 1

        self.create_border(draw, CONFIG_ELEMENTS[self.pos][COORD])

        return image

    def create_rectangle(self, draw, coord, element, color=None, border=None):

        if element[TYPE] == BUTTON:
            color = BUTTON_DEFAULT_COLOR
        if element[TYPE] == SLIDE:
            color = SLIDER_DEFAULT_COLOR

        draw.rectangle([coord[X1], coord[Y1], coord[X2], coord[Y2]], fill=color)

        bbox = self.font.getbbox(element[NAME])
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_position = (coord[X1] + (coord[X2] - coord[X1] - text_width) // 2,
                          coord[Y1] + (coord[Y2] - coord[Y1] - text_height) // 2)
        draw.text(text_position, element[NAME], fill="black", font=self.font)

    def create_border(self, draw, coord=None, color="black", width=6):
        if self.selection == OUT_CELL:
            draw.rectangle([coord[X1], coord[Y1], coord[X2], coord[Y2]], outline=color, width=width)
        elif self.selection == IN_CELL:
            draw.rectangle([coord[X1], coord[Y1], coord[X2], coord[Y2]], outline="green", width=width)
        elif self.selection == WINDOW:
            draw.rectangle([0, 0, self.width, self.height], outline="red", width=width)


    def navigation(self, key):
        if self.selection == OUT_CELL:
            if key == 6 and self.pos < 5:
                self.pos += 1
            elif key == 4 and self.pos > 0:
                self.pos -= 1
            elif key == 8 and self.pos >= 2:
                self.pos -= 2
            elif key == 2 and self.pos <= 3:
                self.pos += 2
            elif key == 9:
                self.selection = IN_CELL
            elif key == 7:
                self.selection = WINDOW
        elif self.selection == IN_CELL:
            if key == 7:
                self.selection = OUT_CELL
        elif self.selection == WINDOW:
            if key == 6 and self.mode < len(MODES) - 1:
                self.mode += 1
            elif key == 4 and self.mode >= 1:
                self.mode -= 1
            if key == 9:
                self.selection = OUT_CELL

    def process(self):
        if self.last_key:
            logging.info(" key {}".format(self.last_key))
            if isinstance(self.last_key, int): # and self.last_key.isnumeric():
                self.navigation(self.last_key)

        if self.has_change:
            self.image = self.generate()
            self.image = ImageOps.mirror(self.image)
            self.has_change = False
            self.last_key = None
            return self.image

