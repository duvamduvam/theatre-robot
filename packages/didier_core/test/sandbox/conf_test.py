import logging
import logging.config
import os
import platform

from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import RPI_TYPE, LOGGING_TEST_FILE_NAME
from vision.vision_config import config


class TestSetup:

    def __init__(self):
        # check rapsberry
        logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test"))

        if platform.machine() not in RPI_TYPE:
            path = "/home/dadou/Nextcloud/rosita/dadoutils/didier-dadoutils"
            os.chdir(path)
            print(os.path.join(path))

        #self.left_arm = robot_factory.left_arm
        #self.right_arm = robot_factory.right_arm
        #self.neck = robot_factory.neck
        #self.wheel = robot_factory.wheel

