import json
import logging
import os

from sqlobject import SQLObject, StringCol, IntCol, PickleCol, BoolCol
from sqlobject.dberrors import DuplicateEntryError
from sqlobject.sqlite import builder

from dadou_utils_ros.files.files_utils import FilesUtils
from robot.robot_static import DB_DIRECTORY, SEQUENCES_DB, TYPES
from dadou_utils_ros.utils_static import NAME, DURATION, KEYS, FACES, ROBOT_LIGHTS, LEFT_EYE, \
    RIGHT_EYE, LEFT_ARM, RIGHT_ARM, NECK, SEQUENCES
from robot.robot_config import config

# Connexion à une base de données SQLite persistante
db_file = "{}{}".format(config[DB_DIRECTORY], config[SEQUENCES_DB])
connection = builder()(filename=db_file)


class SequencesDB(SQLObject):
    _connection = connection

    name = StringCol(unique=True)
    keys = StringCol(default=None)
    duration = IntCol()
    types = StringCol(default=None)
    faces = StringCol(default=None)

    lights = StringCol(default=None)
    robot_lights = StringCol(default=None)

    left_eye = StringCol(default=None)
    right_eye = StringCol(default=None)
    left_arm = StringCol(default=None)
    right_arm = StringCol(default=None)
    neck = StringCol(default=None)
    wheels = StringCol(default=None)

    audio = StringCol(default=None)
    audios = StringCol(default=None)
    audio_name = StringCol(default=None)
    audio_path = StringCol(default=None)

    loop = BoolCol(default=False)


