import asyncio
import json
import logging
import socket

import uvloop
import websockets


class WsClient:

    #"ws://192.168.1.150:4421"

    def __init__(self, host, port, name):

        #websocket = WebSocket("ws://localhost:8001/")
        #self.ws = create_connection(url)

        self.name = name
        self.url = "ws://{}:{}".format(host, port)

        self.activ = self.is_server_listening(host, port)
        if not self.activ:
            logging.error("device {} {} down".format(self.name, self.url))
            return

        logging.info("device {} {} listening".format(self.name, self.url))
        uvloop.install()

    @staticmethod
    def is_server_listening(host, port):
        #TODO make it async
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        activ = False
        try:
            activ = test_socket.connect_ex((host, port)) == 0
        except:
            pass
        test_socket.close()
        return activ

    @staticmethod
    async def async_send(msg, url):
        async with websockets.connect(url) as websocket:
            await websocket.send(json.dumps(msg))
            #response = await websocket.recv()
            #logging.debug("server response : {}".format(response))

    def send(self, msg):
        if self.activ:
            logging.info("send {} to {}".format(msg, self.name))
            asyncio.run(WsClient.async_send(msg, self.url))


