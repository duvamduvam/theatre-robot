import logging

import adafruit_rfm9x
import board
import busio
from digitalio import DigitalInOut


class LoraRadio:
    RADIO_FREQ_MHZ = 434
    TX_POWER = 23

    def __init__(self, config):
        self.init_ok = False
        try:
            cs = DigitalInOut(board.CE1)
            reset = DigitalInOut(board.D25)
            spi = busio.SPI(board.SCK, MOSI=board.MOSI, MISO=board.MISO)

            self.rfm9x = adafruit_rfm9x.RFM9x(spi, cs, reset, self.RADIO_FREQ_MHZ)
            self.rfm9x.tx_power = self.TX_POWER
            self.init_ok = True
        except (RuntimeError, IOError) as err:
            logging.error('failed to initialize lora radio (spi enabled ?): {}'.format(err))

    def send_msg(self, msg):
        if self.init_ok:
            logging.info("send lora msg : {}".format(msg))
            self.rfm9x.send(bytes(msg, "utf-8"))

    def receive_msg(self):
        if self.init_ok:
            msg = self.rfm9x.receive(timeout=0)
            if msg:
                logging.info("receive lora msg : {}".format(msg))
                return msg
                #rssi = rfm9x.last_rssi
