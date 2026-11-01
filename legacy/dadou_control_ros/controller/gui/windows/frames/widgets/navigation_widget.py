import logging
from tkinter import TOP

import time
import tkinter as tk
from enum import Enum

from controller.control_config import CYAN, YELLOW
from controller.audio.audio_navigation import State
from controller.control_factory import ControlFactory


class NavigationWidget(tk.Frame):

    sequence_management = ControlFactory().sequence_management

    def __init__(self, parent, *args, **kwargs):
        self.parent = parent

        tk.Frame.__init__(self, parent, bg=CYAN, *args, **kwargs)

        tk.Button(self, text='play', bg=YELLOW, command=self.play).grid(row=0, column=0, padx=10)
        tk.Button(self, text='pause', bg=YELLOW, command=self.pause).grid(row=0, column=1, padx=10)
        tk.Button(self, text='stop', bg=YELLOW, command=self.stop).grid(row=0, column=2, padx=10)

        tk.Label(self, text='current time').grid(row=1, column=0, columnspan=2)
        self.timer_txt = tk.StringVar()
        self.time_label = tk.Label(self, textvariable=self.timer_txt)
        self.time_label.grid(row=1, column=3, columnspan=2)

        self.pack(fill='x', side=TOP)

        self.update_timer()

    def play(self):
        self.sequence_management.audio_segment.play()

    def stop(self):
        self.sequence_management.audio_segment.stop()

    def pause(self):
        self.sequence_management.audio_segment.pause()

    def update_timer(self):
        self.after(200, self.update_timer)
        if hasattr(ControlFactory().sequence_management, 'audio_segment') and ControlFactory().sequence_management.audio_segment is not None:
            state = ControlFactory().sequence_management.audio_segment.current_state
            #logging.info('state : {} equals {} {}'.format(str(state.value), str(state.value == State.PLAY.value), str(State.PLAY.value)))
            if state.value == State.PLAY.value:
                display_time = self.sequence_management.audio_segment.display_time()
                self.timer_txt.set(display_time)


