import logging
from abc import abstractmethod

from controller.gui.windows.frames.abstract.abstract_sequence_frame import AbstractSequenceFrame


class RectangleAbstract(AbstractSequenceFrame):

    def __init__(self, parent, name, color):
        super().__init__(parent, name, color)
        logging.info('rectangle 2')
        self.rectangles = []
        self.lastX = 0
        self.y1 = 40
        self.y2 = 120

        self.canvas.bind("<Double-Button-1>", self.create_rectangle_click)
        self.canvas_root_x = self.canvas.winfo_rootx()
        self.current_item_index = 0
        self.rectangle_index = 0
        self.time_pos = 0

    def create_rectangle_click(self, e):
        if len(self.rectangles) == 0:
            self.create_rectangle(0, self.canvas.winfo_width(), True)
        else:
            rectangle = self.find_canvas_rectangle(e.widget)
            self.split_rectangle(rectangle, e.x, e.x_root)

    def split_rectangle(self, rectangle, x, x_root):
        rectangle.canvas_rectangle.config(width=x)
        x1 = x_root - self.canvas_root_x-20
        self.create_rectangle(x1, rectangle.x2, True)
        rectangle.x2 = x1

    @abstractmethod
    def create_rectangle(self, x1, x2, highlight):
        pass

    def delete_click(self, e):
        rectangle = self.find_canvas_rectangle(e.widget)
        self.delete_canvas(rectangle, True)

    def delete_canvas(self, rectangle, fill_gap):
        x1 = rectangle.canvas_rectangle.winfo_x()
        x2 = x1+rectangle.canvas_rectangle.winfo_width()

        logging.info('x1:{} x2:{}'.format(x1, x2))
        rectangle.canvas_rectangle.destroy()
        self.rectangles.remove(rectangle)
        if fill_gap:
            self.fill_gap(x1, x2)

    def fill_gap(self, removed_x1, removed_x2):
        left_rectangle = None
        closest_left = None
        for rectangle in self.rectangles:
            logging.info('rectangle x:{} removed_x2:{}'.format(rectangle.x1, removed_x2))

            # find closest left
            if closest_left:
                if closest_left.x1 < rectangle.x1 < removed_x1:
                    closest_left = rectangle
            else:
                if rectangle.x1 < removed_x1:
                    closest_left = rectangle

            # find most left
            if not left_rectangle:
                left_rectangle = rectangle
            elif rectangle.x1 < left_rectangle.x1:
                left_rectangle = rectangle

        self.lastX = removed_x1
        if closest_left:
            closest_left.canvas_rectangle.update()
            closest_left.canvas_rectangle.config(width=removed_x2 - closest_left.x1)
        elif left_rectangle:
            left_rectangle.canvas_rectangle.update()
            left_rectangle.canvas_rectangle.place(x=0, y=10)
            left_rectangle.canvas_rectangle.config(width=left_rectangle.canvas_rectangle.winfo_width()+removed_x2)


    def find_canvas_rectangle(self, rectangle):
        for r in self.rectangles:
            if r.canvas_rectangle == rectangle:
                return r
        print("no matching rectangle")

    def click_resize(self, e):
        rectangle = self.find_canvas_rectangle(e.widget)
        logging.debug("resize {}".format(e.x))
        self.resize(rectangle, e.x, e.x_root)

    def export(self):
        result = []
        for rectangle in self.rectangles:
            pos = round(rectangle.x2 / self.canvas.winfo_width(), 3)
            result.append([pos, rectangle.image_name])
        return result

    def clean(self):
        for rectangle in self.rectangles:
            rectangle.canvas_rectangle.destroy()
        self.rectangles = []
        self.lastX = 0

    def resize(self, rectangle, width, x_pos):
        x_pos = x_pos - self.canvas_root_x
        rectangle.canvas_rectangle.update()
        rectangle.canvas_rectangle.config(width=width)
        rectangle.x2 = x_pos
        self.move_next_rectangle(rectangle)

    def move_next_rectangle(self, input_rectangle):
        next_rectangle = self.get_next_rectangle(input_rectangle.index)
        if next_rectangle:
            next_rectangle.canvas_rectangle.place(x=input_rectangle.x2, y=10)
            next_rectangle.canvas_rectangle.config(width=next_rectangle.x2-input_rectangle.x2)
            logging.debug("move next rectangle {} {} ".format(input_rectangle.x2, next_rectangle.x2))
        else:
            logging.debug("no rectangle after {} ".format(input_rectangle.index))

    def get_next_rectangle(self, index):
        if index < len(self.rectangles):
            for rectangle in self.rectangles:
                logging.info("next rectangle index {}".format(rectangle.index))
                if index + 1 == rectangle.index:
                    return rectangle
        return None


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
