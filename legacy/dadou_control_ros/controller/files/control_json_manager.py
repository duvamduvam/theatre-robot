from dadou_utils_ros.utils_static import (
    JSON_LIGHTS_BASE, SEQUENCES_DIRECTORY, JSON_EXPRESSIONS, JSON_LIGHTS, JSON_AUDIOS,
)
from controller.control_static import JSON_LIGHTS_METHODS, JSON_SPEECHS
from dadou_utils_ros.files.abstract_json_manager import AbstractJsonManager

from controller.control_config import config



class ControlJsonManager(AbstractJsonManager):

    def __init__(self):
        super().__init__(config, [config[JSON_EXPRESSIONS],
                                  config[JSON_LIGHTS_BASE], config[JSON_LIGHTS_METHODS]])
        #self.lights_base = self.open_json(config[JSON_LIGHTS_BASE], 'r')
        #self.lights = self.open_json(LIGHTS_FILE, 'r')
        #self.expressions = self.open_json(EXPRESSIONS_FILE, 'r')

    """def get_sequence(self, name):
        return self.open_json(config[SEQUENCES_DIRECTORY]+name)

    def get_expressions(self):
        return self.open_json(config[JSON_EXPRESSIONS], 'r')

    def get_expressions_names(self):
        expressions_names = []
        for e in self.get_expressions():
            expressions_names.append(e['name'])
        return expressions_names

    def get_lights(self):
        return self.open_json(config[JSON_LIGHTS], 'r')

    def get_lights_names(self):
        lights_names = []
        for e in self.get_lights():
            lights_names.append(e['name'])
        return lights_names

    def get_lights_base(self):
        #bases = self.lights['base']
        #return_values = []
        #for base in bases:
        #    return_values.append(base['name'])
        return self.lights_base

    def get_expressions_name(self, name):
        for result in self.open_json(config[JSON_EXPRESSIONS], 'r'):
            if result['name'] == name:
                return result

    def delete_expression(self, name):
        expressions = self.open_json(config[JSON_EXPRESSIONS], 'r')
        self.delete_item(expressions, name)
        with open(self.json_folder+config[JSON_EXPRESSIONS], 'w') as outfile:
            json.dump(expressions, outfile, indent=4)

    def save_expressions(self, name, duration, loop, keys, left_eyes, right_eyes, mouths):
        expressions = self.open_json(config[JSON_EXPRESSIONS], 'r')
        self.delete_item(expressions, name)
        expressions.append({"name": name, "duration": duration, "loop": Misc.to_bool(loop), "keys": Misc.convert_to_array(keys),
                            "left_eyes": left_eyes, "right_eyes": right_eyes, "mouths": mouths})
        with open(self.json_folder+config[JSON_EXPRESSIONS], 'w') as outfile:
            json.dump(expressions, outfile, indent=4)
        #expressions_w = self.open_json(EXPRESSIONS_FILE, 'w')
        #expressions_w.write(expressions)

    def save_lights(self, lights):
        #lights = self.open_json(LIGHTS_FILE, 'r')
        with open(self.json_folder+config[JSON_LIGHTS], 'w') as outfile:
            json.dump(lights, outfile, indent=4)"""

    #def get_speechs(self):
    #    return self.open_json(config[JSON_SPEECHS], 'r')
