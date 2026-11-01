from dadou_utils_ros.utils_static import WHEELS
from controller.control_static import DATAS

from controller.gui.windows.frames.abstract.abstract_sequence_frame import AbstractSequenceFrame


class WheelsFrame(AbstractSequenceFrame):
    def __init__(self, parent, color, **kwargs):

        self.points = []

        self.UP_LINE_Y = 37
        self.MIDDLE_Y = 75
        self.DOWN_LINE_Y = 112

        super().__init__(parent, WHEELS, color, **kwargs)

        self.create_lines()

        self.canvas.update()
        if DATAS in kwargs:
            self.load(kwargs[DATAS])

    def create_lines(self):
        left = self.canvas.create_line(15, self.UP_LINE_Y, self.winfo_width()-15, self.UP_LINE_Y, width=3)
        right = self.canvas.create_line(15, self.MIDDLE_Y, self.winfo_width()-15, self.MIDDLE_Y, width=3)
        self.canvas.create_line(15, self.DOWN_LINE_Y, self.winfo_width() - 15, self.DOWN_LINE_Y, width=3)

        self.canvas.bind("<Button-1>", self.create_wheels_point_click)

    def create_wheels_point_click(self, e):
        print("create_wheels_point x: "+str(e.x) + " y : "+str(e.y))

        y2 = self.UP_LINE_Y if e.y > (self.UP_LINE_Y+self.DOWN_LINE_Y)/2 else self.DOWN_LINE_Y
        self.create_wheels_point(e.x, e.y, y2)

    def create_wheels_point(self, x, y1, y2):
        self.create_point(x, y1, y1 + 5)
        self.create_point(x, y2, y2 + 5)
        line = self.canvas.create_line(x+3, y1, x+3, y2, dash=(5, 1))
        self.canvas.tag_bind(line, '<Enter>', self.user_move)
        self.points.append([x, y1, y2])


    def create_point_json(self, x, y1, y2):
        X = self.canvas.winfo_width() * x
        if y1 == 0:
            Y1 = self.UP_LINE_Y
        elif y1 > 0:
            Y1 = self.UP_LINE_Y - self.UP_LINE_Y * y1
        else:
            Y1 = self.UP_LINE_Y + self.UP_LINE_Y * abs(y1)

        if y2 == 0:
            Y2 = self.DOWN_LINE_Y
        elif y2 > 0:
            Y2 = self.DOWN_LINE_Y - self.UP_LINE_Y * y2
        else:
            Y2 = self.DOWN_LINE_Y + self.UP_LINE_Y * abs(y2)

        self.create_wheels_point(X, Y1, Y2)

    def create_point(self, x, y1, y2):
        self.canvas.create_oval(x, y1, x+5, y2, width=6, fill="#476042")

    def clear(self):
        if self.canvas:
            self.canvas.delete("all")
            self.create_timeline()
            self.create_lines()
            self.points = []

    def load(self, datas):
        self.clear()
        for wheel in datas:
            self.create_point_json(wheel[0], wheel[1], wheel[2])

    def export(self):
        export_points = []
        for point in self.points:
            left = point[1] if point[1] < point[2] else point[2]
            right = point[1] if point[1] > point[2] else point[2]
            time = point[0] / self.canvas.winfo_width()

            if left > self.UP_LINE_Y:
                left = -(left - self.UP_LINE_Y)/self.UP_LINE_Y
            else:
                left = (self.UP_LINE_Y - left)/self.UP_LINE_Y

            if right > self.DOWN_LINE_Y:
                right = -(right - self.DOWN_LINE_Y)/self.UP_LINE_Y
            else:
                right = (self.UP_LINE_Y- (right - self.MIDDLE_Y))/self.UP_LINE_Y

            export_points.append([round(time, 2), round(left, 2), round(right, 2)])
        return export_points

    def user_move(self, e):
        line = self.canvas.find_closest(e.x, e.y)
        self.canvas.itemconfigure(line, width=10)
        self.canvas.move(line, e.x, 0)

