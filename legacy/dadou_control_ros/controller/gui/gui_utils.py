import tkinter as tk
from tkinter import NW

import PIL
from PIL import Image, ImageTk
from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils_static import X, Y, BASE_PATH
from controller.control_static import CLEAN, PATHS, RANDOM_COLOR

from controller.control_config import config


class GuiUtils:

    @staticmethod
    def set_image(parent, x, y, image_type, image, zoom):
        folder = config[PATHS][image_type]
        image = PIL.Image.open(folder+'/'+image)
        tk_image = ImageTk.PhotoImage(image)
        tk_image = tk_image._PhotoImage__photo.zoom(zoom)
        parent.create_image(x, y, anchor=tk.NW, image=tk_image)
        return tk_image

    @staticmethod
    def copy_image(canvas, image, **kwargs):
        x, y = (0, 0)
        if X in kwargs and Y in kwargs:
            x = kwargs[X]
            y = kwargs[Y]
        if RANDOM_COLOR in kwargs:
            canvas.configure(bg=Misc.random_color())
        if CLEAN in kwargs.keys():
            canvas.delete("all")
        canvas.create_image(x, y, anchor=NW, image=image)

    @staticmethod
    def set_text(parent, x, y, text):
        return parent.create_text(x+5, y+120, text=text, angle=90)

