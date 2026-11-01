
import logging

from sqlobject import SQLObject, StringCol, IntCol, PickleCol, BoolCol
from sqlobject.dberrors import DuplicateEntryError
from sqlobject.sqlite import builder

from robot.robot_static import DB_DIRECTORY, SEQUENCES_DB
from dadou_utils_ros.utils_static import NAME, SEQUENCES
from robot.robot_config import config

# Connexion à une base de données SQLite persistante
db_file = "{}{}".format(config[DB_DIRECTORY], config[SEQUENCES_DB])
connection = builder()(filename=db_file)


class ExpressionsDB(SQLObject):
    _connection = connection

    name = StringCol(unique=True)
    keys = BoolCol(default=None)
    duration = IntCol()
    loop = StringCol(default=None)
    faces = StringCol(default=None)
    left_eye = StringCol(default=None)
    right_eye = StringCol(default=None)
    mouths = StringCol(default=None)


    def print(self):
        # Log the values of all fields dynamically
        for field, col in self.sqlmeta.columns.items():
            print(f"{field}: {getattr(self, field)}")

    @staticmethod
    def insert(sequence_data):
        try:
            ExpressionsDB(**sequence_data)
            logging.info(f"Inserted sequence: {sequence_data[NAME]}")
        except DuplicateEntryError as e:
            logging.error(f"Duplicate entry for expression: {sequence_data[NAME]}")
            # Continuer l'exécution malgré l'erreur de duplication