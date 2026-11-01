import logging
import random
import tkinter as tk

from controller.files.file_manager import FileManager
from controller.gui.gui_utils import GuiUtils
from controller.gui.windows.expression_window import ExpressionDuration
from controller.gui.windows.frames.abstract.rectangle_abstract import RectangleAbstract
from controller.gui.windows.frames.timeline_frame import TimeLineFrame


class RectangleImage(RectangleAbstract):

    def __init__(self, parent, visual_type, name, color):
        super().__init__(parent, name, color)
        self.visual_type = visual_type
        self.items = FileManager.list_folder_files_type(visual_type)
        self.images = []

    def create_rectangle(self, x1, x2):
        rectangle_canvas = tk.Canvas(self.canvas, width=x2-x1, bg=self.random_color())
        rectangle_canvas.place(x=x1, y=10)

        rectangle_canvas.bind('<Button-3>', self.delete_click)
        rectangle_canvas.bind('<Button-2>', self.scroll_item)
        rectangle_canvas.bind("<Double-Button-1>", self.create_rectangle_click)
        #self.canvas.tag_bind(rectangle, '<Button-2>', self.scroll_item)
        rectangle_canvas.bind('<Shift-ButtonRelease-1>', self.click_resize)
        #rectangle_canvas.bind('<Shift-B1-Motion>', self.click_resize)
        rectangle = Rectangle(self.rectangle_index, x1, x2, rectangle_canvas,  self.canvas)
        #image = self.attach_item_index(rectangle.canvas_rectangle, self.current_item_index)
        rectangle.image_name = self.items[self.current_item_index]
        rectangle.image = GuiUtils.set_image(self.canvas, 0, 0, self.visual_type, self.items[self.current_item_index], 8)

        rectangle.time = int(x2 / self.canvas.winfo_width() * ExpressionDuration.value)

        self.rectangles.append(rectangle)
        self.rectangle_index += 1
        self.lastX = x2
        return rectangle

    def scroll_item(self, e):
        rectangle = self.find_canvas_rectangle(e.widget)
        rectangle.canvas_rectangle.delete(rectangle.image)
        self.current_item_index = (self.current_item_index + 1) % len(self.items)
        rectangle.image = GuiUtils.set_image(rectangle.canvas_rectangle, 0, 0, self.visual_type,
                                             self.items[self.current_item_index], 5)
        rectangle.image_name = self.items[self.current_item_index]
        self.images.append(rectangle.image)

    def export(self):
        result = []
        for rectangle in self.rectangles:
            pos = round(rectangle.x2 / self.canvas.winfo_width(), 3)
            result.append([pos, rectangle.image_name])
        return result

    def load(self, datas):
        self.clean()
        for data in datas:
            pos = data[0]
            x2 = int(pos * self.canvas.winfo_width())
            rectangle = self.create_rectangle(self.lastX, x2)
            rectangle.image = GuiUtils.set_image(rectangle.canvas_rectangle, 0, 0, self.visual_type, data[1], 8)
            rectangle.image_name = data[1]
            self.images.append(rectangle.image)

    def current_image(self):
        x = TimeLineFrame.x_pos
        for rectangle in self.rectangles:
            if rectangle.x1 <= x <= rectangle.x2:
                #logging.debug("current frame image {}".format(rectangle.image_name))
                return rectangle.image_name


class Rectangle:
    image = None
    image_name = None
    name = None
    time = 0

    def __init__(self, index, x1, x2, rectangle, canvas):
        self.index = index
        self.x1 = x1
        self.x2 = x2
        self.canvas_rectangle = rectangle
        self.canvas = canvas

    def set_image(self, image):
        self.image = image
