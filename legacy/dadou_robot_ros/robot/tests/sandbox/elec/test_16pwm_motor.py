import adafruit_pca9685
import board
import busio

#from rpi_python_drv8825.stepper import StepperMotor
from robot.robot_static import HEAD_PWM_NB
from robot.robot_config import config
from robot.tests.sandbox.conf_test import TestSetup

TestSetup()

import time
import unittest


class PWMMotorTest(unittest.TestCase):
    TestSetup()

    #kit = ServoKit(channels=16)

    #kit.servo[15].set_pulse_width_range(1000, 2000)
    #kit.servo[14].set_pulse_width_range(1000, 2000)
    #kit.frequency = 60

    #MAX = 65535
    MAX = 0xffff
    i2c = busio.I2C(board.SCL, board.SDA)
    pca9685 = adafruit_pca9685.PCA9685(i2c)
    pca9685.frequency = 60

    pwm_motor1 = pca9685.channels[1]
    pwm_motor1.duty_cycle = 0

    dir_motor1 = pca9685.channels[0]
    dir_motor1.duty_cycle = 0

    pwm_motor2 = pca9685.channels[2]
    pwm_motor2.duty_cycle = 0

    dir_motor2 = pca9685.channels[3]
    dir_motor2.duty_cycle = 0

    neck = pca9685.channels[config[HEAD_PWM_NB]]
    neck.duty_cycle = 0

    def test_left_run(self):
        self.dir_motor1.duty_cycle = self.MAX
        self.pwm_motor1.duty_cycle = 10000
        time.sleep(15)
        self.dir_motor1.duty_cycle = 0
        self.pwm_motor1.duty_cycle = 10000
        time.sleep(15)
        self.pwm_motor1.duty_cycle = 0

    def test_neck_run(self):
        for i in range(3):
            self.neck.duty_cycle = 0
            self.neck.duty_cycle = 10000
            time.sleep(5)

    def test_both(self):
        self.dir_motor1.duty_cycle = 0
        self.increase_decrease(self.pwm_motor1)
        self.dir_motor1.duty_cycle = self.MAX
        self.increase_decrease(self.pwm_motor1)
        self.pwm_motor1.duty_cycle = 0

        self.dir_motor2.duty_cycle = 0
        self.increase_decrease(self.pwm_motor2)
        self.dir_motor2.duty_cycle = self.MAX
        self.increase_decrease(self.pwm_motor2)
        self.pwm_motor2.duty_cycle = 0

    def increase_decrease(self, pwm):
        for i in range(5000, 25000, 2):
            pwm.duty_cycle = i

        #    # Decrease brightness:
        for i in range(25000, 5000, -2):
            pwm.duty_cycle = i


    def test_init(self):
        step = self.pca9685.channels[0]
        step.duty_cycle = self.MAX

        dir = self.pca9685.channels[1]
        dir.duty_cycle = self.MAX

        enable = self.pca9685.channels[2]
        enable.duty_cycle = self.MAX


    def test_stepper(self):

        durationFwd = 5000  # This is the duration of the motor spinning. used for forward direction
        durationBwd = 5000  # This is the duration of the motor spinning. used for reverse direction
        #
        delay = 0.001  # This is actualy a delay between PUL pulses - effectively sets the mtor rotation speed.
        print('Speed set to ' + str(delay))
        #
        cycles = 1000  # This is the number of cycles to be run once program is started.
        cyclecount = 0  # This is the iteration of cycles to be run once program is started.
        print('number of Cycles to Run set to ' + str(cycles))

        step = self.pca9685.channels[0]
        step.duty_cycle = 0

        dir = self.pca9685.channels[1]
        dir.duty_cycle = self.MAX

        enable = self.pca9685.channels[2]
        enable.duty_cycle = 0

        #
        time.sleep(.5)  # pause due to a possible change direction


        print('DIR set to LOW - Moving Forward at ' + str(delay))
        print('Controller PUL being driven.')
        for x in range(durationFwd):
            step.duty_cycle = 0
            time.sleep(.0001)
            step.duty_cycle = self.MAX
            time.sleep(.05)


        enable.duty_cycle = self.MAX
        time.sleep(.5)  #

        #for i in range(3):
        #    step.duty_cycle = self.MAX
        #    time.sleep(0.208)
        #    step.duty_cycle = 0
        #    time.sleep(1)
        #step.duty_cycle = 500

        #time.sleep()




if __name__ == '__main__':
    unittest.main()
