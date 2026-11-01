import tkinter as tk
from tkinter import TOP, BOTH, ttk

from dadou_utils_ros.utils_static import ORANGE
from controller.control_static import BORDEAUX, YELLOW, CYAN, FONT1, PURPLE, FONT3

from controller.control_config import config
from controller.control_factory import ControlFactory
from controller.gui.windows.expression_window import ExpressionWindow
from controller.gui.windows.lights_window import LightsWindow
from controller.gui.windows.remote_window import RemoteWindow
from controller.gui.windows.sequences_window import SequencesWindow
from controller.gui.windows.config_window import ConfigWindow

#https://www.hashbangcode.com/article/using-events-tkinter-canvas-elements-python
from controller.gui.windows.playlist_window import PlaylistWindow
from controller.gui.windows.keyboard_window import KeyboardWindow


class NormalGui(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        self.option_add("*Font", config[FONT3])

        style = ttk.Style(self)
        # set ttk theme to "clam" which support the fieldbackground option
        style.theme_use("clam")

        tk.Grid.rowconfigure(self, 0, weight=1)
        tk.Grid.columnconfigure(self, 0, weight=1)

        self.EXIT = 'EXIT'
        self.EXPRESSION_FRAME = 'EXPRESSION'
        self.KEYBOARD_FRAME = 'KEYBOARD'
        self.PLAYLIST_FRAME = 'PLAYLIST'
        self.SEQUENCE_FRAME = 'SEQUENCE'
        self.LIGHTS_FRAME = 'LIGHTS'
        self.REMOTE_FRAME = 'REMOTE'
        self.CONFIG_FRAME = 'CONFIG'
        self.SPEECH_FRAME = 'SPEECH'

        #font1 = tkfont.Font(family='Helvetica', size=18, weight="bold", slant="italic")

        self.geometry("1600x1024")
        self.attributes("-fullscreen", True)

        menu = tk.Frame(self, bg=config[ORANGE])
        menu.pack(fill='x', side=TOP)

        screen_width = self.winfo_screenwidth()

        tk.Button(menu, text='Config', bg=config[PURPLE], font=config[FONT1], command=lambda: self.show_frame(self.EXIT)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
        tk.Button(menu, text='Keyboard', bg=config[BORDEAUX], font=config[FONT1], command=lambda: self.show_frame(self.KEYBOARD_FRAME)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
        tk.Button(menu, text='Playlist', bg=config[YELLOW], font=config[FONT1], command=lambda: self.show_frame(self.PLAYLIST_FRAME)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
        """if screen_width > 1000:
            tk.Button(menu, text='Sequence', bg=config[ORANGE], font=config[FONT1], command_root=lambda: self.show_frame(self.SEQUENCE_FRAME)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
            tk.Button(menu, text='Expression', bg=config[CYAN], font=config[FONT1], command_root=lambda: self.show_frame(self.EXPRESSION_FRAME)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
            tk.Button(menu, text='Lights', bg=config[PURPLE], font=config[FONT1], command_root=lambda: self.show_frame(self.LIGHTS_FRAME)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
            tk.Button(menu, text='Remote', bg=config[ORANGE], font=config[FONT1], command_root=lambda: self.show_frame(self.REMOTE_FRAME)).pack(ipadx=5, ipady=20, fill='x', expand=True, side='left')
        """
        #self.main = tk.Frame(self, bg='yellow')


        self.main = KeyboardWindow(self)
        self.main.pack(fill=BOTH, expand=True, side=TOP)
        #self.scheduler()


    def show_frame(self, frame_name):

        try:
            for child in self.main.winfo_children():
                child.destroy()
        except Exception as e:
            pass
        self.main.forget()
        self.main.destroy()

        if frame_name == self.KEYBOARD_FRAME:
            self.main = KeyboardWindow(self)
        elif frame_name == self.SEQUENCE_FRAME:
            self.main = SequencesWindow(self)
        elif frame_name == self.PLAYLIST_FRAME:
            self.main = PlaylistWindow(self)
        elif frame_name == self.EXPRESSION_FRAME:
            self.main = ExpressionWindow(self)
        elif frame_name == self.LIGHTS_FRAME:
            self.main = LightsWindow(self)
        elif frame_name == self.REMOTE_FRAME:
            self.main = RemoteWindow(self)
        elif frame_name == self.CONFIG_FRAME:
            self.main = ConfigWindow(self)
        elif frame_name == self.EXIT:
            self.main = ConfigWindow(self)

        self.main.pack(fill=BOTH, expand=True, side=TOP)

    def scheduler(self):
        #self.after(5000, self.scheduler)
        ControlFactory().devices_manager.update_devices()
