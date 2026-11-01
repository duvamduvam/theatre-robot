import logging
from tkinter import LEFT

from PIL import ImageTk, Image
import tkinter as tk

from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import BASE_PATH
from controller.control_static import PATHS, ICONS, INPUT_KEY, SLIDERS, GLOVE_LEFT
from controller.control_config import config
from controller.control_factory import ControlFactory

GLOVE_FEEDBACK_TIMEOUT = 3000


class IconsWidget:
    def __init__(self, parent, menu, serial_inputs):

        self.parent = parent
        self.menu = menu
        self.serial_inputs = serial_inputs
        self.glove_feedback_time = 0


        ##### feedback icons
        icon_pos = 2
        if self.serial_inputs.device_connected(GLOVE_LEFT):
            self.hand_label, self.hand_icon, self.hand_image = self.create_label_icon("hand.png")
        else:
            logging.info("{} not connected".format(GLOVE_LEFT))

        if self.serial_inputs.device_connected("sliders"):
            self.slider_label, self.slider_icon, self.hand_image = self.create_label_icon("sliders.png")

        if ControlFactory().ws_device_connected('sceno'):
            self.sceno_label, self.sceno_icon, self.robot_image = self.create_label_icon("music.png")

        if ControlFactory().ws_device_connected('harddrive'):
            self.helmet_label, self.helmet_icon, self.helmet_image = self.create_label_icon("helmet.png")

        if ControlFactory().ws_device_connected('controller'):
            self.robot_label, self.robot_icon, self.robot_image = self.create_label_icon("controller.png")

        if Misc.wifi_connected():
            if Misc.internet_connected():
                self.wifi_label, self.wifi_icon, self.wifi_image = self.create_label_icon("wifi-green.png")
            else:
                self.wifi_label, self.wifi_icon, self.wifi_image = self.create_label_icon("wifi-red.png")

    def create_label_icon(self, icon):
        image = Image.open(config[PATHS][ICONS]+icon)
        image = image.resize((35, 40))  # Redimensionner l'image à la taille souhaitée
        icon = ImageTk.PhotoImage(image)

        # Créer un widget Label pour afficher l'icône
        label = tk.Label(self.menu, image=icon)
        label.pack(side=LEFT)

        return label, icon, label

    def glove_feedback(self):
        self.hand_label.config(bg="red")
        self.glove_feedback_time = TimeUtils.current_milli_time()
        self.glove_feedback_timeout()

    def glove_feedback_timeout(self):
        if TimeUtils.is_time(self.glove_feedback_time, GLOVE_FEEDBACK_TIMEOUT):
            self.hand_label.config(bg="white")
        else:
            self.hand_label.config(bg="red")
            self.parent.after(100, self.glove_feedback_timeout)

