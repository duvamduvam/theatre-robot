import logging
import tkinter as tk
import time
from tkinter import TOP, BOTH, ttk, LEFT

from controller.input.usb_gamepad import USBGamepad
from dadou_utils_ros.misc import Misc
from dadou_utils_ros.utils.time_utils import TimeUtils
from dadou_utils_ros.utils_static import MODE, DEFAULT
from controller.control_static import (
    BORDEAUX, YELLOW, FONT1, PURPLE, DEVICE, MSG, CONTROL, PLAYLIST, CONFIG, FONT2, HOST_NAME,
)

from controller.control_config import config, FONT_DROPDOWN
from controller.gui.windows.frames.widgets.icons_widget import IconsWidget
from controller.gui.windows.mod_window import ModWindow

from controller.gui.windows.small.small_config import SmallConfig
from controller.gui.windows.small.small_control import SmallControl
from controller.gui.windows.small.small_playlist import SmallPlaylist
from controller.input.serial_inputs import SerialInputs

MESSAGE_INPUT_TIMEOUT = 1000
#MENU = [CONTROL, PLAYLIST, CONFIG]
MENU = [PLAYLIST, CONFIG]

class SmallGui(tk.Tk):
    def __init__(self, node, tkMessageBox=None, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        self.node = node

        self.serial_inputs = SerialInputs(self.node)
        self.usb_gamepad = USBGamepad(self.node)

        #self.geometry("480x320")
        self.geometry("640x480")
        #Remove action bar for raspberry
        if Misc.is_raspberrypi():
            self.wm_attributes('-type', 'splash')
        self.bind('<Escape>', lambda e: self.destroy())
        screen_width = self.winfo_screenwidth()
        if screen_width < 1000:
            self.attributes("-fullscreen", True)

        self.menu = tk.Frame(self, height=60)
        self.menu.pack(fill='x', side=TOP)

        self.new_msg = False
        self.popup_closing = False

        #self.listCombo, self.selected_menu = self.create_menu(MENU, 7)
        #self.listCombo.bind('<<ComboboxSelected>>', self.menu_changed)

        self.playlist_button = tk.Button(self.menu, text="P", width=1, font=FONT_DROPDOWN, command=lambda: self.change_window(PLAYLIST, DEFAULT))
        self.playlist_button.pack(side=LEFT)

        self.keyboard_button = tk.Button(self.menu, text="K", width=1, font=FONT_DROPDOWN, command=lambda: self.change_window(CONTROL, DEFAULT))
        self.keyboard_button.pack(side=LEFT)

        self.config_button = tk.Button(self.menu, text="C", width=1, font=FONT_DROPDOWN, command=lambda: self.change_window(CONFIG, DEFAULT))
        self.config_button.pack(side=LEFT)

        self.mod_button = tk.Button(self.menu, text="M", width=1, font=FONT_DROPDOWN, command=lambda: self.change_window(MODE, None))
        self.mod_button.pack(side=LEFT)

        self.icons_widget = IconsWidget(self, menu=self.menu, serial_inputs=self.serial_inputs)

        self.main = None
        self.change_window(PLAYLIST, DEFAULT)
        self.popup, self.popup_label, self.popup_info = self.create_popup()

        self.main.pack(fill=BOTH, side=TOP)

        self.check_inputs()
        self.check_remove_feedback_msg()

    def check_inputs(self):
        self.after(50, self.check_inputs)
        press = self.serial_inputs.check_inputs()
        if not press:
            press = self.usb_gamepad.check_inputs()
        if press:
            self.show_popup(press)

    def create_menu(self, items, width):
        selected_menu = tk.StringVar()
        combo = ttk.Combobox(self.menu, values=items, textvariable=selected_menu, state="readonly", font=FONT_DROPDOWN, width=width)
        combo.option_add("*TCombobox*Listbox*Background", config[PURPLE])
        combo.option_add("*TCombobox*Listbox*Font", FONT_DROPDOWN)
        combo.current(0)
        combo.pack(side=LEFT)
        return combo, selected_menu

    # bind the selected value changes
    def menu_changed(self, event):
        self.change_window(self.selected_menu.get(), DEFAULT)

    def change_window(self, name, mode):
        #TODO switch to withdraw or deiconify
        if self.main:
            try:
                for child in self.main.winfo_children():
                    child.destroy()
            except Exception as e:
                logging.error(e)
            self.main.forget()
            self.main.destroy()

        if name == CONFIG:
            self.main = SmallConfig(self, self.node)
        elif name == CONTROL:
            self.main = SmallControl(self, mode, self.node)
        elif name == PLAYLIST:
            self.main = SmallPlaylist(self, mode, self.node)
        elif name == MODE:
            self.main = ModWindow(self, self.node)

        self.main.pack(fill=BOTH, expand=True, side=TOP)
        time.sleep(0.1)
        self.update_idletasks()

    def feedback_popup(self, input):
        if self.new_msg:
            self.feedback_message.destroy()
        self.feedback_message = tk.Message(self, )
        self.feedback_message.config(bg=config[BORDEAUX])
        input_var = tk.StringVar()
        input_var.set(input)
        self.feedback_msg_label = tk.Label(self.feedback_message, font=config[FONT1],
                                           textvariable=input_var, wraplength=500)
        self.feedback_msg_label.pack()
        self.feedback_message.pack(fill=BOTH, expand=True)
        self.new_msg = True
        self.feedback_message_time = TimeUtils.current_milli_time()

    def create_popup(self):
        popup = tk.Toplevel(self, bg=config[BORDEAUX])
        popup.wm_attributes('-type', 'splash')
        popup.geometry("400x100")
        popup_info = tk.StringVar()
        popup_label = tk.Label(popup, textvariable=popup_info, font=config[FONT2], bg=config[BORDEAUX])
        popup_label.place(x=30, y=30)
        popup.withdraw()
        return popup, popup_label, popup_info

    def show_popup(self, text):
        self.popup_info.set(text)
        self.popup.deiconify()
        if not self.popup_closing:
            self.after(3000, self.hide_popup)
            self.popup_closing = True

    def hide_popup(self):
        self.popup.withdraw()
        self.popup_closing = False

    def update_feedback_panel(self, label: tk.Label, activ: bool):
        if activ:
            label.config(bg=config[YELLOW])
        else:
            label.config(bg=config[BORDEAUX])

    def check_remove_feedback_msg(self):
        self.after(100, self.check_remove_feedback_msg)
        if self.new_msg and TimeUtils.is_time(self.feedback_message_time, MESSAGE_INPUT_TIMEOUT):
            self.feedback_message.destroy()
            self.new_msg = False


