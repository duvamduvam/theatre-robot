import logging
import logging.config
import time
import unittest
import pytest

from controller.control_config import config
from controller.input.keyboard import KeyListener
from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME


class TestKeyboard(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "tests"))
    def test_keyboard(self):
        keyboardLister = KeyListener()
        while True:
            last_key = keyboardLister.last_key
            if last_key:
                print("last {}".format(last_key))
                time.sleep(0.01)

if __name__ == '__main__':
    unittest.main()
