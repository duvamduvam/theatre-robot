import logging
import os
import traceback
from os import listdir
from os.path import isfile, join

from dadou_utils_ros.utils_static import BASE_PATH
from controller.control_static import PATHS

from controller.control_config import config
from controller.control_factory import ControlFactory


class FileManager:

    SEQUENCE_FOLDER = "frames"

    @staticmethod
    def list_folder_files_type(folder_type):

        folder = config[PATHS][folder_type]
        return FileManager.list_folder_files(folder)

    @staticmethod
    def list_folder_files(folder):
        try:
            return [f for f in listdir(folder) if isfile(join(folder, f))]
        except TypeError as e:
            logging.error("type error {}".format(folder))
            traceback.print_exc()

    """@staticmethod
    def get_files_path(path):
        files = []
        for f in listdir(path):
            if isfile(join(path, f)):
                files.append(f)
        return files

    def sequences_files(self):
        return self.get_files_path(self.BASE_FOLDER+ControlStatic.JSON_DIRECTORY+self.SEQUENCE_FOLDER)
"""