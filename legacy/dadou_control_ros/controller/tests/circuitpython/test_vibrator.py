import logging
import logging.config
import os
import random
import time
import unittest
import board

from controller.circuit_py.vibrator import Vibrator
from controller.control_config import config
from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME


class MyTestCase(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "tests"))
    def test_vibrator(self):
        vibrator = Vibrator(board.D14)
        logging.info("start test vibrator")

        while True:
            vibrator.process()
            time.sleep(0.01)
            ran = random.randrange(0, 1000)
            if ran > 990:
                vibrator.click()
    def test_gui(self):
        if os.environ.get('DISPLAY'):
            print(True)
        else:
            print(False)

if __name__ == '__main__':
    unittest.main()
