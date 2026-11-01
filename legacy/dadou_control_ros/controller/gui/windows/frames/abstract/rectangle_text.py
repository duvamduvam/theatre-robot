import logging
import tkinter as tk
from tkinter import TOP

from dadou_utils_ros.misc import Misc
from controller.control_static import DATAS

from controller.gui.gui_utils import GuiUtils
from controller.gui.windows.expression_window import ExpressionDuration
from controller.gui.windows.frames.abstract.rectangle_abstract import RectangleAbstract
from controller.gui.windows.frames.timeline_frame import TimeLineFrame


class RectangleText(RectangleAbstract):

    def __init__(self, parent, name, color, items, **kwargs):
        super().__init__(parent, name, color)
        self.pack(fill='x', side=TOP)
        self.items = items
        #self.items = FileManager.list_folder_files(visual_type)

        self.canvas.update()
        if DATAS in kwargs:
            self.load(kwargs[DATAS])

    def create_rectangle(self, x1, x2, highlight):
        rectangle_canvas = tk.Canvas(self.canvas, width=x2-x1, bg=Misc.random_color())
        rectangle_canvas.place(x=x1, y=10)

        rectangle_canvas.bind('<Button-3>', self.delete_click)
        rectangle_canvas.bind('<Button-2>', self.scroll_item)
        rectangle_canvas.bind("<Double-Button-1>", self.create_rectangle_click)
        #self.canvas.tag_bind(rectangle, '<Button-2>', self.scroll_item)
        rectangle_canvas.bind('<Shift-ButtonRelease-1>', self.click_resize)
        #rectangle_canvas.bind('<Shift-B1-Motion>', self.click_resize)
        rectangle = Rectangle(self.rectangle_index, x1, x2, rectangle_canvas,  self.canvas)
        rectangle.time = int(x2 / self.canvas.winfo_width() * ExpressionDuration.value)

        self.rectangles.append(rectangle)
        self.rectangle_index += 1
        self.lastX = x2
        return rectangle

    def scroll_item(self, e):
        rectangle = self.find_canvas_rectangle(e.widget)
        #rectangle.canvas_rectangle.delete(rectangle.image)
        self.current_item_index = (self.current_item_index + 1) % len(self.items)
        rectangle.canvas_rectangle.delete(rectangle.text_object)
        rectangle.text_object = GuiUtils.set_text(rectangle.canvas_rectangle, 0, 0, self.items[self.current_item_index])
        rectangle.text = self.items[self.current_item_index]

    def export(self):
        result = []
        for rectangle in self.rectangles:
            pos = round(rectangle.x2 / self.canvas.winfo_width(), 3)
            result.append([pos, rectangle.text])
        return result

    def load(self, datas):
        self.clean()
        for data in datas:
            try:
                pos = data[0]
                x2 = int(pos * self.canvas.winfo_width())
                rectangle = self.create_rectangle(self.lastX, x2, False)
                rectangle.text_object = GuiUtils.set_text(rectangle.canvas_rectangle, 0, 0, data[1])
                #self.objects.append(rectangle.text_object)
                rectangle.text = data[1]
            except ValueError:
                logging.error('pos {} or text {} error'.format(data[0], data[1]))

    def current_image(self):
        x = TimeLineFrame.x_pos
        for rectangle in self.rectangles:
            if rectangle.x1 <= x <= rectangle.x2:
                #logging.debug("current frame image {}".format(rectangle.image_name))
                return rectangle.image_name


class Rectangle:
    text = None
    text_object = None
    name = None
    time = 0

    def __init__(self, index, x1, x2, rectangle, canvas):
        self.index = index
        self.x1 = x1
        self.x2 = x2
        self.canvas_rectangle = rectangle
        self.canvas = canvas

