"""
Raspberry Pi Pico + LSM303
Act as usb_hid,
read Accelerometer and report mouse movement.

ref:
https://docs.circuitpython.org/projects/hid/en/latest/_modules/adafruit_hid/mouse.html
"""
import logging
import time
from math import atan2, degrees
import board

import busio
from controller.circuit_py.adafruit_bno055_bis import BNO055_I2C


class BNO055:

    measure_period = 0.5
    last_time = 0

    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        self.sensor = BNO055_I2C(i2c, address=0x18)

    def vector_2_degrees(self, x, y):
        angle = degrees(atan2(y, x))
        if angle < 0:
            angle += 360
        return angle

    def get_inclination(self, _sensor):
        x, y, z = _sensor.acceleration
        return self.vector_2_degrees(x, z), self.vector_2_degrees(y, z)

    def translate(self, value, leftMin, leftMax, rightMin, rightMax):
        # Figure out how 'wide' each range is
        leftSpan = leftMax - leftMin
        rightSpan = rightMax - rightMin

        # Convert the left range into a 0-1 range (float)
        valueScaled = float(value - leftMin) / float(leftSpan)

        # Convert the 0-1 range into a value in the right range.
        return int(rightMin + (valueScaled * rightSpan))

    def two_char(self, num):
        if abs(num) < 100:
            if abs(num) > 9:
                return str(num)
            else:
                return '0'+str(num)

    def process(self):
        #if self.is_time(self.last_time, self.measure_period):

        try:
            #self.mesure = self.sensor.quaternion
            #magnetic : 0 (y -> rotation latéral) | 1
            #self.mesure = self.sensor.magnetic
            #euler : 0 (y -> rotation latéral) | 2 (z bas / haut)
            self.mesure = self.sensor.euler

            logging.info("Gyroscope (rad/sec): {}".format(self.sensor.gyro))
            logging.info("Euler angle: {}".format(self.sensor.euler))
            self.last_time = round(time.time() * 1000)
            return {"turn": self.mesure[1], "speed": self.mesure[2]}
        except Exception as e:
            print(e)

        """angle_xz, angle_yz = self.get_inclination(self.sensor)
        print("XZ angle = {:6.2f}deg   YZ angle = {:6.2f}deg".format(angle_xz, angle_yz))

        forward = self.translate(angle_yz, 340, 10, 0, 99)
        #print("forward {}".format(forward))

        turn = self.translate(angle_xz, 0, 320, 0, 99)
        #print("turn {}".format(turn))

        if self.two_char(forward) and self.two_char(turn):
            return self.two_char(forward)+self.two_char(turn)

        self.last_time = round(time.time() * 1000)"""

    @staticmethod
    def is_time(last_time, time_out) -> bool:
        #logging.debug(" last_time is int : " + str(isinstance(last_time, int)) + " -> " + str(
        #    last_time) + " timeout is int : " + str(
        #    isinstance(time_out, int)) + " -> " + str(
        #    time_out))
        current = round(time.time() * 1000)

        return ((current - last_time) - time_out) > 0

