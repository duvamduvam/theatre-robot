from dadou_utils_ros.utils_static import NECK
from controller.control_static import NECKS, DATAS

from controller.gui.windows.frames.abstract.abstract_sequence_frame import AbstractSequenceFrame


class NeckFrame(AbstractSequenceFrame):
    def __init__(self, parent, color, **kwargs):
        super().__init__(parent, NECK, color, **kwargs)
        self.points = []
        self.lastX = 0
        self.canvas.bind("<Button-1>", self.create_circle_click)

        self.canvas.update()
        if DATAS in kwargs:
            self.load(kwargs[DATAS])

    def create_circle(self, x, y):
        circle = self.canvas.create_oval(x, y, x+10, y+10, width=3, fill="#476042")
        self.canvas.tag_bind(circle, '<Button-3>', self.delete)
        point = [round(x/self.canvas.winfo_width(), 2), round((self.canvas.winfo_height()-y)/self.canvas.winfo_height(), 2)]
        self.points.append(point)

    def create_circle_click(self, e):
        self.create_circle(e.x, e.y)

    def create_circle_json(self, x, y):
        self.create_circle(int(self.canvas.winfo_width()*x),
                           int(self.canvas.winfo_height()-(self.canvas.winfo_height()*y)))

    def delete(self, e):
        circle = self.canvas.find_closest(e.x, e.y)
        self.canvas.delete(circle)

    def clear(self):
        self.canvas.delete("all")
        self.points = []
        self.create_timeline()
        self.lastX = 0

    def load(self, datas):
        self.clear()
        for neck in datas:
            self.create_circle_json(neck[0], neck[1])