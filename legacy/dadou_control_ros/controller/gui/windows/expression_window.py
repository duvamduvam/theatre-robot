import logging
import tkinter as tk
from tkinter import BOTH, TOP, LEFT

from dadou_utils_ros.utils_static import DURATION, LOOP, KEYS, STOP, ORANGE, JSON_EXPRESSIONS, NAME
from controller.control_static import PURPLE, YELLOW, BORDEAUX, CYAN, PLAY, PAUSE, IMAGE

from controller.gui.windows.frames.widgets.directory_tree_widget import DirectoryTreeWidget
from controller.control_config import config
from controller.control_factory import ControlFactory
from controller.gui.expression_duration import ExpressionDuration
from controller.gui.visuals_object.visual_eye import VisualEye
from controller.gui.visuals_object.visual_mouth import VisualMouth
from controller.gui.windows.frames.abstract.rectangle_image2 import RectangleImage2
from controller.gui.windows.frames.timeline_frame import TimeLineFrame
from controller.gui.windows.frames.widgets.galley_widget import GalleryWidget
from controller.gui.windows.frames.widgets.image_observer_feedback import ImageObserverFeedBack



class ExpressionWindow(tk.Frame):

    current_mouse_pos = None

    def __init__(self, mode, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.mode = mode
        self.pack(fill=BOTH, expand=True, side=TOP)

        left_menu = tk.Frame(self, width=50, bg=CYAN)
        left_menu.pack(fill='y', ipadx=20, side=LEFT)

        DirectoryTreeWidget(left_menu, "/home/dadou/Nextcloud/dev/didier/python/dadou_control/visuals", IMAGE)

        top_frame = tk.Frame(self, width=800, bg=CYAN)
        self.top_canvas = tk.Canvas(top_frame, height=300, bg=PURPLE)
        self.top_canvas.grid(row=0, column=0, rowspan=5, columnspan=5)

        self.time_line = TimeLineFrame(self)
        play_button = tk.Button(top_frame, text=PLAY, command=self.time_line.play)
        play_button.grid(row=1, column=6, padx=10)
        pause_button = tk.Button(top_frame, text=PAUSE, command=self.time_line.pause)
        pause_button.grid(row=1, column=7, padx=10)
        stop_button = tk.Button(top_frame, text=STOP, command=self.time_line.stop)
        stop_button.grid(row=1, column=8, padx=10)

        tk.Button(top_frame, text='-', command=self.decrement).grid(row=2, column=6)
        tk.Button(top_frame, text='+', command=self.increment).grid(row=2, column=7)
        self.expression_duration = tk.StringVar()
        self.expression_duration.set('0')
        tk.Label(top_frame, textvariable=self.expression_duration, width=5).grid(row=2, column=8)

        #tk.Button(top_frame, text='load', command_root=self.load).grid(row=3, column=6, padx=10)
        tk.Button(top_frame, text='save', command=self.save).grid(row=3, column=6, padx=10)
        tk.Button(top_frame, text='new', command=self.add).grid(row=3, column=7, padx=10)
        tk.Button(top_frame, text='delete', command=self.delete).grid(row=3, column=8, padx=10)

        self.expression_name = tk.Text(top_frame, width=10, height=1)
        self.expression_name.grid(row=4, column=6, padx=10)

        self.current_mouse_pos = tk.StringVar()
        current_mouse_pos_label = tk.Label(top_frame, textvariable=self.current_mouse_pos)
        current_mouse_pos_label.grid(row=4, column=7, columnspan=2)

        self.expressions_var = tk.StringVar()
        self.expression_list = tk.Listbox(top_frame, listvariable=self.expressions_var, height=16)
        self.expression_list.grid(row=1, column=10, rowspan=4)
        self.expression_list.bind('<<ListboxSelect>>', self.select_expression)
        self.expression_list.bind('<Double-Button-1>', self.load)

        self.loop = tk.StringVar()
        self.loop.set('0')

        keys_label = tk.Label(top_frame, text='keys', padx=10)
        keys_label.grid(row=1, column=11, padx=10)

        self.keys_txt = tk.Text(top_frame, width=10, height=1)
        self.keys_txt.grid(row=1, column=12,  padx=10)

        #tk.Label(top_frame, text='length', width=5).grid(row=2, column=11, padx=10)
        #self.length_txt = tk.Text(top_frame, width=10, height=1)
        #self.length_txt.grid(row=2, column=12, padx=10)

        loop_check = tk.Checkbutton(top_frame, text='loop', variable=self.loop, onvalue=1, offvalue=0)
        loop_check.grid(row=3, column=11)

        top_frame.pack(fill='x', side=TOP)

        ###### face feedback
        self.right_eye_frame = RectangleImage2(self, VisualEye.TYPE, 'Left eye', config[YELLOW])
        self.left_eye_frame = RectangleImage2(self, VisualEye.TYPE, 'Right eye', config[ORANGE])
        self.mouth_frame = RectangleImage2(self, VisualMouth.TYPE, 'Mouths', config [BORDEAUX])

        self.right_eye_observer = ImageObserverFeedBack(self.top_canvas, self.right_eye_frame, 10, 10, VisualEye.TYPE)
        self.left_eye_observer = ImageObserverFeedBack(self.top_canvas, self.left_eye_frame, 210, 10, VisualEye.TYPE)
        self.mouth_observer = ImageObserverFeedBack(self.top_canvas, self.mouth_frame, 30, 120, VisualMouth.TYPE)

        self.load_listbox()
        self.top_canvas.update()
        self.mouse_pos()


    def mouse_pos(self):
        canvas_root_pos = self.right_eye_frame.winfo_rootx()
        canvas_width = self.right_eye_frame.winfo_width()
        x = self.winfo_pointerx() - canvas_root_pos
        #self.time_pos = ((e.x_root - self.canvas_root_x)/self.canvas.winfo_width())*ExpressionDuration.value
        duration = int(self.expression_duration.get())
        if duration != 0 and x >= 0:
            time_pos = round((x/canvas_width)*duration, 2)
            self.current_mouse_pos.set(str(time_pos))

        self.after(100, self.mouse_pos)

    def increment(self):
        self.expression_duration.set(str(int(self.expression_duration.get())+100))
        self.time_line.duration = int(self.expression_duration.get())
        ExpressionDuration.value = int(self.expression_duration.get())

    def decrement(self):
        self.expression_duration.set(str(int(self.expression_duration.get())-100))
        self.time_line.duration = int(self.expression_duration.get())
        ExpressionDuration.value = int(self.expression_duration.get())

    def load_listbox(self):
        expressions = ControlFactory().control_json_manager.open_json(config[JSON_EXPRESSIONS])
        results = []
        for expression in expressions:
            results.append(expression[NAME])
        self.expressions_var.set(results)

    def add(self):
        new_name = self.expression_name.get("1.0", 'end-1c')
        self.expression_name.delete('1.0', tk.END)
        self.expression_name.insert(tk.END, new_name)
        self.save()
        self.load_listbox()
        #logging.info('add new expression')

    def delete(self):
        name = self.expression_name.get(1.0, 'end-1c')
        logging.info('delete expression '.format(name))
        ControlFactory().control_json_manager.delete_expression(name)
        self.load_listbox()

    def save(self):
        ControlFactory().control_json_manager.save_expressions(
            self.expression_name.get(1.0, 'end-1c'),
            ExpressionDuration.value,
            self.loop.get(),
            self.keys_txt.get(1.0, 'end-1c'),
            self.right_eye_frame.export(),
            self.left_eye_frame.export(),
            self.mouth_frame.export()
        )

    def load(self, e):
        name = self.expression_name.get(1.0, 'end-1c')
        expression = ControlFactory().control_json_manager.get_element_from_key(config[JSON_EXPRESSIONS], NAME, name)
        #expression = ControlFactory().control_json_manager.get_attributs_list(config[JSON_EXPRESSIONS], name)
        ExpressionDuration.value = expression[DURATION]
        #self.length_txt.insert("end-1c", ExpressionDuration.value)
        self.expression_duration.set(ExpressionDuration.value)
        self.time_line.duration = int(self.expression_duration.get())
        self.loop.set(expression[LOOP])
        self.keys_txt.delete('1.0', tk.END)

        self.keys_txt.insert("end-1c", expression[KEYS])
        self.right_eye_frame.load(expression['left_eyes'])
        self.left_eye_frame.load(expression['right_eyes'])
        self.mouth_frame.load(expression['mouths'])

    def select_expression(self, e):
        w = e.widget
        if len(w.curselection()) > 0:
            index = int(w.curselection()[0])
            value = w.get(index)
            self.expression_name.delete('1.0', tk.END)
            self.expression_name.insert(tk.END, value)
        else:
            logging.error("no line selected")


