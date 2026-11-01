

from sqlobject import SQLObject, StringCol, IntCol
from sqlobject.sqlite import builder

from robot.robot_static import DB_DIRECTORY, AUDIOS_DB
from robot.robot_config import config

# Connexion à une base de données SQLite persistante
db_file = "{}{}".format(config[DB_DIRECTORY], config[AUDIOS_DB])
connection = builder()(filename=db_file)


class AudioDB(SQLObject):
    _connection = connection

    name = StringCol(unique=True)
    keys = StringCol(default=None)
    path = StringCol()
    length = IntCol(default=None)
    expression = StringCol(default=None)
