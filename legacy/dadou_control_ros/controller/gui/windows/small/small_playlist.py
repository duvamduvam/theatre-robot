import logging
import os
import tkinter as tk
from tkinter import BOTH, TOP, filedialog, LEFT, Y, RIGHT

import vlc
from playsound import playsound

from controller.buttons.button_config import Buttons
from controller.control_config import config, RESTART_APP, FONT_BUTTON
from controller.control_factory import ControlFactory
from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import AUDIO, STOP, AUDIOS_DIRECTORY, ANIMATION, DEFAULT
from controller.control_static import (
    PLAYLISTS, PLAYLIST_PLAY, BORDEAUX, PLAYLIST_PATH, FONT2, PLAYLIST_STOP, YELLOW, PLAYLIST, NEXT, CONTROL,
    CONFIG, PLAYLIST_LIST, CHOOSE,
)

MENU = [CONTROL, PLAYLIST, CONFIG]
PLAYLIST_CMD_INTERVAL = 1000


class SmallPlaylist(tk.Frame):
    def __init__(self, parent, mode, node, *args, **kwargs):

        self.node = node

        #self.playlist_type = DEFAULT

        self.parent = parent
        self.mode = mode
        self.devices = None
        self.sliders = None
        self.playlist_last_cmd = 0

        self.control_json = ControlFactory().control_json_manager
        self.input_key_play = config[PLAYLIST_PLAY]
        self.input_key_stop = config[PLAYLIST_STOP]
        self.input_key_restart_app = RESTART_APP

        self.current_pos = 0
        self.audio_process = None
        self.vlc_player = None

        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.pack(fill=BOTH, expand=True, side=TOP)
        self.main = tk.Frame(self, width=400, bg=config[BORDEAUX])
        self.main.pack(fill=BOTH, expand=True, side=RIGHT)
        self.files = tk.StringVar()
        self.files.set(FilesUtils.get_folder_files_name( config[PLAYLIST_PATH]))

        self.playlist_data = None

        self.playlist_var = tk.StringVar()

        self.playlist_listbox = tk.Listbox(self.main, listvariable=self.playlist_var, selectbackground=config[BORDEAUX], width=22, font=config[FONT2])
        self.playlist_listbox.bind("<<ListboxSelect>>", self.playlist_click)
        self.playlist_listbox.pack(fill=Y, expand=True, side=LEFT)

        button_width = 1
        #button_top_frame = tk.Frame(self.main)
        #button_top_frame.pack(side=TOP)
        self.send_button = tk.Button(self.main, bg=config[BORDEAUX], text='send', width=15, height=button_width, font=FONT_BUTTON, command=self.click_send)
        self.send_button.pack(side=TOP)
        #self.play_button = tk.Button(self.main, bg=config[BORDEAUX], text='play', width=5, height=button_width, font=config[FONT3], command_root=self.click_play)
        #self.play_button.pack(side=TOP)

        self.stop_button = tk.Button(self.main, bg=config[YELLOW], text='stop', width=15, height=button_width, font=FONT_BUTTON, command=self.click_stop)
        self.stop_button.pack(side=TOP)

        self.up_button = tk.Button(self.main, text='up', bg=config[BORDEAUX], width=15, height=button_width, font=FONT_BUTTON, command=self.on_entry_up)
        self.up_button.pack(side=TOP)

        self.down_button = tk.Button(self.main, bg=config[YELLOW], text='down', width=15, height=button_width, font=FONT_BUTTON, command=self.on_entry_down)
        self.down_button.pack(side=TOP)

        #self.playlists_button = tk.Button(self.main, bg=config[BORDEAUX], text='playlists', width=15, height=button_width, font=FONT_BUTTON, command=self.show_playlists)
        #self.playlists_button.pack(side=TOP)

        self.get_playlist_file(self.mode)
        self.exec_input()

    def on_entry_down(self):
        self.playlist_listbox.yview_scroll(1, "units")

    def on_entry_up(self):
        self.playlist_listbox.yview_scroll(-1, "units")

    def click_add(self):
        filepath = filedialog.askopenfilename(initialdir= config[AUDIOS_DIRECTORY],title="Open a Text File",
                                              filetypes=(("text    files", "*"), ("all files", "*.*")))
        self.files.append(filepath)

    def playlist_click(self, evt):
        if self.playlist_type == DEFAULT:
            if len(self.playlist_listbox.curselection()) > 0:
                self.current_pos = self.playlist_listbox.curselection()[0]
        elif self.playlist_type == CHOOSE:
            if len(self.playlist_listbox.curselection()) > 0:
                logging.info(self.playlist_listbox.curselection()[0])
                self.get_playlist_file(config[PLAYLIST_LIST][self.playlist_listbox.curselection()[0]])

    def change_playlist(self, evt):
        if len(self.playlist_listbox.curselection())>0:
            self.current_pos = self.playlist_listbox.curselection()[0]

    #def show_playlists(self):
    #    self.playlist_var.set(config[PLAYLIST_LIST])
    #    self.current_pos = 0
    #    self.playlist_listbox.select_set(self.current_pos)
    #    self.playlist_type = CHOOSE

    @staticmethod
    async def async_playsound(audio_path):
        playsound(audio_path)

    def click_play(self):
        #audio = SoundObject( '/..' + config[AUDIOS_DIRECTORY], self.playlist_listbox.get(self.playlist_listbox.curselection()[0]))
        #audio.play()
        playlist_num = self.playlist_listbox.curselection()[0]
        audio_params = list(self.playlist_data.values())[playlist_num]
        logging.info(audio_params)
        audio_path = '/..' + config[AUDIOS_DIRECTORY] + audio_params[AUDIO]
        if os.path.isfile(audio_path):

            if self.vlc_player:
                self.vlc_player.stop()
            self.vlc_player = vlc.MediaPlayer(audio_path)
            self.vlc_player.play()

            self.next()
        else:
            logging.error("{} not available".format(audio_path))

    def click_send(self):
        playlist_num = self.playlist_listbox.curselection()[0]
        audio_params = list(self.playlist_data.values())[playlist_num]
        logging.info("send playlist number {} value {}".format(playlist_num, audio_params))
        self.next()
        self.node.publish(audio_params)

    def click_stop(self):
        self.node.publish({AUDIO: STOP, ANIMATION: False})
        if self.vlc_player:
            self.vlc_player.stop()

    def click_audio(self, evt):
        w = evt.widget
        if len(w.curselection()):
            self.current_pos = int(w.curselection()[0])
            self.playlist_listbox.select_set(self.current_pos)

            self.playlist_listbox.selection_clear(0, 'end')
            self.playlist_listbox.select_set(self.current_pos)

    def next(self):
        if self.current_pos < len(self.playlist_data.keys()):
            self.playlist_listbox.selection_clear(0, 'end')
            self.current_pos = self.current_pos+1
            self.playlist_listbox.select_set(self.current_pos)
            if self.current_pos > 4:
                self.on_entry_down()

    def click_file(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            value = w.get(index)
            logging.info('You selected item %d: "%s"' % (index, value))

            self.playlist_listbox.delete(0, "end")
            self.playlist = value
            self.get_playlist_file(self.playlist)

    def get_playlist_file(self, file):
        if file == DEFAULT:
            file = config[PLAYLIST_LIST][0]
        self.playlist_type = DEFAULT
        items = []
        self.playlist_data = self.control_json.open_json(PLAYLISTS + '/' + file)
        for key in self.playlist_data:
            items.append(key)

        self.playlist_var.set(items)
        self.current_pos = 0
        self.playlist_listbox.select_set(self.current_pos)

    def playlist_instructions(self, cmd):
        if TimeUtils.is_time(self.playlist_last_cmd, PLAYLIST_CMD_INTERVAL):
            if cmd == NEXT:
                self.click_send()
            self.playlist_last_cmd = TimeUtils.current_milli_time()

    def exec_input(self):
        self.after(100, self.exec_input)

        serial_messages = self.parent.serial_inputs.get_key_msg()
        if serial_messages and len(serial_messages) > 0:
            for msg in serial_messages:
                #if GLOVE in msg[DEVICE]:
                value = Buttons.get(PLAYLIST, msg)  # BUTTONS_LAYOUT[self.mode][KEYS_MAPPING[msg[MSG]]][CMD]
                if not value:
                    return

                logging.info("input msg {}".format(value))
                key_list = list(value.keys())
                self.parent.show_popup("{} : {}".format(key_list[0], value[key_list[0]]))
                if key_list[0] == PLAYLIST:
                    self.playlist_instructions(value[key_list[0]])
                else:
                    self.node.publish(value)

