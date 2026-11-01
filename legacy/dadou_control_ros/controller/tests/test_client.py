import asyncio
import websockets

async def hello():
    async with websockets.connect("ws://192.168.1.150:4421") as websocket:
        await websocket.send("Hello world!")
        response = await websocket.recv()
        print(response)

asyncio.run(hello())

#websocket = websockets.connect("ws://192.168.1.150:4421")
#websocket.send("Hello world!")
