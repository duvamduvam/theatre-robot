import unittest

from robot.db.audio_db import AudioDB


class MyTestCase(unittest.TestCase):
    def test_audio(self):
        if not AudioDB.tableExists():
            AudioDB.createTable()

        audio1 = AudioDB(name="chanson1", path="rep1", length=30)
        audio2 = AudioDB(name="chanson2", path="rep2", length=50)

        # Récupération et affichage des personnes
        for audio in AudioDB.select():
            print(f"{audio.name} {audio.path}, {audio.length} ans")


if __name__ == '__main__':
    unittest.main()
