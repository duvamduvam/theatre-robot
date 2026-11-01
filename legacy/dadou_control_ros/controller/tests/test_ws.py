import time
import unittest

from com import WsServer


class WsTests(unittest.TestCase):

    def test_ws(self):
        print("before to start")
        server = WsServer()
        server.start()
        print("after to start")
        time.sleep(2)
        #for x in range(100):
        #    #time.sleep(2)
        #    WsCom.send(str(x))
        #    #wscom.send(" message "+str(x))
        #    #WsServer.send(f"message : {x}")
        time.sleep(2000)
