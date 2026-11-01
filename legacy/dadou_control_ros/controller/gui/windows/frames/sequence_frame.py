import logging
import tkinter as tk
from tkinter import BOTH, TOP

from controller.control_factory import ControlFactory
from controller.gui.windows.frames.abstract.rectangle_text import RectangleText2
from controller.gui.windows.frames.music_frame import MusicFrame
from controller.gui.windows.frames.widgets.navigation_widget import NavigationWidget
from controller.gui.windows.frames.neck_frame import NeckFrame
from controller.gui.windows.frames.wheels_frame import WheelsFrame

from controller.gui.windows.frames.widgets.sequences_manager_widget import SequencesManagerWidget


class SequenceFrame(tk.Frame):

    current_position = 0

    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, bg='grey', *args, **kwargs)
        self.pack(fill=BOTH, expand=True, side=TOP)

        self.left_menu = tk.Frame(self, bg='blue', width=100)
        self.left_menu.pack(fill='y', side='left')

        music_frame = MusicFrame(self, 'red')

        NavigationWidget(self.left_menu, width=100)
        sequence_widget = SequencesManagerWidget(self, self.left_menu, music_frame)

        expressions = ControlFactory().control_json_manager.get_expressions_names()
        self.faces_frame = RectangleText2(self, 'face', 'green', expressions)
        lights = list(ControlFactory().control_json_manager.get_lights().keys())
        self.lights_frame = RectangleText2(self, 'lights', 'yellow', lights)
        self.neck_frame = NeckFrame(self, 'orange')
        self.wheels_frame = WheelsFrame(self, 'violet')

        sequence_widget.load_first_sequence()

    def open_popup(self, parent):
        top = tk.Toplevel(parent)
        top.geometry("500x250")
        top.title("Child Window")
        tk.Label(top, text="Hello World!", font=('Mistral 18 bold')).place(x=150, y=80)

