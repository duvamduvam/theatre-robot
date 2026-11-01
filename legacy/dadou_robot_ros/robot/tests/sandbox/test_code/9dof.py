# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time

import board

from robot.robot_static import CALIBRATION
from robot.move.bno_055_extended import BNO055Extended
from robot.robot_config import config

# If you are going to use UART uncomment these lines
# uart = board.UART()
# sensor = adafruit_bno055.BNO055_UART(uart)

last_val = 0xFFFF

i2c = board.I2C()  # uses board.SCL and board.SDA
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
#sensor = BNO055Extended(i2c, config[CALIBRATION])
#sensor = adafruit_bno055.BNO055_I2C(i2c)
sensor = BNO055Extended(i2c, config[CALIBRATION])


while True:

    #sensor.mode = adafruit_bno055.ACCONLY_MODE
    print("mode : {}".format(sensor.mode))
    print("Calibration : sys {} gyro {} accel {} and mag {} ".format(sensor.calibration_status[0],
                                                                     sensor.calibration_status[1], sensor.calibration_status[2], sensor.calibration_status[3]))

    print("Temperature: {} degrees C".format(sensor.temperature))
    """
    print(
        "Temperature: {} degrees C".format(temperature())
    )  # Uncomment if using a Raspberry Pi
    """
    print("Accelerometer (m/s^2): {}".format(sensor.acceleration))
    print("Magnetometer (microteslas): {}".format(sensor.magnetic))
    print("Gyroscope (rad/sec): {}".format(sensor.gyro))
    print("Euler angle: x {} y {} z {}".format(sensor.euler[0], sensor.euler[1], sensor.euler[2]))
    print("Quaternion: {}".format(sensor.quaternion))
    print("Linear acceleration (m/s^2): {}".format(sensor.linear_acceleration))
    print("Gravity (m/s^2): {}".format(sensor.gravity))
    print()

    time.sleep(1)
