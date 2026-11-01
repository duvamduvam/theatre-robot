
import json
import logging
import logging.config
import os
import unittest
import random

from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.logging_conf import LoggingConf
from robot.robot_static import TYPES
from dadou_utils_ros.utils_static import SEQUENCES_DIRECTORY, NAME, KEYS, DURATION, FACES, \
    ROBOT_LIGHTS, LEFT_EYE, RIGHT_EYE, LEFT_ARM, RIGHT_ARM, NECK, LOGGING_TEST_FILE_NAME
from robot.db.sequences_db import SequencesDB
from robot.files.robot_json_manager import RobotJsonManager
from robot.robot_config import config


class TestDbExpression(unittest.TestCase):
    print(config[LOGGING_TEST_FILE_NAME])
    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test db expression"))
    robot_json_manager = RobotJsonManager(config)
    expressions = robot_json_manager.open_json(self.json_file)
    for expression in expressions:
        self.sequences_name[seq_key][NAME] = seq_key

    import json
    import logging
    import logging.config
    import os
    import unittest
    import random

    from dadou_utils_ros.files.files_utils import FilesUtils
    from dadou_utils_ros.logging_conf import LoggingConf
    from robot.robot_static import TYPES
    from dadou_utils_ros.utils_static import SEQUENCES_DIRECTORY, NAME, KEYS, DURATION, FACES, \
        ROBOT_LIGHTS, LEFT_EYE, RIGHT_EYE, LEFT_ARM, RIGHT_ARM, NECK, LOGGING_TEST_FILE_NAME
    from robot.db.sequences_db import SequencesDB
    from robot.robot_config import config

    class MyTestCase(unittest.TestCase):
        print(config[LOGGING_TEST_FILE_NAME])
        logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "test db sequences"))

        def test_drop(self):

            logging.info("drop base")
            SequencesDB.dropTable()

        def test_import_json(self):

            logging.info("import json in db")

            if not SequencesDB.tableExists():
                SequencesDB.createTable()
            else:
                SequencesDB.dropTable()
                SequencesDB.createTable()

            sequences_files = FilesUtils.get_folder_files(config[SEQUENCES_DIRECTORY])
            for sequence_file in sequences_files:
                json_sequence = FilesUtils.open_json(sequence_file, 'r')
                logging.info(json_sequence)

                name = os.path.basename(sequence_file).replace(".json", "")
                db_fields = {NAME: name}
                if KEYS in json_sequence:
                    db_fields[KEYS] = json_sequence[KEYS]
                if DURATION in json_sequence:
                    db_fields[DURATION] = int(json_sequence[DURATION])  # Conversion en entier
                if TYPES in json_sequence:
                    db_fields[TYPES] = json.dumps(json_sequence[TYPES])
                if FACES in json_sequence:
                    db_fields[FACES] = json.dumps(json_sequence[FACES])
                    logging.info(db_fields)
                if ROBOT_LIGHTS in json_sequence:
                    db_fields[ROBOT_LIGHTS] = json.dumps(json_sequence[ROBOT_LIGHTS])
                if LEFT_EYE in json_sequence:
                    db_fields[LEFT_EYE] = json.dumps(json_sequence[LEFT_EYE])
                if RIGHT_EYE in json_sequence:
                    db_fields[RIGHT_EYE] = json.dumps(json_sequence[RIGHT_EYE])
                if LEFT_ARM in json_sequence:
                    db_fields[LEFT_ARM] = json.dumps(json_sequence[LEFT_ARM])
                if RIGHT_ARM in json_sequence:
                    db_fields[RIGHT_ARM] = json.dumps(json_sequence[RIGHT_ARM])
                if NECK in json_sequence:
                    db_fields[NECK] = json.dumps(json_sequence[NECK])

                # Création de l'objet SequencesDB avec les champs conditionnels
                SequencesDB.insert(sequence_data=db_fields)

            # for seq in SequencesDB.select():
            #    seq.print()

        def test_raed_seq(self):
            for seq in SequencesDB.select():
                seq.print()

        def test_insert_dict(self):
            name = os.path.basename("test_{}").format(random.randint(1, 1000))
            db_fields = {NAME: name}
            db_fields[DURATION] = random.randint(1, 1000)  # Conversion en entier

            face = [
                [
                    0.3,
                    "love"
                ],
                [
                    0.6,
                    "love"
                ],
                [0.9,
                 "love"
                 ]
            ],

            db_fields[FACES] = str(face)

            # Création de l'objet SequencesDB avec les champs conditionnels
            SequencesDB.insert(sequence_data=db_fields)

    if __name__ == '__main__':
        unittest.main()

    def test_drop(self):

        logging.info("drop base")
        SequencesDB.dropTable()

    def test_import_json(self):

        logging.info("import json in db")

        if not SequencesDB.tableExists():
            SequencesDB.createTable()
        else:
            SequencesDB.dropTable()
            SequencesDB.createTable()

        sequences_files = FilesUtils.get_folder_files(config[SEQUENCES_DIRECTORY])
        for sequence_file in sequences_files:
            json_sequence = FilesUtils.open_json(sequence_file, 'r')
            logging.info(json_sequence)

            name = os.path.basename(sequence_file).replace(".json", "")
            db_fields = {NAME: name}
            if KEYS in json_sequence:
                db_fields[KEYS] = json_sequence[KEYS]
            if DURATION in json_sequence:
                db_fields[DURATION] = int(json_sequence[DURATION])  # Conversion en entier
            if TYPES in json_sequence:
                db_fields[TYPES] = json.dumps(json_sequence[TYPES])
            if FACES in json_sequence:
                db_fields[FACES] = json.dumps(json_sequence[FACES])
                logging.info(db_fields)
            if ROBOT_LIGHTS in json_sequence:
                db_fields[ROBOT_LIGHTS] = json.dumps(json_sequence[ROBOT_LIGHTS])
            if LEFT_EYE in json_sequence:
                db_fields[LEFT_EYE] = json.dumps(json_sequence[LEFT_EYE])
            if RIGHT_EYE in json_sequence:
                db_fields[RIGHT_EYE] = json.dumps(json_sequence[RIGHT_EYE])
            if LEFT_ARM in json_sequence:
                db_fields[LEFT_ARM] = json.dumps(json_sequence[LEFT_ARM])
            if RIGHT_ARM in json_sequence:
                db_fields[RIGHT_ARM] = json.dumps(json_sequence[RIGHT_ARM])
            if NECK in json_sequence:
                db_fields[NECK] = json.dumps(json_sequence[NECK])

            # Création de l'objet SequencesDB avec les champs conditionnels
            SequencesDB.insert(sequence_data=db_fields)

        #for seq in SequencesDB.select():
        #    seq.print()

    def test_raed_seq(self):
        for seq in SequencesDB.select():
            seq.print()

    def test_insert_dict(self):
        name = os.path.basename("test_{}").format(random.randint(1, 1000))
        db_fields = {NAME: name}
        db_fields[DURATION] = random.randint(1, 1000)  # Conversion en entier

        face = [
            [
                0.3,
                "love"
            ],
            [
                0.6,
                "love"
            ],
            [0.9,
             "love"
             ]
        ],

        db_fields[FACES] = str(face)

        # Création de l'objet SequencesDB avec les champs conditionnels
        SequencesDB.insert(sequence_data=db_fields)


if __name__ == '__main__':
    unittest.main()




def load_keys_and_names_sequences(self, json_manager):
    sequences = json_manager.open_json(self.json_file)
    for seq_key in sequences:
        if KEYS in sequences[seq_key].keys():
            for key in sequences[seq_key][KEYS]:
                self.sequences_key[key] = sequences[seq_key]
        self.sequences_name[seq_key] = sequences[seq_key]
        self.sequences_name[seq_key][NAME] = seq_key