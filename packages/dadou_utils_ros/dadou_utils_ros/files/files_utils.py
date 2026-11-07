import json
from os import listdir, path
from os.path import isfile, join


class FilesUtils:

    @staticmethod
    def get_folder_files(folder, recursive=True):
        files = []
        for file in listdir(folder):
            full_path = join(folder, file)
            if path.isfile(full_path):
                files.append(full_path)
            if path.isdir(full_path) and recursive:
                files.extend(FilesUtils.get_folder_files(full_path))
        return files

    @staticmethod
    def get_folder_files_name(folder):
        return [f for f in listdir(folder) if isfile(join(folder, f))]

    @staticmethod
    def open_json(file, mode):
        with open(file, mode) as json_file:
            return json.load(json_file)

    """def get_image(self, type, name):
        if type == self.EYE:
            return Image.open(self.config.base_path + self.EYE_VISUALS_PATH + name)
        if type == self.MOUTH:
            return Image.open(self.config.base_path + self.MOUTH_VISUALS_PATH + name)
        return None

    def get_folder_path(self, type):
        if type == self.EYE:
            return config.

    def get_folder_files_name(self, folder):
        return [f for f in listdir(folder) if isfile(join(folder, f))]
    """