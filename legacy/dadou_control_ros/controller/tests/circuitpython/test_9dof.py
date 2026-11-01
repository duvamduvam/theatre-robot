import logging
import logging.config
import time
import unittest
from unittest.mock import patch, MagicMock


from controller.circuit_py.bno055 import BNO055
from controller.control_config import config
from dadou_utils_ros.logging_conf import LoggingConf
from dadou_utils_ros.utils_static import LOGGING_TEST_FILE_NAME


class Test9dof(unittest.TestCase):

    logging.config.dictConfig(LoggingConf.get(config[LOGGING_TEST_FILE_NAME], "tests"))
    def test_get_values(self):
        dof = BNO055()
        logging.info("start test vibrator")

        while True:
            dof.process()
            time.sleep(2)

    @patch('adafruit_bno055.BNO055_I2C')
    @patch('busio.I2C')
    @patch('board.SCL')
    @patch('board.SDA')
    def test_get_values2(self, mock_sda, mock_scl, mock_i2c, mock_bno055):
        # Créez une instance simulée du capteur
        mock_bno055_instance = MagicMock()
        mock_bno055.return_value = mock_bno055_instance

        # Simulez un identifiant de puce valide
        mock_bno055_instance._read_register.return_value = 0xA0

        # Initialisez le capteur
        dof = BNO055()
        logging.info("start dof test")
        while True:
            logging.info(dof.process())
            time.sleep(1)


        # Vérifiez les lectures de valeurs
        #self.assertIsNotNone(dof)


if __name__ == '__main__':
    unittest.main()
