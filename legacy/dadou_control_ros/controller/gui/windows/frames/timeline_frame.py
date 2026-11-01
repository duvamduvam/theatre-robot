
import logging
import tkinter as tk
from enum import Enum
from tkinter import TOP

from dadou_utils_ros.utils.time_utils import TimeUtils
from controller.control_static import PURPLE, BORDEAUX

from controller.control_config import config


class TimeLineFrame(tk.Frame):
    duration = 0
    x_pos = 0

    def __init__(self, parent):
        tk.Frame.__init__(self, parent, bg=config[PURPLE])
        #self.config(height=50)
        self.pack(fill='x', side=TOP)

        self.canvas = tk.Canvas(self, height=50, bg=config[BORDEAUX])
        self.canvas.pack(fill='x')

        self.bar = self.create_line(0)

        self.canvas.update()
        self.width = self.canvas.winfo_width()
        self.start_time = 0
        self.progress = 0
        self.state = State.STOP

    def play(self):
        logging.debug("play sequences")
        self.start_time = TimeUtils.current_milli_time()
        if self.state == State.PAUSED:
            pos = self.progress * self.duration
            self.start_time = self.start_time - pos

        self.state = State.PLAYING
        self.canvas.after(1, self.process_play)

    def stop(self):
        logging.debug("stop sequences")
        self.state = State.STOP
        self.canvas.delete(self.bar)
        self.bar = self.canvas.create_line(0, 0, 0, 50, width=10)
        self.progress = 0

    def pause(self):
        logging.debug("pause sequences")
        if self.progress != 0:
            self.state = State.PAUSED
        else:
            self.state = State.STOP

    def process_play(self):

        if self.state == State.PLAYING:
            self.canvas.after(50, self.process_play)

            time = TimeUtils.current_milli_time()
            self.progress = (time - self.start_time)/self.duration
            if self.progress >= 1:
                self.start_time = TimeUtils.current_milli_time()
            #progress = f'{(time - self.start_time)/(self.duration*1000):.2g}'
            #progress = "{%0.4}".format((time - self.start_time)/(self.duration*1000))
            #progress = "{:.2f}".format((time - self.start_time)/(self.duration*1000))
            TimeLineFrame.x_pos = int(self.width * self.progress)
            self.canvas.delete(self.bar)
            self.bar = self.create_line(TimeLineFrame.x_pos)
            #logging.debug("{} play bar position {} progress {}".format(time, self.x_pos, self.progress))

    def create_line(self, x):
        bar = self.canvas.create_line(x, 0, x, 50, width=10)
        self.canvas.bind('<B1-Motion>', self.drag_bar)
        return bar

    def drag_bar(self, e):
        self.canvas.delete(self.bar)
        self.bar = self.create_line(e.x)
        self.progress = e.x / self.canvas.winfo_width()
        self.state = State.PAUSED


class State(Enum):
    PLAYING = 1
    STOP = 2
    PAUSED = 3



