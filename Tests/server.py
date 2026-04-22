from Base.protocol_core import *

class Zero_Handler:
    def __init__(self, connection):
        self.connection = connection
        self.is_alive = True
        t = threading.Thread(target=self.resender)
        t.start()
    def resender(self):
        print("resender")
        while self.connection.is_alive:
            while not self.connection.inner_queue.empty():
                msg = self.connection.inner_queue.get()
                print("Getted message", len(msg))
                self.connection.send_inner(msg)
                print("Sended message")
            time.sleep(1/1000)


server = Server('127.0.0.1', 6552, Zero_Handler)