import asyncio
import logging
import os
import subprocess
import threading
import tkinter as tk
from tkinter import BOTH, TOP, filedialog, LEFT, X, Y, RIGHT, END
from playsound import playsound
import vlc

from dadou_utils_ros.com.input_messages_list import InputMessagesList
from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.utils_static import NAME, AUDIO, STOP, KEY, BASE_PATH, AUDIOS_DIRECTORY, ANIMATION, WHEELS
from controller.control_static import (
    PLAYLISTS, INPUT_KEY, PLAYLIST_PLAY, BORDEAUX, PLAYLIST_PATH, CYAN, FONT1, FONT2, PLAYLIST_STOP, SLIDERS,
)
from dadou_utils_ros.audios.sound_object import SoundObject

from controller.control_factory import ControlFactory
from controller.control_config import config, RESTART_APP


class PlaylistWindow(tk.Frame):
    def __init__(self, parent, *args, **kwargs):

        self.input_keys = None
        self.sliders = None

        self.control_json = ControlFactory().control_json_manager
        self.deviceManager = ControlFactory().devices_manager
        self.input_key_play = config[PLAYLIST_PLAY]
        self.input_key_stop = config[PLAYLIST_STOP]
        self.input_key_restart_app = RESTART_APP

        self.current_pos = 0
        self.audio_process = None
        self.vlc_player = None

        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.pack(fill=BOTH, expand=True, side=TOP)
        self.main = tk.Frame(self, width=600, bg=config[BORDEAUX])
        self.main.pack(fill=BOTH, expand=True, side=RIGHT)

        left_menu = tk.Frame(self, width=50, bg=config[CYAN])
        left_menu.pack(fill=BOTH, ipadx=20, side=LEFT)

        self.files = tk.StringVar()
        self.files.set(FilesUtils.get_folder_files_name( config[PLAYLIST_PATH]))
        self.files_listbox = tk.Listbox(left_menu, listvariable=self.files, height=20, font=config[FONT2])
        self.files_listbox.bind('<<ListboxSelect>>', self.click_file)
        self.files_listbox.pack(fill=X, ipadx=20, side=TOP)

        self.playlist_data = None

        self.playlist_var = tk.StringVar()
        self.files.set(FilesUtils.get_folder_files_name( config[PLAYLIST_PATH]))
        self.playlist_listbox = tk.Listbox(self.main, listvariable=self.playlist_var, selectbackground=config[BORDEAUX], height=16, width=40, font=config[FONT2])
        self.playlist_listbox.bind('<<ListboxSelect>>', self.click_audio)
        self.playlist_listbox.grid(row=0, column=0, rowspan=7, columnspan=3, sticky='new')

        #scrollbar = tk.Scrollbar(self.main)

        # Adding Scrollbar to the right
        # side of root window
        #scrollbar.grid(row=1, column=1, rowspan=5, sticky='new')

        # Insert elements into the listbox
        #for values in range(100):
        #    self.playlist_listbox.insert(END, values)

        # Attaching Listbox to Scrollbar
        # Since we need to have a vertical
        # scroll we use yscrollcommand
        #self.playlist_listbox.config(yscrollcommand=scrollbar.set)

        # setting scrollbar command_root parameter
        # to listbox.yview method its yview because
        # we need to have a vertical view
        #œscrollbar.config(command_root=listbox.yview)

        self.add_button = tk.Button(self.main, text='add', width=15, height=2, font=config[FONT1], command=self.click_add)
        self.add_button.grid(row=0, column=4, sticky='new')

        self.play_button = tk.Button(self.main, text='play', width=15, height=2, font=config[FONT1], command=self.click_play)
        self.play_button.grid(row=1, column=4, sticky='new')

        self.send_button = tk.Button(self.main, text='send', width=15, height=2, font=config[FONT1], command=self.click_send)
        self.send_button.grid(row=2, column=4, sticky='new')

        self.stop_button = tk.Button(self.main, text='stop', width=15, height=2, font=config[FONT1], command=self.click_stop)
        self.stop_button.grid(row=3, column=4, sticky='new')

        self.up_button = tk.Button(self.main, text='up', width=15, height=2, font=config[FONT1], command=self.OnEntryUp)
        self.up_button.grid(row=4, column=4, sticky='new')

        self.down_button = tk.Button(self.main, text='down', width=15, height=2, font=config[FONT1], command=self.OnEntryDown)
        self.down_button.grid(row=5, column=4, sticky='new')

        self.check_devices()
        self.check_glove_input()
        self.check_sliders_input()

        self.last_input_time = 0

    def OnEntryDown(self):
        self.playlist_listbox.yview_scroll(1, "units")

    def OnEntryUp(self):
        self.playlist_listbox.yview_scroll(-1, "units")

    def click_add(self):
        filepath = filedialog.askopenfilename(initialdir= config[AUDIOS_DIRECTORY],title="Open a Text File",
                                              filetypes=(("text    files", "*"), ("all files", "*.*")))
        self.files.append(filepath)

    @staticmethod
    async def async_playsound(audio_path):
        playsound(audio_path)

    def click_play(self):
        #audio = SoundObject( '/..' + config[AUDIOS_DIRECTORY], self.playlist_listbox.get(self.playlist_listbox.curselection()[0]))
        #audio.play()
        playlist_num = self.playlist_listbox.curselection()[0]
        audio_params = list(self.playlist_data.values())[playlist_num]
        audio_path =  '/..' + config[AUDIOS_DIRECTORY] + audio_params[AUDIO]
        if os.path.isfile(audio_path):

            if self.vlc_player:
                self.vlc_player.stop()
            self.vlc_player = vlc.MediaPlayer(audio_path)
            self.vlc_player.play()

            #asyncio.run(PlaylistWindow.async_playsound(audio_path))
            #playsound(audio_path)
            #if self.audio_process:
            #    self.audio_process._Thread__stop()

            #multiprocessing.Process(target=playsound, args=("file.mp3",))
            #self.audio_process = threading.Thread(target=playsound, args=(audio_path,), daemon=False)
            #self.audio_process.start()

            """if self.audio_process:
                self.audio_process.terminate()
            self.audio_process = subprocess.Popen(['mpg123',  # The program to launch
                                  '-C',  # Commands can be sent
                                  '-q',  # Be quiet
                                  audio_path],
                                 stdin=subprocess.PIPE,  # Send commands here
                                 stdout=None,
                                 stderr=None)

            #playsound(audio_path)
            #self.audio_segment = SoundObject(audio_path)
            #self.audio_segment.play()"""
            self.next()
        else:
            logging.error("{} not available".format(audio_path))

    def click_send(self):
        playlist_num = self.playlist_listbox.curselection()[0]
        #audio_name = self.playlist_listbox.get(playlist_num)
        audio_params = list(self.playlist_data.values())[playlist_num]
        #audio_params[AUDIO] = audio_name
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
            #index = int(w.curselection()[0])
            #value = w.get(index)
            self.current_pos = int(w.curselection()[0])
            self.playlist_listbox.select_set(self.current_pos)
            #self.playlist_var.set(value)
            #logging.info('You selected item %d: "%s"' % (index, value))

            self.playlist_listbox.selection_clear(0, 'end')
            self.playlist_listbox.select_set(self.current_pos)

    def next(self):
        self.playlist_listbox.selection_clear(0, 'end')
        self.current_pos = self.current_pos+1
        self.playlist_listbox.select_set(self.current_pos)

    def click_file(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            value = w.get(index)
            #self.playlist_var.set(value)
            logging.info('You selected item %d: "%s"' % (index, value))

            self.playlist_listbox.delete(0, "end")
            self.playlist = value
            self.get_playlist(self.playlist)

    def get_playlist(self, file):
        items = []
        self.playlist_data = self.control_json.open_json(PLAYLISTS + '/' + file)
        for key in self.playlist_data:
            items.append(key)

        self.playlist_var.set(items)
        self.current_pos = 0
        self.playlist_listbox.select_set(self.current_pos)

    def check_devices(self):
        self.after(3000, self.check_devices)
        self.input_keys = self.deviceManager.get_device_type(INPUT_KEY)
        self.sliders = self.deviceManager.get_device(SLIDERS)

    def check_sliders_input(self):
        self.after(100, self.check_sliders_input)

        if self.sliders:
            msg = self.sliders.get_msg_separator()
            if msg:
                self.node.publish(msg)

    def check_glove_input(self):
        self.after(100, self.check_glove_input)

        for device in self.input_keys:
            msg = device.get_msg_separator()
            if msg:
                if msg in self.input_key_play:
                    if TimeUtils.is_time(self.last_input_time, 500):
                        self.click_send()
                        self.last_input_time = TimeUtils.current_milli_time()
                elif msg in self.input_key_stop:
                    if TimeUtils.is_time(self.last_input_time, 2000):
                        self.click_stop()
                        self.last_input_time = TimeUtils.current_milli_time()
                elif msg in self.input_key_restart_app:
                    exit()
                elif msg == 'K':
                    self.node.publish({WHEELS: STOP})
                else:
                    #TODO improve that ...
                    self.node.publish({KEY: msg})

