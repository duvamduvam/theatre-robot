"""
Raspberry Pi Pico + LSM303
Act as usb_hid,
read Accelerometer and report mouse movement.

ref:
https://docs.circuitpython.org/projects/hid/en/latest/_modules/adafruit_hid/mouse.html
"""
import time
from math import atan2, degrees
import board
import adafruit_lsm303_accel
import adafruit_lsm303dlh_mag
import busio
import usb_hid
from adafruit_hid.mouse import Mouse

mouse = Mouse(usb_hid.devices)

SDA=board.GP0
SCL=board.GP1
i2c = busio.I2C(SCL,SDA)  # uses board.SCL and board.SDA

sensor = adafruit_lsm303_accel.LSM303_Accel(i2c)
mag = adafruit_lsm303dlh_mag.LSM303DLH_Mag(i2c)
def vector_2_degrees(x, y):
    angle = degrees(atan2(y, x))
    if angle < 0:
        angle += 360
    return angle

def get_inclination(_sensor):
    x, y, z = _sensor.acceleration
    return vector_2_degrees(x, z), vector_2_degrees(y, z)

def translate(value, leftMin, leftMax, rightMin, rightMax):
    # Figure out how 'wide' each range is
    leftSpan = leftMax - leftMin
    rightSpan = rightMax - rightMin

    # Convert the left range into a 0-1 range (float)
    valueScaled = float(value - leftMin) / float(leftSpan)

    # Convert the 0-1 range into a value in the right range.
    return rightMin + (valueScaled * rightSpan)


while True:
    angle_xz, angle_yz = get_inclination(sensor)
    print("XZ angle = {:6.2f}deg   YZ angle = {:6.2f}deg".format(angle_xz, angle_yz))
    #print(angle_xz, angle_yz)
    #print("Magnetometer (micro-Teslas)): X=%0.3f Y=%0.3f Z=%0.3f"%mag.magnetic)
    #print("")

    #if angle_yz < 170:
    forward = translate(angle_yz, 300, 85, -10, 10)
    print("forward {}".format(forward))

    turn = translate(angle_xz, 0, 180, -10, 10)
    print("turn {}".format(turn))

    #LEFT/RIGHT
    """if angle_yz > 85:
        mouse.move(x=+3)
    elif angle_yz > 50:
        mouse.move(x=+1)
    elif angle_yz < 60:
        mouse.move(x=-3)
    elif angle_yz < 75:
        mouse.move(x=-1)

    #UP/DOWN
    if angle_yz > 120:
        mouse.move(y=-3)
    elif angle_yz > 105:
        mouse.move(y=-1)
    elif angle_yz < 60:
        mouse.move(y=+3)
    elif angle_yz < 75:
        mouse.move(y=+1)
    """
    #LEFT/RIGHT
    #if angle_xz > 120:
    #    mouse.move(x=+3)
    #elif angle_xz > 105:
    #    mouse.move(x=+1)
    #elif angle_xz < 60:
    #    mouse.move(x=-3)
    #elif angle_xz < 75:
    #    mouse.move(x=-1)

    #UP/DOWN
    #if angle_yz > 120:
    #    mouse.move(y=-3)
    #elif angle_yz > 105:
    #    mouse.move(y=-1)
    #elif angle_yz < 60:
    #    mouse.move(y=+3)
    #elif angle_yz < 75:
    #    mouse.move(y=+1)



    time.sleep(0.02)