from Base.protocol_core import *

class Zero_Handler:
    def __init__(self, connection):
        self.is_alive = False
        time.sleep(1)
        connection.is_alive = 0

server = Server('127.0.0.1', 55432, Zero_Handler)