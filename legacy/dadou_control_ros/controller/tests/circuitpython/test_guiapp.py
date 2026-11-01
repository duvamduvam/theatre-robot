import logging
import logging.config
import time
import unittest
from os import wait

from controller.control_config import config
from controller.gui.pillow.TkPillowGui import PillowGuiApp
from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME


class TestOled(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "tests"))
    def test_oled(self):
        app = PillowGuiApp(None)
        while True:
            app.process()
            time.sleep(0.1)


if __name__ == '__main__':
    unittest.main()
