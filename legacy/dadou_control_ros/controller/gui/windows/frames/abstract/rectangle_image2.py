import logging
import tkinter as tk

from dadou_utils_ros.misc import Misc

from controller.control_factory import ControlFactory
from controller.gui.windows.frames.abstract.rectangle_highlighted import HighlightedRectangle
from controller.files.file_manager import FileManager
from controller.gui.gui_utils import GuiUtils
from controller.gui.windows.expression_window import ExpressionDuration
from controller.gui.windows.frames.abstract.rectangle_abstract import RectangleAbstract
from controller.gui.windows.frames.timeline_frame import TimeLineFrame


class RectangleImage2(RectangleAbstract):

    def __init__(self, parent, visual_type, name, color):
        super().__init__(parent, name, color)
        self.visual_type = visual_type
        self.items = FileManager.list_folder_files_type(visual_type)
        self.images = []

    def create_rectangle(self, x1, x2, highlight):
        logging.debug("new image rectangle")
        rectangle_canvas = tk.Canvas(self.canvas, width=x2-x1, bg=Misc.random_color())
        rectangle_canvas.place(x=x1, y=10)
        rectangle_canvas.bind('<Button-1>', self.highlight)
        rectangle_canvas.bind('<Button-3>', self.delete_click)
        rectangle_canvas.bind("<Double-Button-1>", self.create_rectangle_click)
        rectangle_canvas.bind('<ButtonRelease-2>', self.click_resize)
        rectangle = Rectangle(self.rectangle_index, x1, x2, rectangle_canvas,  self.canvas)

        rectangle.time = int(x2 / self.canvas.winfo_width() * ExpressionDuration.value)

        self.rectangles.append(rectangle)
        self.rectangle_index += 1
        self.lastX = x2
        if highlight:
            rectangle.canvas_rectangle.configure(bg='white')
            HighlightedRectangle.rectangle = rectangle
        return rectangle

    def highlight(self, e):
        rectangle = self.find_canvas_rectangle(e.widget)
        rectangle.canvas_rectangle.configure(bg='white')
        HighlightedRectangle.update_rectangle(rectangle)

    def drop_image(self,e):
        logging.info("drop")

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
        folder = ControlFactory().control_json_manager.get_folder_path_from_type(self.visual_type).rstrip('/')
        for rectangle in self.rectangles:
            pos = round(rectangle.x2 / self.canvas.winfo_width(), 3)
            if rectangle.image_folder:
                rectangle.image_folder = rectangle.image_folder.replace(folder, '')
                result.append([pos, rectangle.image_folder+'/'+rectangle.image_name])
            else:
                result.append([pos, rectangle.image_name])
        return result

    def load(self, datas):
        self.clean()
        for data in datas:
            pos = data[0]
            x2 = int(pos * self.canvas.winfo_width())
            rectangle = self.create_rectangle(self.lastX, x2, False)
            rectangle.tk_image = GuiUtils.set_image(rectangle.canvas_rectangle, 0, 0, self.visual_type, data[1], 8)
            rectangle.image_name = data[1]
            self.images.append(rectangle.tk_image)

    def current_image(self):
        x = TimeLineFrame.x_pos
        for rectangle in self.rectangles:
            if rectangle.x1 <= x <= rectangle.x2:
                #logging.debug("current frame image {}".format(rectangle.image_name))
                return rectangle.tk_image

class Rectangle:
    tk_image = None
    image_name = None
    image_folder = None
    name = None
    time = 0

    def __init__(self, index, x1, x2, rectangle, canvas):
        self.index = index
        self.x1 = x1
        self.x2 = x2
        self.canvas_rectangle = rectangle
        self.canvas = canvas

    def set_image(self, tk_image, name, folder):
        self.image_name = name
        self.image_folder = folder
        self.tk_image = tk_image
        GuiUtils.copy_image(HighlightedRectangle.rectangle.canvas_rectangle, tk_image, clean=True, random_color=True)
