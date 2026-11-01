import json
import logging
import os

from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.utils_static import NAME


class DBManager:

    #tables = [SequencesDB]

    @staticmethod
    def print(row):
        # Log the values of all fields dynamically
        for field, col in row.sqlmeta.columns.items():
            logging.info(f"{field}: {getattr(row, field)}")

    def get_by_field(self, cls, key, value):
        res = cls.select(key == value)
        if res.count() > 0:
            return res[0]



    @staticmethod
    def create_table(cls, create):
        if not cls.tableExists():
            cls.create_table()

        if create:
            cls.dropTable()
            cls.create_table()
    @staticmethod
    def insert(cls, db_data):
        db_fields = {}
        for k, v in db_data.items():
            if isinstance(v, dict) or isinstance(v, list):
                db_fields[k] = json.dumps(v)
            else:
                db_fields[k] = v
        try:
            logging.info(f"Inserted entry: {db_fields}")
            return cls(**db_fields)
        except Exception as e:
            logging.error("Error adding {} => {}".format(db_fields, e))

    @staticmethod
    def multi_json_import(cls, json_files, create=False):
        logging.info("import json in db")

        for file_path in json_files:
            DBManager.json_import(cls, file_path, create)
            create = False

    def json_import(self, cls, file_path, create=False):

        self.create_table(cls, create)

        file = FilesUtils.open_json(file_path, 'r')
        logging.info(file)

        file[NAME] = os.path.basename(file_path).replace(".json", "")

        # Création de l'objet SequencesDB avec les champs conditionnels
        DBManager.insert(cls, db_data=file)

    def json_import_keys(self, cls, file_path, create=False):

        self.create_table(cls, create)

        file = FilesUtils.open_json(file_path, 'r')
        logging.info(file)

        datas = {}
        for k, v in file.items():
            v[NAME] = k
            DBManager.insert(cls, db_data=v)

        # Création de l'objet SequencesDB avec les champs conditionnels