from Base.protocol_core import *

class Zero_Handler:
    def __init__(self, connection):
        self.connection = connection
        self.is_alive = True
    def resender(self):
        while self.connection.is_alive:
            while not self.connection.inner_queue.empty():
                msg = self.connection.inner_queue.get()
                self.connection.send_inner(msg)
            time.sleep(1/1000)


server = Server('127.0.0.1', 5000, Zero_Handler)