import unittest
import logging
import logging.config
import unittest

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME, AUDIO
from didier_core.actions.audio_manager import AudioManager
from didier_core.files.robot_json_manager import RobotJsonManager
from didier_core.robot_config import config


class TestAudio(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test_face"))
    robot_json_manager = RobotJsonManager(config)
    audio_manager = AudioManager(config, robot_json_manager)
    def test_sound(self):
        self.audio_manager.update({AUDIO: "street/promotion-vie-eternelle.mp3"})


if __name__ == '__main__':
    unittest.main()
