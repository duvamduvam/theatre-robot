import asyncio
import logging
import traceback
from threading import Thread

from dadou_utils_ros.utils_static import ANGLO, KEY, JOYSTICK


class Message:

    event_loop = asyncio.new_event_loop()

    def __init__(self, ws_clients, devices_manager=None):
        self.ws_clients = ws_clients
        #self.lora = devices_manager.get_device(LORA)
        self.lora = None

    def send(self, msg: dict, targets=None):

        for ws_client in self.ws_clients:
            if targets:
                if ws_client.name in targets:
                    self.ws_client_thread(ws_client, msg)
            else:
                self.ws_client_thread(ws_client, msg)

    def ws_client_thread(self, ws_client, msg):
        thread = Thread(target=ws_client.send, args=(msg,))
        thread.start()

    def send_lora(self, msg: dict):
        if ANGLO in msg:
            self.lora.send_msg('A'+msg[ANGLO])
        if KEY in msg:
            self.lora.send_msg('K'+msg[KEY])
        if JOYSTICK in msg:
            self.lora.send_msg('J' + msg[JOYSTICK])

    """def __int__(self, msg):
        self.msg = msg
        if msg is not dict:
            logging.warning("input {} is not a dictionary".format(msg))

    def get(self, key):
            if not self.msg[key]:
                logging.warning("no => {} <= in message".format(key))
            return self.msg[key]

    def key(self):
        return self.get('key')"""
