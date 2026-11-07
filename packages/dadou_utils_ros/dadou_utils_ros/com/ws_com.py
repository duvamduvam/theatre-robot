import asyncio
from threading import Thread

import websockets


class WsCom(Thread):

    IP = 'locahost'
    PORT = '8765'

    @staticmethod
    async def echo(websocket):
        async for message in websocket:
            print(message)
            await websocket.send(message)

    @staticmethod
    async def main():
        async with websockets.serve(WsCom.echo, WsCom.IP, WsCom.PORT):
            await asyncio.Future()  # run forever

    async def await_send(self, msg, ip):
        async with websockets.connect(WsCom.echo, "ws://localhost:8765") as websocket:
            await websocket.send(msg)
            await websocket.recv()

    def send(self, msg, ip):
        asyncio.run(self.send(msg, ip))
        #thread = Thread(target=WsCom.await_send, args=msg)
        #thread.start()

    def run(self):
        asyncio.run(WsCom.main())
