import logging
from enum import Enum

from controller.gui.windows.frames.abstract.abstract_sequence_frame import AbstractSequenceFrame


class CanvasType(Enum):
    BAR = 1
    RECTANGLE = 2


class RectangleFrame(AbstractSequenceFrame):
    def __init__(self, parent, name, color):
        super().__init__(parent, name, color)

        self.rectangle_bars = []
        self.lastX = 0
        self.y1 = 40
        self.y2 = 120

        self.canvas.bind("<Button-1>", self.create_rectangle_click)

    def create_rectangle(self, x1, x2):
        rectangle = self.canvas.create_rectangle(x1, self.y1, x2, self.y2)
        self.canvas.itemconfig(rectangle, fill='pink')
        bar = self.canvas.create_line(x2, self.y1, x2, self.y2, width=5)
        self.canvas.tag_bind(rectangle, '<Button-3>', self.delete_click)
        #self.canvas.tag_bind(rectangle, '<Button-2>', self.scroll_item)
        self.canvas.tag_bind(bar, '<Enter>', self.bar_focus_on)
        self.canvas.tag_bind(bar, '<Leave>', self.bar_focus_out)
        self.rectangle_bars.append(RectangleBar(x1, x2, rectangle, bar, self.canvas))
        self.lastX = x2
        self.set_all_bar_on_top()

    def create_rectangle_click(self, e):
        if e.x > self.lastX:
            self.create_rectangle(self.lastX, e.x)

    def delete_click(self, e):
        rectangle = self.canvas.find_closest(e.x, e.y)
        rectangle_bar = self.find_rectangle(rectangle)
        self.delete(rectangle_bar, True)

    def delete(self, rectangle_bar, fill_gap):
        x1 = rectangle_bar.x1
        x2 = rectangle_bar.x2
        self.canvas.delete(rectangle_bar.rectangle_id)
        self.canvas.delete(rectangle_bar.bar_id)
        self.rectangle_bars.remove(rectangle_bar)

        if fill_gap:
            self.fill_gap(x1, x2)

    def fill_gap(self, removed_x1, removed_x2):
        for rectangle_bar in self.rectangle_bars:
            if rectangle_bar.x1 == removed_x2:
                self.delete(rectangle_bar, False)
                self.create_rectangle(removed_x1, rectangle_bar.x2)
                return
        self.lastX = removed_x1

    def find_rectangle(self, rectangle):
        for rectangle_bar in self.rectangle_bars:
            if rectangle_bar.rectangle_id == rectangle[0]:
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

    #def scroll_item(self, e):
    #    rectangle =
    #    pass

    #def attach_item(self, rectangle):
    #    self.images.append(GuiUtils.set_image(self.canvas, xpos, ypos, visual_type.TYPE, item, zoom))


class RectangleBar:
    def __init__(self, x1, x2, rectangle, bar, canvas):
        self.rectangle_id = rectangle
        self.bar_id = bar
        self.canvas = canvas
        self.x1 = x1
        self.x2 = x2

