from buildinLed import BuildinLed
import busio
import board
import busio
#from anglometer import Anglometer
from glove_keys import GloveKeys
from vibrator import Vibrator
#from bno055 import BNO055
import adafruit_lsm303_accel

import supervisor
supervisor.runtime.autoreload = False

keyboard = GloveKeys((("x", "w", "v"), ("r", "q", "p"), ("o", "n", "m"), ("u", "t", "s")),
                     (board.GP10, board.GP11, board.GP12),
                     (board.GP6, board.GP7, board.GP8, board.GP9))

#keyboard = GloveKeys((("c", "b", "a"), ("f", "e", "d"), ("i", "h", "g"), ("l", "k", "j")),
#                     (board.GP10, board.GP11, board.GP12),
#                     (board.GP6, board.GP7, board.GP8, board.GP9))

buildinLed = BuildinLed()
#uart = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=10)
#anglometer = Anglometer()
vibrator = Vibrator(board.GP14)
#bno055 = BNO055(board.GP2, board.GP3)


SDA = board.GP2
SCL = board.GP3
i2c = busio.I2C(SCL, SDA)  # uses board.SCL and board.SDA
sensor = adafruit_lsm303_accel.LSM303_Accel(i2c)

print("start glove")

while True:
    try:
        acc_x, acc_y, acc_z = sensor.acceleration

        print('Acceleration (m/s^2): ({0:10.3f}, {1:10.3f}, {2:10.3f})'.format(acc_x, acc_y, acc_z))
        print('')

        keys = keyboard.check()
        if len(keys) > 0:
            #if keys[0] == "a":
            #   bno055.process()
            #else:
            msg = "<"+keys[0]+">"
            print(msg)
            buildinLed.flash()
            vibrator.click()
        buildinLed.process()
        vibrator.process()
        #bno055.process()
    except Exception as e:
        print("error : {}".format(e))
