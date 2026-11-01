
import json
import logging

from dadou_utils_ros.utils_static import JSON_DIRECTORY, BASE_PATH


class AbstractJsonManager:

    def __init__(self, config, json_keys):
        self.config = config
        self.json_files = {}
        for json_key in json_keys:
            self.json_files[json_key] = self.open_json(json_key)

    def get_json_file(self, name):
        return self.json_files[name]

    def get_json_keys_list(self, json_file):
        return self.json_files[json_file].keys()

    def get_element_from_key(self, json_file, key, value):
        for result in self.json_files[json_file]:
            if value in result[key]:
                return result

    #TODO simplify with the fileUtils.open_json
    def open_json(self, file_name, directory=""):
        path = self.config[JSON_DIRECTORY] + directory + file_name
        logging.info("import json {}".format(path))
        if ".json" not in path:
            path += ".json"
        with open(path, 'r') as json_file:
            return json.load(json_file)

    def write_json(self, datas, file_name, directory=""):
        path = self.config[JSON_DIRECTORY] + directory + file_name
        with open(path, "w") as outfile:
            outfile.write(json.dumps(datas, indent=4, sort_keys=True))

    # ATTENTION : get_attributs_list et delete_item sont APPELÉES en vrai par
    # dadou_control_ros (sequences_window.py / control_json_manager.py) mais ne
    # sont pour l'instant que des ébauches commentées ci-dessous -> ces chemins
    # de la télécommande lèvent une AttributeError. À décommenter/implémenter
    # avant usage, ne PAS supprimer ces stubs (fil à ne pas perdre).
    """def get_attributs_list(self, json_file, key):
        attributs_list = []
        for file in self.json_files[json_file]:
            attributs_list.append(file[key])
        return attributs_list"""

    """def delete_item(self, items, name):
        for item in items:
            if item[NAME] == name:
                items.remove(item)
                return
        logging.error('name {} not found in items {}'.format(name, items))"""

