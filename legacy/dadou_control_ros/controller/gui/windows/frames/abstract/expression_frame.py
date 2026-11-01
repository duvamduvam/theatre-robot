import logging

from controller.files.file_manager import FileManager
from controller.gui.windows.frames.abstract.rectangle_frame import RectangleFrame


class ExpressionFrame(RectangleFrame):
    def __init__(self, parent, name, color, visual_type):
        items = FileManager.list_folder_files(visual_type.TYPE)

        super().__init__(parent, name, color, items)

