from dadou_utils_ros.misc import Misc
from dadou_utils_ros.singleton import SingletonMeta


class HighlightedRectangle(metaclass=SingletonMeta):
    rectangle = None
    zoom = 8

    @staticmethod
    def update_rectangle(rectangle):
            if HighlightedRectangle.rectangle and HighlightedRectangle.rectangle.canvas_rectangle:
                HighlightedRectangle.rectangle.canvas_rectangle.configure(bg=Misc.random_color())
            HighlightedRectangle.rectangle = rectangle
