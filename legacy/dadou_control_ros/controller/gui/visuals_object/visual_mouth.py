from controller.gui.visuals_object.visual_object import VisualObject
from dadou_utils_ros.utils_static import MOUTH


class VisualMouth(VisualObject):
    TYPE = MOUTH
    WIDTH = 24
    HEIGHT = 16

    def __init__(self):
        super().__init__(MOUTH)

