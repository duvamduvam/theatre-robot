import shutil
import tkinter as tk
from tkinter import HORIZONTAL, filedialog
from tkinter.messagebox import showinfo

class AudioPopupWidget:

    def __init__(self, parent):

        self.AUDIO_FOLDER = '/home/dadoutils/Nextcloud/dev/didier/dadoutils/DadouControl/audios'

        self.parent = parent
        self.top = tk.Toplevel(self.parent)
        self.top.geometry("800x600")
        self.top.title("Child Window")

        self.audio_files_management = tk.Frame(self.top, bg=CYAN)
        audio_label = tk.Label(self.audio_files_management, text='nouveau fichier audio')
        audio_label.grid(row=0, column=0, padx=10)
        choose_button = tk.Button(self.audio_files_management, text='choose', command=lambda: self.select_file(parent))
        choose_button.grid(row=0, column=1, padx=10)
        self.file_label = tk.Label(self.audio_files_management, text='result')
        self.file_label.grid(row=1, column=0, padx=10)
        self.audio_files_management.pack(fill='x', side=TOP)

    def select_file(self, parent):
        filetypes = (
            ('text files', '*.mp3'),
            ('All files', '*.*')
        )

        parent.filename = filedialog.askopenfilename(
            title='Open a file',
            initialdir='/home/dadoutils',
            filetypes=filetypes)

        showinfo(
            title='Selected File',
            message=parent.filename
        )

        if parent.filename is not None:
            self.file_label.configure(text="File Opened: " + parent.filename)
            shutil.copy(parent.filename, self.AUDIO_FOLDER)
