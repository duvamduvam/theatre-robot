"""Décodage des StringTime : un payload invalide doit être refusé AVEC un log
explicite (pas d'exception avalée en silence — cause d'une session de
diagnostic perdue le 2026-07-10)."""
import logging
import unittest

from robot.nodes.payload import decode


class FakeStringTime:
    def __init__(self, msg):
        self.msg = msg


class TestDecode(unittest.TestCase):

    def test_nom_d_expression_json(self):
        self.assertEqual(decode(FakeStringTime('"calib"'), "face"), "calib")

    def test_objet_json(self):
        self.assertEqual(decode(FakeStringTime('{"brightness": 0.5}'), "robot_lights"),
                         {"brightness": 0.5})

    def test_booleen_json(self):
        # L'arrêt d'animation se publie msg: "false" (booléen JSON).
        self.assertIs(decode(FakeStringTime('false'), "animation"), False)

    def test_chaine_brute_refusee_avec_log(self):
        # Le piège historique : 'calib' sans guillemets n'est PAS du JSON.
        with self.assertLogs(level=logging.ERROR) as logs:
            self.assertIsNone(decode(FakeStringTime('calib'), "face"))
        self.assertIn("face", logs.output[0])
        self.assertIn("calib", logs.output[0])

    def test_payload_non_chaine_refuse(self):
        with self.assertLogs(level=logging.ERROR):
            self.assertIsNone(decode(FakeStringTime(None), "face"))


if __name__ == "__main__":
    unittest.main()
