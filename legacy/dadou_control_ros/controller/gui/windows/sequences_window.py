import logging
import tkinter as tk
from tkinter import BOTH, TOP, font

from dadou_utils_ros.utils_static import FACE, LIGHTS, WHEELS, NECK, ORANGE, NAME, JSON_EXPRESSIONS, JSON_LIGHTS
from controller.control_static import CYAN, BORDEAUX, PURPLE, YELLOW, FONT1, FONT2

from controller.control_config import config
from controller.control_factory import ControlFactory
from controller.gui.windows.frames.abstract.rectangle_text import RectangleText
from controller.gui.windows.frames.music_frame import MusicFrame
from controller.gui.windows.frames.widgets.navigation_widget import NavigationWidget
from controller.gui.windows.frames.neck_frame import NeckFrame
from controller.gui.windows.frames.wheels_frame import WheelsFrame

from controller.gui.windows.frames.widgets.sequences_widget import SequencesManagerWidget


class SequencesWindow(tk.Frame):

    current_position = 0

    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, bg=config[CYAN], *args, **kwargs)
        #self.pack(fill=BOTH, expand=True, side=TOP)

        self.left_menu = tk.Frame(self, bg=config[CYAN], width=100)
        self.left_menu.pack(fill='y', side='left')

        music_frame = MusicFrame(self, config[BORDEAUX])

        NavigationWidget(self.left_menu, width=100)
        SequencesManagerWidget(self, self.left_menu, music_frame)

        self.new_section = self.new_frame()

        self.expressions = ControlFactory().control_json_manager.get_attributs_list(config[JSON_EXPRESSIONS], NAME)
        self.lights = ControlFactory().control_json_manager.get_keys_list(config[JSON_LIGHTS])


    def new_frame(self):
        new_frame = tk.Frame(self.left_menu, bg=config[CYAN])
        new_frame.pack(fill='x', side=TOP)
        helv36 = font.Font(family='Helvetica', size=36, weight=font.BOLD)
        tk.Button(new_frame, text='new section', bg=PURPLE, font=config[FONT1], command=lambda: self.choice_popup())\
            .pack(ipadx=10, ipady=30, fill='x', expand=True, side='left')
        return new_frame

    def choice_popup(self):
        popup = tk.Toplevel()
        popup.wm_title("New section")
        popup.geometry("500x200")

        tk.Button(popup, text=FACE, bg=config[PURPLE], command=lambda: self.add_section(FACE)).pack(fill='x', side=TOP)
        tk.Button(popup, text=LIGHTS, bg=config[PURPLE], command=lambda: self.add_section(LIGHTS)).pack(fill='x', side=TOP)
        tk.Button(popup, text=NECK, bg=config[PURPLE], command=lambda: self.add_section(NECK)).pack(fill='x', side=TOP)
        tk.Button(popup, text=WHEELS, bg=config[PURPLE], command=lambda: self.add_section(WHEELS)).pack(fill='x', side=TOP)

    def add_section(self, section):
        logging.info('new section {}'.format(section))

        if section == FACE:
            self.load_face()
        elif section == LIGHTS:
            self.load_lights()
        elif section == WHEELS:
            self.load_wheels()
        elif section == NECK:
            self.load_neck()

    def load_face(self, datas=None):
        RectangleText(self, FACE, config[CYAN], self.expressions, datas=datas)

    def load_lights(self, datas=None):
        RectangleText(self, LIGHTS, config[CYAN], self.lights, datas=datas)

    def load_neck(self, datas=None):
        NeckFrame(self, config[ORANGE], datas=datas)

    def load_wheels(self, datas=None):
        WheelsFrame(self, config[PURPLE], datas=datas)
