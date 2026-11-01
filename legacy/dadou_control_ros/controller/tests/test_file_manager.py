import logging
import unittest

from files.file_manager import FileManager


class FileManagerTests(unittest.TestCase):

    logging.info("start face test")
    fileManager = FileManager()

    #@unittest.skip
    def test_get_files(self):
        files = self.fileManager.sequences_files()
        print(files)

