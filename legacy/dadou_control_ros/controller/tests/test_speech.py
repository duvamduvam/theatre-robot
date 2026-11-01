import logging
import unittest
import speech_recognition as sr

class TestSpeech(unittest.TestCase):


    def test_microphone(self):
        microphones = sr.Microphone.list_microphone_names()
        i = 0
        for m in microphones:
            print("{} {}".format(i, m))
            i = i+1

        print(l)

if __name__ == '__main__':
    unittest.main()

