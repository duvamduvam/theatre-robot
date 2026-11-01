import logging
import time
import tkinter as tk

from controller.control_static import BORDEAUX, CONTROL, PLAYLIST, CONFIG, FONT2
from controller.buttons.button_config import CONTROL_CONFIG, PLAYLIST_CONFIG
from controller.control_config import config, FONT_BUTTON, SINGLE_GLOVE, DUAL_GLOVE_9DOF_LEFT, DUAL_GLOVE_9DOF_RIGHT, \
    DUAL_GLOVE_LEFT
from controller.gui.windows.small.small_config import SmallConfig
from controller.gui.windows.small.small_control import SmallControl
from controller.gui.windows.small.small_playlist import SmallPlaylist


class ModWindow(tk.Frame):
    def __init__(self, parent, node, *args, **kwargs):
        #tk.Frame.__init__(self, parent, *args, **kwargs)
        self.node = node
        tk.Frame.__init__(self, parent, *args, **kwargs)

        self.parent = parent
        buttons_names = []
        if isinstance(parent.main, SmallControl):
            self.window = CONTROL
            buttons_names = CONTROL_CONFIG
        elif isinstance(parent.main, SmallPlaylist):
            self.window = PLAYLIST
            buttons_names = PLAYLIST_CONFIG
        elif isinstance(parent.main, SmallConfig):
            self.window = CONFIG
            buttons_names = CONTROL_CONFIG

        self.buttons = self.create_buttons(buttons_names)
        time.sleep(0.1)
        parent.update_idletasks()

    def create_buttons(self, buttons_names):
        buttons = []
        for y in range(len(buttons_names)):
            buttons_row = []
            for x in range(len(buttons_names[y])):
                button = tk.Button(self, text=buttons_names[y][x], bg=config[BORDEAUX], width=10, height=2, font=config[FONT2],
                                   command=lambda mode=buttons_names[y][x]: self.click_button(mode))
                button.grid(column=x, row=y)
                buttons_row.append(button)
            buttons.append(buttons_row)
        return buttons

    def click_button(self, mode):
        self.parent.change_window(self.window, mode)
