import unittest

from robot_drive.joystick_mixer import translate


class MyTestCase(unittest.TestCase):

    def test_anglo_translate(self):
        left, right = translate(forward=50, turn=0)
        print("left {} right {}".format(left, right))


if __name__ == '__main__':
    unittest.main()
