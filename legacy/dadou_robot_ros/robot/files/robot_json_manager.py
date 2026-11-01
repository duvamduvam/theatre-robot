import logging

from dadou_utils_ros.files.abstract_json_manager import AbstractJsonManager
from robot.robot_static import JSON_COLORS, JSON_RELAYS, JSON_NOTES, JSON_AUDIOS_DATAS
from dadou_utils_ros.utils_static import JSON_AUDIOS, JSON_EXPRESSIONS, JSON_LIGHTS
from dadou_utils_ros.utils_static import JSON_LIGHTS_BASE

from robot.robot_config import config

class RobotJsonManager(AbstractJsonManager):
    logging.info("start json manager")

    audios = None
    audio_seq = None
    colors = None
    config = None
    expressions = None
    lights = None
    lights_seq = None
    mappings = None
    relays = None
    visual = None

    def __init__(self, config):
        self.config = config
        component = [self.config[JSON_AUDIOS], self.config[JSON_COLORS], self.config[JSON_EXPRESSIONS],\
                self.config[JSON_LIGHTS], config[JSON_LIGHTS_BASE], self.config[JSON_RELAYS], self.config[JSON_NOTES], self.config[JSON_AUDIOS_DATAS]]

        super().__init__(config, component)
