import inspect
import logging
import tkinter as tk
from collections import OrderedDict
from tkinter import HORIZONTAL, DISABLED, ACTIVE, W, YES, NW, LEFT, TOP, RIGHT, X, N, END, NORMAL, BOTH
from tkinter.colorchooser import askcolor

from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.utils_static import (
    JSON_LIGHTS_BASE, ORANGE, METHOD, COLOR, NAME, BASE_PATH, JSON_DIRECTORY, SEQUENCES, LOOP, DURATION, KEYS,
)
from controller.control_static import CYAN, YELLOW, JSON_LIGHTS_METHODS, BASE, STATE, PROJECT_LIGHTS_DIRECTORY

from controller.control_config import config
from controller.control_factory import ControlFactory


class LightsWindow(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        self.json_manager = ControlFactory().control_json_manager

        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.pack(fill=BOTH, expand=True, side=TOP)

        ####################### VARS #########################
        self.lights_base_names = tk.StringVar()
        #self.methods_dropbox_var = tk.StringVar()
        self.method_light_label = tk.StringVar()
        self.name_light_label = tk.StringVar()
        self.lights_names = tk.StringVar()
        self.selected_sequence_var = tk.StringVar()
        self.selected_project_var = tk.StringVar()

        self.lights_bases = self.json_manager.open_json(config[JSON_LIGHTS_BASE])
        self.lights_methods = self.json_manager.open_json(config[JSON_LIGHTS_METHODS])

        left_menu = tk.Frame(self, width=100, bg=config[CYAN])
        left_menu.pack(fill='y', ipadx=20, side=LEFT)

        self.right_param = tk.Frame(self, bg=config[YELLOW], height=200)
        self.right_param.pack(fill='x', side=TOP)
        self.right_lights_control = tk.Frame(self, bg=config[ORANGE], height=100)
        self.right_lights_control.pack(side=LEFT, anchor=N, expand=YES, fill=X)

        self.add_lights_button = tk.Button(self.right_lights_control, command=self.add_light,  text="add")
        self.add_lights_button.grid(row=1, column=1)
        self.text_add = tk.Text(self.right_lights_control, width=15, height=1)
        self.text_add.grid(row=2, column=1)

        ############################### DROPBOX ################################
        self.method_light_label.set(list(self.lights_methods.keys())[0])
        self.methods_dropbox = tk.OptionMenu(self.right_lights_control, self.method_light_label,  *list(self.lights_methods.keys()), command=self.method_changed)
        self.methods_dropbox.grid(row=3, column=1)

        ############################### BUTTON delete save #####################
        self.delete_lights_button = tk.Button(self.right_lights_control, command=self.delete_light, text="delete")
        self.delete_lights_button.grid(row=4, column=1)
        self.save_lights_button = tk.Button(self.right_lights_control, command=self.save_light, text="save")
        self.save_lights_button.grid(row=5, column=1)

        ############################## LISTBOX Lights ##########################
        self.base_lights_label = tk.Label(self.right_lights_control, text="Projects Files")
        self.base_lights_label.grid(row=1, column=2)
        self.get_light_names(self.lights_bases)
        self.lights_list = tk.Listbox(self.right_lights_control, listvariable=self.lights_names, height=10)
        self.lights_list.grid(row=2, column=2, rowspan=5)
        self.lights_list.bind('<<ListboxSelect>>', self.select_light)

        ############################## LISTBOX JSON FILES ##########################
        self.json_files_label = tk.Label(self.right_lights_control, text="Projects Files")
        self.json_files_label.grid(row=1, column=3)
        project_lights_path = FilesUtils.get_folder_files_name(config[JSON_DIRECTORY] + config[PROJECT_LIGHTS_DIRECTORY])
        self.json_lights_files_var = tk.StringVar()
        self.json_lights_files_var.set(project_lights_path)
        self.json_lights_list = tk.Listbox(self.right_lights_control, listvariable=self.json_lights_files_var, height=10)
        self.json_lights_list.bind('<<ListboxSelect>>', self.select_sequence)
        self.json_lights_list.grid(row=2, column=3, rowspan=5)

        self.add_element_button = tk.Button(self.right_lights_control, command=self.add_part, text="add")

        ############################## PROJECTS LIGHTS ##########################
        self.project_light_data = {}
        self.selected_element_var = tk.StringVar()
        self.project_lights_label = tk.Label(self.right_lights_control, text="Project Lights")
        self.project_lights_label.grid(row=1, column=4)
        self.project_lights_name = tk.Label(self.right_lights_control, textvariable=self.selected_element_var)
        self.project_lights_name.grid(row=1, column=5, columnspan=2)

        self.project_lights_var = tk.StringVar()
        self.project_lights_list = tk.Listbox(self.right_lights_control, listvariable=self.project_lights_var, height=10)
        self.project_lights_list.grid(row=2, column=4, rowspan=5)
        self.project_lights_list.bind('<<ListboxSelect>>', self.select_element)

        lights_keys_label = tk.Label(self.right_lights_control, text="keys")
        lights_keys_label.grid(row=2, column=5)
        self.lights_keys_var = tk.StringVar()
        self.lights_keys_entry = tk.Entry(self.right_lights_control, textvariable=self.lights_keys_var, width=15)
        self.lights_keys_entry.grid(row=2, column=6)
        self.lights_loop_bool = tk.BooleanVar()
        self.light_loop_radio_button_on = tk.Radiobutton(self.right_lights_control, text="loop off", variable=self.lights_loop_bool, value=False)
        self.light_loop_radio_button_on.grid(row=3, column=5)
        self.light_loop_radio_button_off = tk.Radiobutton(self.right_lights_control, text="on", variable=self.lights_loop_bool, value=True)
        self.light_loop_radio_button_off.grid(row=3, column=6)
        self.light_duration_var = tk.StringVar()
        self.light_duration_label = tk.Label(self.right_lights_control, text="duration")
        self.light_duration_label.grid(row=4, column=5)
        self.light_duration_entry = tk.Entry(self.right_lights_control, textvariable=self.light_duration_var)
        self.light_duration_entry.bind('<Key-Return>', self.element_timing_changed)
        self.light_duration_entry.grid(row=4, column=6)
        self.light_save_button = tk.Button(self.right_lights_control, text="save", command=self.save_global_light)
        self.light_save_button.grid(row=5, column=5)
        self.light_delete_button = tk.Button(self.right_lights_control, text="delete", command=self.delete_global_light)
        self.light_delete_button.grid(row=5, column=6)

        self.light_add_button = tk.Button(self.right_lights_control, text="add", command=self.add_element_light)
        self.light_add_button.grid(row=6, column=5)
        self.new_light_element_var = tk.StringVar()
        self.new_light_element_entry = tk.Entry(self.right_lights_control, textvariable=self.new_light_element_var)
        self.new_light_element_entry.grid(row=6, column=6)

        ############################## PROJECTS ELEMENT LIGHTS ##########################
        self.elements_parts = []
        self.element_lights_label = tk.Label(self.right_lights_control, text="Light elements")
        self.element_lights_label.grid(row=1, column=7)
        self.element_lights_var = tk.StringVar()
        self.element_lights_selected = ""
        self.project_lights_elements_list = tk.Listbox(self.right_lights_control, listvariable=self.element_lights_var, height=10)
        self.project_lights_elements_list.grid(row=2, column=7, rowspan=5)
        self.project_lights_elements_list.bind('<<ListboxSelect>>', self.select_element_part)

        ############################## PROJECTS ELEMENT BUTTON ##########################
        self.add_element_button = tk.Button(self.right_lights_control, command=self.add_part, text="add")
        self.add_element_button.grid(row=1, column=8)
        self.delete_element_button = tk.Button(self.right_lights_control, command=self.delete_part, text="delete")
        self.delete_element_button.grid(row=2, column=8)
        self.save_element_button = tk.Button(self.right_lights_control, command=self.save_part, text="save")
        self.save_element_button.grid(row=3, column=8)
        self.element_timing_var = tk.StringVar()
        self.element_timing = tk.Entry(self.right_lights_control, textvariable=self.element_timing_var, width=15)
        self.element_timing.bind('<Key-Return>', self.element_timing_changed)
        self.element_timing.grid(row=4, column=8)
        self.move_element_up_button = tk.Button(self.right_lights_control, command=self.move_part_up, text="up")
        self.move_element_up_button.grid(row=5, column=8)
        self.move_element_down_button = tk.Button(self.right_lights_control, command=self.move_part_down, text="down")
        self.move_element_down_button.grid(row=6, column=8)

        tk.Label(self.right_param, text='light method').grid(row=1, column=3)
        tk.Label(self.right_param, textvariable=self.method_light_label).grid(row=1, column=4)
        tk.Label(self.right_param, text='light name').grid(row=1, column=5)
        tk.Label(self.right_param, textvariable=self.name_light_label).grid(row=1, column=6)

        ################################# COLORS METHODS PARAMS ################################

        self.color_label = tk.Label(self.right_param, text='color', width=10)
        self.color_label.grid(row=2, column=1)
        self.color_scale = tk.Button(self.right_param, bg=config[ORANGE], text='color', command=self.change_color)
        self.color_scale.grid(row=2, column=2, padx=10, pady=4)

        self.speed_scale = self.create_scale('speed', 3, 1, 0.001, 10, 200, 0.001, 0.01)
        self.size_scale = self.create_scale('size', 4, 1, 0, 100, 200, 1, 20)
        self.spacing_scale = self.create_scale('spacing', 2, 3, 0, 100, 200, 1, 0)
        self.step_scale = self.create_scale('step', 3, 3, 0, 50, 200, 1, 8)
        self.reverse_scale = self.create_scale('reverse', 4, 3, 0, 1, 200, 1, 0)
        self.period_scale = self.create_scale('period', 5, 3, 0, 100, 200, 1, 0)
        self.tail_length_scale = self.create_scale('tail length', 2, 5, 0, 100, 200, 1, 25)
        self.bounce_scale = self.create_scale('bounce', 3, 5, 0, 1, 200, 1, 1)
        self.ring_scale = self.create_scale('ring', 4, 5, 0, 1, 200, 1, 0)
        self.mask_scale = self.create_scale('mask', 5, 5, 0, 1, 200, 1, 0)
        self.num_sparkles_scale = self.create_scale('num sparkles', 2, 7, 1, 0, 200, 1, 1)
        self.max_intensity_scale = self.create_scale('max intensity', 3, 7, 0, 1, 200, 0.01, 1)
        self.min_intensity_scale = self.create_scale('min intensity', 4, 7, 0, 1, 200, 0.01, 0)
        self.precompute_rainbow_scale = self.create_scale('precompute rainbow', 2, 9, 0, 1, 200, 1, 1)
        self.colorwheel_offset_scale = self.create_scale('colorwheel offset', 3, 9, 0, 1, 200, 1, 1)
        self.background_brightness_scale = self.create_scale('background brightness', 4, 9, 0, 1, 200, 0.01, 0.2)

        self.get_base_names(self.lights_methods)

    def save_light(self):
        all_vars = vars(self)
        scale_params = {}
        for var in all_vars:
            if var.__contains__('_scale'):
                scale = getattr(self, var)
                if scale.cget(STATE) == ACTIVE or scale.cget(STATE) == NORMAL:
                    if COLOR not in var:
                        scale_params[var.replace('_scale', '')] = scale.get()
                    else:
                        scale_params[COLOR] = self.get_color()

        scale_params[METHOD] = self.method_light_label.get()
        if self.name_light_label.get():
            self.lights_bases[self.name_light_label.get()] = scale_params
        #self.json_manager.save_lights(self.lights_bases)
        self.json_manager.save_file(self.lights_bases, config[JSON_LIGHTS_BASE])

    def select_base(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            value = w.get(index)
            self.selected_sequence_var.set(value)
            #self.load_sequence(value)
            self.method_light_label.set(value)
            logging.info('You selected item %d: "%s"' % (index, value))
            self.enable_right_sliders(value)

    def select_light(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            selected_light = w.get(index)
            self.name_light_label.set(selected_light)

            light_param = self.json_manager.open_json(config[JSON_LIGHTS_BASE])

            self.method_light_label.set(light_param[selected_light][METHOD])
            self.set_sliders(light_param[selected_light][METHOD], light_param[selected_light])

    def light_loop_switch(self):
        self.lights_loop_bool.set(not self.lights_loop_bool.get())

    def select_sequence(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            self.selected_project_var = w.get(index)
            self.project_light_data = self.json_manager.open_json(config[PROJECT_LIGHTS_DIRECTORY]+self.selected_project_var)
            lights_data_key_list = list(self.project_light_data.keys())
            self.project_lights_var.set(lights_data_key_list)

    def select_element(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            self.selected_element_var.set(w.get(index))
            element_data = self.json_manager.open_json(config[PROJECT_LIGHTS_DIRECTORY]
                                                       +self.selected_project_var)[self.selected_element_var.get()]
            self.lights_loop_bool.set(element_data[LOOP])
            self.light_duration_var.set(element_data[DURATION])
            self.lights_keys_var.set(element_data[KEYS])
            self.elements_parts = []
            for key, val in element_data[SEQUENCES].items():
                self.elements_parts.append("{} : {}".format(val, key))
            self.element_lights_var.set(self.elements_parts)

    def save_global_light(self):
        self.project_light_data = dict(sorted(self.project_light_data.items()))
        self.project_light_data[self.selected_element_var.get()][LOOP] = self.lights_loop_bool.get()
        self.project_light_data[self.selected_element_var.get()][DURATION] = self.light_duration_var.get()
        self.project_light_data[self.selected_element_var.get()][KEYS] = self.lights_keys_var.get()
        self.json_manager.save_file(self.project_light_data, self.selected_project_var,
                                    config[PROJECT_LIGHTS_DIRECTORY])

    def delete_global_light(self):
        self.project_light_data.pop(self.selected_element_var.get())
        self.json_manager.save_file(self.project_light_data, self.selected_project_var,
                                    config[PROJECT_LIGHTS_DIRECTORY])
        self.project_lights_var.set(list(self.project_light_data.keys()))

    def add_element_light(self):
        if self.new_light_element_var:
            self.selected_element_var.set(self.new_light_element_var.get())
            self.project_light_data[self.new_light_element_var.get()] = {}
            self.project_light_data[self.new_light_element_var.get()][LOOP] = False
            self.lights_loop_bool.set(False)
            self.project_light_data[self.new_light_element_var.get()][DURATION] = 0
            self.light_duration_var.set("0")
            self.project_light_data[self.new_light_element_var.get()][KEYS] = "None"
            self.lights_keys_var.set("None")
            self.project_light_data[self.new_light_element_var.get()][SEQUENCES] = {}
            self.save_global_light()
            self.project_lights_var.set(list(self.project_light_data.keys()))

    def select_element_part(self, evt):
        w = evt.widget
        if len(w.curselection()):
            index = int(w.curselection()[0])
            self.element_lights_selected = w.get(index)
            element = self.element_lights_selected.split(" : ")
            self.element_timing_var.set(element[0])

    def element_timing_changed(self, evt):
        index = self.elements_parts.index(self.element_lights_selected)
        element = self.element_lights_selected.split(" : ")
        self.elements_parts[index] = self.element_timing_var.get() + " : "+element[1]
        self.element_lights_var.set(self.elements_parts)

    def add_part(self):
        selection = self.lights_list.curselection()
        if selection:
            self.elements_parts = FilesUtils.clean_string(self.element_lights_var.get(), ['(', ')', '\''])
            self.elements_parts = FilesUtils.lstring_list_clean(self.elements_parts.split(","))
            self.elements_parts.insert(0, "0 : "+self.lights_list.get(selection[0]))
            self.element_lights_var.set(self.elements_parts)

    def delete_part(self):
        if len(self.project_lights_elements_list.curselection()):
            index = int(self.project_lights_elements_list.curselection()[0])
            selected_element_var = self.project_lights_elements_list.get(index)

            self.elements_parts.remove(selected_element_var)
            self.element_lights_var.set(self.elements_parts)

    def save_part(self):
        elements = {}
        for element in self.elements_parts:
            if ':' in element:
                e = element.split(':')
                elements[e[1].lstrip().rstrip()] = e[0].lstrip().rstrip()
        self.project_light_data[self.selected_element_var.get()][SEQUENCES] = elements
        self.json_manager.save_file(self.project_light_data, self.selected_project_var, config[PROJECT_LIGHTS_DIRECTORY])

    def move_part_up(self):
        if len(self.project_lights_elements_list.curselection()):
            index = int(self.project_lights_elements_list.curselection()[0])
            if index != 0:
                switch_element = self.elements_parts[index-1].split(':')
                selected_element_var = self.project_lights_elements_list.get(index).split(':')
                self.elements_parts[index - 1] = switch_element[0] + ":" + selected_element_var[1]
                self.elements_parts[index] = selected_element_var[0] + ":" + switch_element[1]
                self.element_lights_var.set(self.elements_parts)

    def move_part_down(self):
        if len(self.project_lights_elements_list.curselection()):
            index = int(self.project_lights_elements_list.curselection()[0])
            if index != len(self.elements_parts)-1:
                switch_element = self.elements_parts[index+1].split(':')
                selected_element_var = self.project_lights_elements_list.get(index).split(':')
                self.elements_parts[index + 1] = switch_element[0] + ":" + selected_element_var[1]
                self.elements_parts[index] = selected_element_var[0] + ":" + switch_element[1]
                self.element_lights_var.set(self.elements_parts)

    def get_base_names(self, bases):
        base_names = []
        for base in bases:
            base_names.append(base)
        self.lights_base_names.set(base_names)

    def get_light_names(self, elements):
        element_names = []
        for element in elements.keys():
            element_names.append(element)
        self.lights_names.set(element_names)

    def method_changed(self, *args):
        self.enable_right_sliders(self.method_light_label.get())

    def change_color(self):
        colors = askcolor(title="Tkinter Color Chooser")
        self.set_color(colors[1])

    def set_color(self, color):
        self.color_label.configure(bg=color)

    def get_color(self):
        return self.color_label.cget("bg")

    def create_scale(self, label, row, col, min, max, length, resolution, default):
        tk.Label(self.right_param, text=label, width=14).grid(row=row, column=col)
        scale = tk.Scale(self.right_param, from_=min, to=max, length=length,  resolution=resolution, orient=HORIZONTAL)
        scale.grid(row=row, column=col+1, padx=5, pady=6)
        scale.set(default)
        #state=DISABLED

        return scale

    def enable_right_sliders(self, name):
        try:
            all_vars = vars(self)
            for var in all_vars:
                if var.__contains__('_scale'):
                    scale = getattr(self, var)
                    scale.configure(state=DISABLED, bg=config[CYAN])

            scale_params = self.lights_methods[name]
            for param in scale_params:
                scale = getattr(self, param+'_scale')
                scale.configure(state=ACTIVE, bg=config[ORANGE])
                #scale.refresh()

        except AttributeError as err:
            logging.error(err)

    def set_sliders(self, method, values):
        self.enable_right_sliders(method)
        for param in values:
            if type(values[param]) == int:
                scale = getattr(self, param + '_scale')
                scale.set(values[param])
            elif COLOR in param:
                self.set_color(values[param])

    def add_light(self):
        new_light = self.text_add.get(1.0, END+"-1c")
        self.name_light_label.set(new_light)
        self.save_light()
        self.lights_bases = self.json_manager.open_json(config[JSON_LIGHTS_BASE])
        self.get_light_names(self.lights_bases)

    def delete_light(self):
        self.name_light_label.set('')
        delete_index = self.lights_list.curselection()[0]
        to_delete = self.lights_list.get(delete_index)
        self.lights_bases.pop(to_delete, None)
        self.save_light()
        self.lights_bases = self.json_manager.open_json(config[JSON_LIGHTS_BASE])
        self.get_light_names(self.lights_bases)
