import logging
import re
import time
from os.path import exists

import serial
from serial import SerialException

from dadou_utils_ros.utils_static import ERROR, SERIAL_ID, BAUD_RATE, NAME, DEVICE_MSG_SIZE, MSG, TYPE


#usb permission : sudo usermod -a -G dialout dadou


class SerialDevice:

    USB_ID_PATH = "/dev/serial/by-id/"
    plugged = False
    device = None
    msg_size = 0

    def __init__(self, device_config):
#    def __init__(self, name, serial_id, type, baud_rate, msg_size=0, default_msg=None):
        self.serialPath = self.USB_ID_PATH+device_config[SERIAL_ID]
        self.baud_rate = device_config[BAUD_RATE]
        self.name = device_config[NAME]
        self.msg_size = device_config[DEVICE_MSG_SIZE]
        if MSG in device_config:
            self.default_msg = device_config[MSG]
        self.connect()
        self.type = device_config[TYPE]
        self.buf = bytearray()

    def connect(self):
        try:
            device_exists = exists(self.serialPath)
            if device_exists:
                self.device = serial.Serial(self.serialPath, 115200, timeout=1)
                logging.info('serial connected  : ' + self.name)
                self.plugged = True
            else:
                logging.error("device {} not present".format(self.name))
        except SerialException:
            logging.error("serial id {} not present".format(self.device), exc_info=True)
            pass

    def get_msg(self, size='X'):
        if size == 'X':
            size = self.msg_size
        try:
            if not self.device:
                self.connect()
            if self.plugged and self.device.isOpen() and exists(self.serialPath):
                # logging.info("{} connected!".format(self.arduino.port))
                if self.device.inWaiting() > 0:
                    if size == 0:
                        line = self.device.readline()
                    else:
                        line = self.device.read(size)
                        self.device.reset_input_buffer()
                    # msg = line.decode('UTF8').strip()
                    msg = line.decode("ascii", errors="replace")
                    logging.info("received from {} : {}".format(self.name, msg))
                    self.device.flush()
                    return msg
        except Exception as e:
            logging.error("{} device error : {}".format(self.name, e))
            self.device = None  # Réinitialise le device
                # self.device.read(self.device.in_waiting)
                # print(self.device.in_waiting)
        return None

    """def get_msg2(self):
        i = self.buf.find(b">")
        if i >= 0:
            r = self.buf[:i+1]
            self.buf = self.buf[i+1:]
            return r.decode()
        while True:
            i = max(1, min(2048, self.device.in_waiting))
            data = self.device.read(i)
            i = data.find(b">")
            if i >= 0:
                r = self.buf + data[:i+1]
                self.buf[0:] = data[i+1:]
                return r.decode()
            else:
                self.buf.extend(data)"""

    def send_msg(self, msg, flush=False):
        if not self.device:
            logging.error("device {} empty".format(self.name))
            return
        if self.device.isOpen() and flush:
            # self.device.flush()
            self.device.reset_input_buffer()
        if self.device.isOpen() and msg:
            self.device.write(str.encode("<{}>\n".format(msg)))
        else:
            logging.error("device {} open:  or msg empty".format(self.name))

    def get_msg_separator(self):
        msg = self.get_msg()
        if msg and len(re.findall('<.+>', msg)) > 0:
            msg = re.findall('<.+>', msg)[0]
            if len(msg) > 2:
                return msg[1:len(msg)-1]

    def setPlugedIn(self, connected):
        self.plugged = connected
