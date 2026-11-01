import logging
import os
import sys
from tkinter import BOTH, TOP, X, HORIZONTAL, LEFT, RIGHT

import tkinter as tk

from dadou_utils_ros.utils_static import ORANGE
from controller.control_static import BORDEAUX, FONT1

from controller.control_config import config


class ConfigWindow(tk.Frame):

    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        #self.main = tk.Frame.__init__(self, parent, bg=PURPLE, *args, **kwargs)
        self.pack(fill=BOTH, expand=True, side=TOP)
        self.exit_button = tk.Button(self, text='Exit', bg=config[BORDEAUX], font=config[FONT1],
                  command=exit)
        self.exit_button.grid(row=0, column=0)
        self.restart_button = tk.Button(self, text='Restart', bg=config[ORANGE], font=config[FONT1],
                  command=self.restart)
        self.restart_button.grid(row=0, column=1)


        #volume_frame = tk.Frame(self)
        #volume_label = tk.Label(volume_frame, text="Volume")
        #volume_label.pack(fill=X, side=LEFT)
        #self.volume_scale = tk.Scale(volume_frame, from_=0, to=100, length=500, resolution=1, command_root=self.update_volume(), orient=HORIZONTAL)
        #self.volume_scale.pack(fill=X, side=LEFT)
        #volume_frame.pack(fill=X, side=TOP)

    #def update_volume(self):
    #    logging.info("volume changed {}".format(self.volume_scale.get()))

    def restart(self):
        os.execv(sys.executable, ['python'] + sys.argv)
