import logging
import tkinter as tk
from tkinter import TOP, X, BOTH

from dadou_utils_ros.com.input_messages_list import InputMessagesList
from dadou_utils_ros.utils_static import KEY, JOYSTICK, ORANGE, WHEELS, STOP
from controller.control_static import (
    BUTTON_GRID, INPUT_KEY, LORA, SLIDERS, CYAN, BORDEAUX, FONT1, YELLOW, PURPLE, GLOVE_LEFT, GLOVE_RIGHT,
)

from controller.control_config import config, RESTART_APP
from controller.control_factory import ControlFactory


class KeyboardWindow(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.mod = 'A'
        #logging.info("Control factory : {} {} {}".format(ControlFactory(), ControlFactory().__dict__, dir(ControlFactory())))

        self.deviceManager = ControlFactory().devices_manager

        self.devices = None
        self.sliders = None
        self.input_key_restart_app = RESTART_APP

        #self.serial_glove_left = self.deviceManager.gloveLeft
        #self.serial_glove_right = self.deviceManager.gloveRight

        self.pack(fill=BOTH, expand=True, side=TOP)


        keys = [['1', '2', '3', 'A', 'E'],
                ['4', '5', '6', 'B', 'F'],
                ['7', '8', '9', 'C', 'G'],
                ['&', '0', '$', 'D', 'H']]

        grid = tk.Frame(self, bg=config[CYAN], width=1000, height=500, padx=20, pady=20)
        #grid['padding'] = (5,10,5,10)

        for x in range(4):
            for y in range(5):
                self.create_cell(grid, x, y, keys[x][y])
                #tk.Label(grid, bg=config[BORDEAUX, text=keys[x][y], font=self.FONT1, height=1, width=2).grid(row=x, column=y)

        self.lora_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='Lo', font=config[BUTTON_GRID], height=1, width=2)
        self.lora_feedback_panel.grid(row=0, column=6)

        self.lora_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='Lo', font=config[BUTTON_GRID], height=1, width=2)
        self.lora_feedback_panel.grid(row=0, column=6)

        self.wifi_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='Wi', font=config[BUTTON_GRID], height=1, width=2)
        self.wifi_feedback_panel.grid(row=0, column=7)

        self.internet_label = tk.Label(grid, bg=config[ORANGE], text="I", font=config[BUTTON_GRID], width=2)
        self.internet_label.grid(row=0, column=8)

        self.left_glove_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='L', font=config[BUTTON_GRID], height=1, width=2)
        self.left_glove_feedback_panel.grid(row=1, column=6)

        self.right_glove_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='R', font=config[BUTTON_GRID], height=1, width=2)
        self.right_glove_feedback_panel.grid(row=1, column=7)

        self.joy_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='J', font=config[BUTTON_GRID], height=1, width=2)
        self.joy_feedback_panel.grid(row=1, column=8)

        self.sliders_feedback_panel = tk.Label(grid, bg=config[BORDEAUX], text='S', font=config[BUTTON_GRID], height=1, width=2)
        self.sliders_feedback_panel.grid(row=2, column=6)

        self.right_panel_top = tk.Label(grid, bg=config[YELLOW], text='A', font=config[BUTTON_GRID], height=1, width=4)
        self.right_panel_top.grid(row=2, column=7, columnspan=2)

        self.right_panel_middle = tk.Label(grid, bg=config[CYAN], font=config[BUTTON_GRID], height=1, width=4)
        self.right_panel_middle.grid(row=3, column=6, columnspan=3, rowspan=2)

        grid.pack(fill=BOTH, side=TOP, expand=True)

        self.check_plugged_device()
        self.check_internet()
        self.check_glove_input()
        #self.check_self.gamepad_input()
        self.check_sliders_input()

    def create_cell(self, grid, x, y, name):
        color = config[CYAN]
        if ((x+y) % 2) == 0:
            color = config[YELLOW]
        cell = tk.Button(grid, text=name, font=config[BUTTON_GRID], bg=color, command=lambda: self.click_button(name), activebackground=config[PURPLE], height=1, width=2)
        cell.grid(row=x, column=y)

    def check_internet(self) -> None:
        self.after(500, self.check_internet)
        #TODO fix slow startup
        """if Misc.is_connected():
            self.internet_label.config(bg="green")
        else:
            self.internet_label.config(bg=BORDEAUX)"""

    def click_button(self, key):
        if key in "ABCDEFGH":
            self.right_panel_top.config(text=key)
            self.mod = key
        else:
            self.right_panel_middle.config(text=self.mod + key)
            self.node.publish({KEY: self.mod + key})

    def check_plugged_device(self):
        self.after(3000, self.check_plugged_device)

        self.sliders = self.deviceManager.get_device(SLIDERS)
        self.devices = self.deviceManager.get_device_type(INPUT_KEY)

        self.update_feedback_panel(self.left_glove_feedback_panel, self.deviceManager.get_device(GLOVE_LEFT))
        self.update_feedback_panel(self.right_glove_feedback_panel, self.deviceManager.get_device(GLOVE_RIGHT))
        #self.update_feedback_panel(self.lora_feedback_panel, self.deviceManager.get_device(LORA))
        #self.update_feedback_panel(self.joy_feedback_panel, self.deviceManager.get_device(JOY))
        self.update_feedback_panel(self.sliders_feedback_panel, self.deviceManager.get_device(SLIDERS))

    def update_feedback_panel(self, label: tk.Label, activ: bool):
        if activ:
            label.config(bg=config[YELLOW])
        else:
            label.config(bg=config[BORDEAUX])

    def check_glove_input(self):
        self.after(100, self.check_glove_input)
        for device in self.devices:
            msg = device.get_msg_separator()
            if msg:
                self.right_panel_middle.config(text=msg)
                if msg in self.input_key_restart_app:
                    exit()
                elif msg == 'K':
                    self.node.publish({WHEELS: STOP})
                else:
                    self.node.publish({KEY: msg})


    #def check_buttons_input(self):
    #    self.after(100, self.check_glove_input)
    #    devices = self.deviceManager.get_device_type(INPUT_KEY)
    #    for device in devices:
    #        msg = device.get_msg_separator()
    #        if msg:
    #            self.right_panel_middle.config(text=msg)
    #            ControlFactory().message.send_multi_ws({KEY: msg})

    """def check_self.gamepad_input(self):
        self.after(100, self.check_self.gamepad_input)
        joy = self.deviceManager.get_device(JOY)
        if joy:
            msg = joy.get_msg_separator()
            if msg:
                self.right_panel_middle.config(text=msg)
                ControlFactory().message.send_multi_ws({JOY: msg})"""

    def check_sliders_input(self):
        self.after(100, self.check_sliders_input)

        if self.sliders:
            msg = self.sliders.get_msg_separator()
            if msg:
                self.right_panel_middle.config(text=msg)
                self.node.publish(msg)

