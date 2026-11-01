import logging
import os
import tkinter as tk
from tkinter import filedialog as fd

from dadou_utils_ros.utils.time_utils import TimeUtils

from controller.control_factory import ControlFactory
from controller.control_config import ControlStatic
from controller.files.file_manager import FileManager
from controller.gui.windows.frames.widgets.audio_select_popup import AudioPopupWidget
from controller.gui.windows.frames.music_frame import MusicFrame


class SequencesManagerWidget(tk.Frame):
    def __init__(self, parent, menu, music_frame: MusicFrame):
        self.parent = parent
        self.music_frame = music_frame

        #TODO improve 'frames' parameters
        self.sequence_manager = ControlFactory().sequence_management
        tk.Frame.__init__(self, menu)

        #variables
        self.files_var = tk.StringVar(self)
        self.audio_name_var = tk.StringVar(self)
        self.audio_duration_var = tk.StringVar(self)
        self.audio_duration_formatted_var = tk.StringVar(self)

        self.selected_sequence_var = tk.StringVar(self)
        self.audio_path = None

        self.seq_files = FileManager.list_folder_files(ControlStatic.SEQUENCES_DIRECTORY_KEY)
        self.seq_files.sort()
        self.files_var.set(self.seq_files)

        tk.Button(self, text='load').grid(row=0, column=0, padx=10)
        tk.Button(self, text='save', command=self.save).grid(row=0, column=1, padx=10)
        tk.Button(self, text='new', command=self.new).grid(row=0, column=2, padx=10)
        tk.Button(self, text='delete', command=self.delete).grid(row=0, column=3, padx=10)

        self.audio_name = tk.Label(self, textvariable=self.audio_name_var)
        logging.info(self.audio_name_var.get())
        self.audio_name.grid(row=1, column=0, sticky='ns', columnspan=4)
        self.audio_duration = tk.Label(self, textvariable=self.audio_duration_formatted_var)
        self.audio_duration.grid(row=2, column=1)
        tk.Label(self, text='current : ').grid(row=3, column=0)

        self.selected_sequence = tk.Label(self, textvariable=self.selected_sequence_var)
        self.selected_sequence.grid(row=3, column=1)

        tk.Label(self, text='new : ').grid(row=4, column=0)
        self.new_text = tk.Text(self, width=30, height=1)
        self.new_text.grid(row=4, column=1, columnspan=3)

        audio_dialog = tk.Button(self, text="Ajouter", command=lambda: AudioPopupWidget(menu))
        audio_dialog.grid(row=5, column=0)

        sequences_listbox = tk.Listbox(self, listvariable=self.files_var, height=6)
        sequences_listbox.bind('<<ListboxSelect>>', self.select_sequence)
        sequences_listbox.grid(row=5, column=1, columnspan=2)

        self.pack(fill='x', side='top')

    def select_sequence(self, evt):
        w = evt.widget
        index = int(w.curselection()[0])
        value = w.get(index)
        self.selected_sequence_var.set(value)
        self.load_sequence(value)
        logging.info('You selected item %d: "%s"' % (index, value))

    def load_first_sequence(self):
        self.load_sequence(self.seq_files[0])

    def load_sequence(self, sequence_name):
        self.selected_sequence_var.set(sequence_name)
        self.sequence_manager.load_audio(sequence_name)
        audio_name = self.sequence_manager.audio_segment.audio_name
        self.audio_path = self.sequence_manager.json_sequence["audio_path"]
        self.audio_name_var.set(audio_name)

        audio_duration = self.sequence_manager.audio_segment.get_duration()
        self.audio_duration_var.set(audio_duration)
        self.audio_duration_formatted_var.set(TimeUtils.formatted_time(audio_duration))

        self.music_frame.update()

        display_data = self.sequence_manager.audio_segment.get_audio_data_display(self.music_frame.winfo_width())
        self.music_frame.load_audio(display_data)

        self.parent.faces_frame.load(self.sequence_manager.get_parts("faces"))
        self.parent.lights_frame.load(self.sequence_manager.get_parts("lights"))

        self.parent.neck_frame.clear()
        for neck in self.sequence_manager.get_parts("necks"):
            self.parent.neck_frame.create_circle_json(neck[0], neck[1])

        self.parent.wheels_frame.clear()
        for wheel in self.sequence_manager.get_parts("wheels"):
            self.parent.wheels_frame.create_point_json(wheel[0], wheel[1], wheel[2])


    def save(self):
        logging.info('save sequence')
        necks = self.parent.neck_frame.points
        wheels = self.parent.wheels_frame.export()
        lights = self.parent.lights_frame.export()
        faces = self.parent.faces_frame.export()

        self.sequence_manager.save_sequence(self.selected_sequence_var.get(), self.audio_duration_var.get(),
                                            self.audio_name_var.get(), self.audio_path, lights, faces, necks, wheels)

    def delete(self):
        logging.info('delete')

    def new(self):
        filepath = fd.askopenfilename()
        self.audio_name_var.set(os.path.basename(filepath))
        self.audio_path = os.path.dirname(filepath)+"/"
        new_seq = self.new_text.get("1.0", "end-1c")
        if new_seq:
            self.selected_sequence_var.set(new_seq)
        files = FileManager.list_folder_files(ControlStatic.SEQUENCES_DIRECTORY_KEY)
        files.sort()
        self.files_var.set(files)

