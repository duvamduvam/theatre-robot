import logging
import tkinter as tk

from controller.com.serial_devices_manager import SerialDeviceManager
from controller.control_factory import ControlFactory


class GloveWindow(tk.Frame):
    def __init__(self, parent):

        self.deviceManager = SerialDeviceManager()
        self.serial_glove_left = self.deviceManager.gloveLeft

        tk.Frame.__init__(self, parent, bg='grey')
        self.pack(fill='both', expand=True, side='top')

        top = tk.Frame(self, bg='blue')
        top.pack(fill='x', side='top')

        self.top_left = tk.Label(top, bg='orange')
        self.top_left.pack(ipadx=10, ipady=10, fill='x', expand=True, side='left')
        self.top_right = tk.Label(top, bg='red')
        self.top_right.pack(ipadx=10, ipady=10, fill='x', expand=True, side='right')

        self.glove_left = tk.Label(self, bg='blue')
        #keyboard input command_root
        input_command_frame = tk.Frame(self.glove_left)
        input_command_frame.pack(fill='x', side='top')

        self.free_text = tk.Text(input_command_frame, height=5, width=52)
        self.free_text.grid(row=0, column=0, padx=10)
        send_text = tk.Button(input_command_frame, text='envoyer', command=lambda: self.sendText())
        send_text.grid(row=1, column=0, padx=10)

        self.glove_left.config(font=("Courier", 100, "bold"))
        self.glove_left.pack(ipadx=10, ipady=10, fill='both', expand=True, side='left')
        self.glove_right = tk.Label(self, bg='yellow')
        self.glove_left.config(font=("Courier", 100, "bold"))
        self.glove_right.pack(ipadx=10, ipady=10, fill='both', expand=True, side='right')

        self.checkNewUsb()
        self.gloveInput()

    def checkNewUsb(self) -> None:
        self.after(1000, self.checkNewUsb)
        msg = "disconnected"
        if self.deviceManager.checkNewDevice(self.serial_glove_left):
            msg = "connected"
            self.top_left.config(bg="green")
            self.top_left.config(text=msg)
            #self.serial_glove_left = SerialDevice(self.deviceManager.gloveLeft)
        else:
            self.top_left.config(bg="red")
        self.top_left.config(text=msg)

    def gloveInput(self) -> None:
        self.after(100, self.gloveInput)
        if self.serial_glove_left.plugged:
            msg = self.serial_glove_left.get_msg()
            if msg:
                #ControlFactory().ws_client.send(msg)
                self.glove_left.config(text=msg)

    def sendText(self):
        command = self.free_text.get("1.0",'end-1c')
        logging.info("input command_root "+command)
        ControlFactory().ws_client.send(command)


