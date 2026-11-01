import logging
import tkinter as tk
from tkinter import TOP

from controller.control_config import config

from controller.gui.windows.frames.widgets.time_line_bar import TimeLineBar
from controller.control_static import DATAS, FONT2


class AbstractSequenceFrame(tk.Frame):
    time_line_bar_pos = 0
    def __init__(self, parent, name, color, **kwargs):
        tk.Frame.__init__(self, parent)

        logging.info(name)

        self.pack(fill='x', side=TOP)
        self.update()

        delete_frame = tk.Frame(self, width=20, bg='black')
        delete_frame.pack(fill='y', side='left')

        self.canvas = tk.Canvas(self, height=150, bg=color)
        delete_frame.bind('<Button-3>', self.delete_sequence)
        self.set_frame_name(name)
        self.canvas.pack(fill='x')

        self.create_timeline()

    def create_timeline(self):
        TimeLineBar(self.canvas)

    def set_frame_name(self, name):
        self.canvas.create_text(100, 20, text=name, fill="black", font=config[FONT2])

    def listen_time_frame(self):
        print(AbstractSequenceFrame.time_line_bar_pos)

    def delete_sequence(self, key):
        logging.info('delete section')
        self.forget()
        self.destroy()

    def load(self, data):
        pass
