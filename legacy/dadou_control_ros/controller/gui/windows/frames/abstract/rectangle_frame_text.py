import logging
from enum import Enum
import tkinter as tk

from controller.gui.gui_utils import GuiUtils
from controller.gui.windows.expression_window import ExpressionDuration
from controller.gui.windows.frames.abstract.abstract_sequence_frame import AbstractSequenceFrame


class CanvasType(Enum):
    BAR = 1
    RECTANGLE = 2


class RectangleFrameText(AbstractSequenceFrame):
    def __init__(self, parent, name, color, items):
        super().__init__(parent, name, color)
        logging.info('rectangle text')
        self.points = []
        self.rectangle_bars = []
        self.lastX = 0
        self.y1 = 40
        self.y2 = 120
        self.images = []

        self.items = items
        self.canvas.bind("<Button-1>", self.create_rectangle_click)
        self.current_image_index = 0
        self.rectangle_bar_index = 0

    def create_rectangle(self, x1, x2, name=None):
        #rectangle = self.canvas.create_rectangle(x1, self.y1, x2, self.y2, fill="pink")
        rectangle_canvas = tk.Canvas(self.canvas, width=x2-x1)
        rectangle_canvas.place(x=x1, y=10)

        bar = rectangle_canvas.create_line(x2-x1, self.y1, x2-x1, self.y2, width=5)
        rectangle_canvas.bind('<Button-3>', self.delete_click)
        rectangle_canvas.bind('<Button-2>', self.scroll_item)
        #self.canvas.tag_bind(rectangle, '<Button-2>', self.scroll_item)
        self.canvas.tag_bind(bar, '<Enter>', self.bar_focus_on)
        self.canvas.tag_bind(bar, '<Leave>', self.bar_focus_out)
        rectangle_bar = RectangleBar(x1, x2, rectangle_canvas, bar, self.canvas)
        text_object = self.attach_item_name(rectangle_bar.canvas_rectangle,  self.items[self.current_image_index])
        rectangle_bar.text = self.items[self.current_image_index]
        rectangle_bar.text_object = text_object

        rectangle_bar.time = round((self.lastX / self.canvas.winfo_width()), 2)

        if name:
            self.attach_item_name(rectangle_bar.canvas_rectangle, name)

        self.rectangle_bars.append(rectangle_bar)
        self.rectangle_bar_index += 1
        self.lastX = x2
        self.set_all_bar_on_top()
        return rectangle_bar

    def create_rectangle_click(self, e):
        if e.x > self.lastX:
            self.create_rectangle(self.lastX, e.x)

    def create_rectangle_json(self, x1, x2, name):
        x1 = int(self.canvas.winfo_width() * x1)
        x2 = int(self.canvas.winfo_width() * x2)
        self.create_rectangle(x1, x2, name)

    def delete_click(self, e):
        rectangle_bar = self.find_canvas_rectangle(e.widget)
        self.delete_canvas(rectangle_bar, True)

    def delete_canvas(self, rectangle_bar, fill_gap):
        x1 = rectangle_bar.canvas_rectangle.winfo_x()
        x2 = x1+rectangle_bar.canvas_rectangle.winfo_width()

        logging.info('x1:{} x2:{}'.format(x1, x2))
        rectangle_bar.canvas_rectangle.destroy()
        #self.canvas.delete(rectangle_bar.bar_id)
        self.rectangle_bars.remove(rectangle_bar)
        if fill_gap:
            self.fill_gap(x1, x2)

    def fill_gap(self, removed_x1, removed_x2):
        for rectangle_bar in self.rectangle_bars:
            logging.info('rectangle bar x:{} removed_x2:{}'.format(rectangle_bar.x1, removed_x2))
            if abs(removed_x2 - rectangle_bar.x1) <= 3:
                rectangle_bar.canvas_rectangle.update()
                x1 = removed_x1
                x2 = rectangle_bar.x2
                self.delete_canvas(rectangle_bar, False)
                self.create_rectangle(x1, x2)
        self.lastX = removed_x1


    def find_canvas_rectangle(self, rectangle):
        for rectangle_bar in self.rectangle_bars:
            if rectangle_bar.canvas_rectangle == rectangle:
                return rectangle_bar
        print("no matching rectangle bar")

    def set_all_bar_on_top(self):
        for rectangle_bar in self.rectangle_bars:
            self.canvas.tag_raise(rectangle_bar.bar_id)

    def bar_focus_on(self, e):
        bar = self.canvas.find_closest(e.x, e.y)
        if self.is_bar(bar):
            self.canvas.itemconfig(bar, width=10)

    def bar_focus_out(self, e):
        bar = self.canvas.find_closest(e.x, e.y)
        if self.is_bar(bar):
            self.canvas.itemconfig(bar, width=5)

    def is_bar(self, canvas_id):
        for rectangle_bar in self.rectangle_bars:
            if rectangle_bar.bar_id == canvas_id[0]:
                return True

    def scroll_item(self, e):
        rectangle_bar = self.find_canvas_rectangle(e.widget)
        rectangle_bar.canvas_rectangle.delete(rectangle_bar.text_object)
        self.current_image_index = (self.current_image_index + 1) % len(self.items)
        text_object = self.attach_item_name(rectangle_bar.canvas_rectangle,  self.items[self.current_image_index])
        rectangle_bar.text_object = text_object
        rectangle_bar.text = self.items[self.current_image_index]

    #def attach_item_index(self, canvas, item_index):
    #    return [self.items[item_index], GuiUtils.set_text(canvas, 0, 0, self.items[item_index])]

    def attach_item_name(self, canvas, name):
        return GuiUtils.set_text(canvas, 0, 0, name)

    def export(self):
        result = []
        for rectangle_bar in self.rectangle_bars:
            result.append([rectangle_bar.time, rectangle_bar.text])
        return result

    def load(self, datas):
        for data in datas:
            time = data[0]
            text = data[1]
            x2 = int(time/ExpressionDuration.value * self.canvas.winfo_width())
            rectangle_bar = self.create_rectangle(self.lastX, x2)
            text = self.attach_item_name(rectangle_bar.canvas_rectangle, text)
            rectangle_bar.text = text
            rectangle_bar.time = time

    def clear(self):
        for rectangle_bar in self.rectangle_bars:
            rectangle_bar.canvas_rectangle.destroy()
        self.lastX = 0


class RectangleBar:
    text_object = None
    text = None
    name = None
    time = 0

    def __init__(self, x1, x2, rectangle, bar, canvas):
        self.x1 = x1
        self.x2 = x2
        self.canvas_rectangle = rectangle
        self.bar_id = bar
        self.canvas = canvas

    def set_image(self, image):
        self.image = image

