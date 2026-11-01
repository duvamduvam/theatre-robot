# Here we will import all the extra functionality desired
from time import *

from adafruit_servokit import ServoKit

# Below is an initialising statement stating that we will have access to 16 PWM channels of the HAT and to summon them we will use | kit |
kit = ServoKit(channels=16)

# Below desides the initial angle that the servo which is attatched to Port 0 will be. In this case we will make it zero degrees.
#kit.servo[0].angle = 0
#kit.frequency(60)
# Below will create an infinite loop
while True:
    kit.servo[6].angle = 0
    kit.servo[7].angle = 0
    sleep(5)

    kit.servo[6].angle = 180
    kit.servo[7].angle = 180
    sleep(5)

    kit.servo[6].angle = 90
    kit.servo[7].angle = 90
    sleep(5)

    """kit.servo[0].angle = 120
    sleep(2)
    kit.servo[0].angle = 60
    sleep(2)"""
    #for i in range(180):
    #    kit.servo[0].angle = i
    #    sleep(0.05)


# Below will make the system wait for 3 seconds
sleep(3)
# Below will rotate the Standard servo to the 180 degree point
kit.servo[0].angle = 0