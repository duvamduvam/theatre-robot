import logging
import tkinter as tk
from tkinter import BOTH, TOP

from dadou_utils_ros.misc import Misc

from controller.control_config import CYAN


class RemoteWindow(tk.Frame):
    def __init__(self, parent, *args, **kwargs):

        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.pack(fill=BOTH, expand=True, side=TOP)

        left_menu = tk.Frame(self, width=50, bg=CYAN)
        left_menu.pack(fill='y', ipadx=20, side='left')

        tk.Button(left_menu, text='streaming', command=self.start_streaming).grid(row=3, column=6, padx=10)

    def start_streaming(self):
        Misc.exec_shell('ffplay tcp://192.168.1.127:8888 -vf "setpts=N/30" -fflags nobuffer -flags low_delay -framedrop & ')
