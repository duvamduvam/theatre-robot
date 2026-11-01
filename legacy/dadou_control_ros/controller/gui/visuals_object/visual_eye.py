from controller.gui.visuals_object.visual_object import VisualObject
from controller.control_static import EYE, EYES


class VisualEye(VisualObject):

    TYPE = EYES
    WIDTH = 8
    HEIGHT = 8

    def __init__(self):
        super().__init__(EYE)

