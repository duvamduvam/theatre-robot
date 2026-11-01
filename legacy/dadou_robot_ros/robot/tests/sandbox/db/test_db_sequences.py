import json
import logging
import logging.config
import os
import unittest
import random

from sqlobject import StringCol

from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.logging_conf import LoggingConf
from robot.robot_static import TYPES, AUDIOS_DB
from dadou_utils_ros.utils_static import SEQUENCES_DIRECTORY, NAME, KEYS, DURATION, FACES, \
    ROBOT_LIGHTS, LEFT_EYE, RIGHT_EYE, LEFT_ARM, RIGHT_ARM, NECK, LOGGING_TEST_FILE_NAME, \
    SEQUENCES, JSON_DIRECTORY, JSON_AUDIOS
from robot.db.audio_db import AudioDB
from robot.db.sequences_db import SequencesDB
from robot.db.db_manager import DBManager

from robot.robot_config import config


class MyTestCase(unittest.TestCase):
    print(config[LOGGING_TEST_FILE_NAME])
    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test db sequences"))

    def test_drop(self):

        logging.info("drop base")
        SequencesDB.dropTable()


    def test_import_json_sequence(self):
        sequences_files = FilesUtils.get_folder_files(config[SEQUENCES_DIRECTORY])
        seq = SequencesDB

        db_manager = DBManager()
        db_manager.multi_json_import(seq, sequences_files, create=True)

        row = db_manager.get_by_field(cls=seq,  key=seq.q.name, value="speak")

        db_manager.print(row)

    def test_import_json_audio(self):
        audio_file = config[JSON_DIRECTORY]+config[JSON_AUDIOS]

        seq = AudioDB

        db_manager = DBManager()
        db_manager.json_import_keys(seq, audio_file, create=True)

        row = db_manager.get_by_field(cls=seq,  key=seq.q.name, value="stop")

        db_manager.print(row)

    def test_modules(self):
        print(globals())

    def test_create_db(self):
        if not SequencesDB.tableExists():
            SequencesDB.dropTable()
        fields = {NAME:StringCol(unique=True), TYPES:StringCol(default=None)}
        SequencesDB(fields)

        SequencesDB.createTable()
        #seq_db.dropTable()
        #seq_db.createTable()





if __name__ == '__main__':
    unittest.main()
