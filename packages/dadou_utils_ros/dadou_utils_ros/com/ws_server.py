import asyncio
import json
import logging
from threading import Thread

import uvloop
import websockets

from dadou_utils_ros.com.input_messages_list import InputMessagesList
from dadou_utils_ros.utils_static import IP


class WsServer(Thread):

    @staticmethod
    async def handler(websocket):
        async for message in websocket:
            msg_dict = json.loads(message)
            msg_dict[IP] = websocket.remote_address[0]
            self.node.publish(msg_dict)
            logging.info("received message {}".format(msg_dict))
            #await websocket.send("I recieved : "+message)

    @staticmethod
    async def main():
        async with websockets.serve(WsServer.handler, "0.0.0.0", 4421):
            await asyncio.Future()  # run forever

    def run(self):
        uvloop.install()
        asyncio.run(WsServer.main())
