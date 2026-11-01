import logging
import tkinter as tk
import tkinter

from controller.control_config import CYAN
from controller.files.file_manager import FileManager
from controller.gui.gui_utils import GuiUtils
from controller.gui.visuals_object.visual_eye import VisualEye
from controller.gui.visuals_object.visual_mouth import VisualMouth

from dadou_utils_ros.utils_static import MOUTH
from controller.control_static import EYE, VISUALS, ICON


class GalleryWidget(tkinter.Canvas):
    def __init__(self, parent, zoom, *args, **kwargs):
        tk.Canvas.__init__(self, parent, bg=CYAN, *args, **kwargs)

        self.xpos = 10
        self.ypos = 10
        self.ymargin = 10
        self.zoom = 8

    def show_folder(self, path):
        visual_type = None
        if EYE in path or ICON in path:
            visual_type = VisualEye()
        if MOUTH in path:
            visual_type = VisualMouth()

        #folder = ControlFactory().base_path+'/'+VISUALS+'/'+path
        items = FileManager.list_folder_files(path)

        xpos = 10
        ypos = 10
        ymargin = 10
        self.images = []
        for item in items:
            self.images.append(GuiUtils.set_image(self, xpos, ypos, path, item, self.zoom))
            ypos += ymargin + visual_type.HEIGHT * self.zoom