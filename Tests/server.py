from Base.protocol_core import *
from pathlib import Path

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



# Получаем путь к папке, где лежит текущий запускной скрипт
BASE_DIR = Path(__file__).resolve().parent.parent

# Теперь собираем путь динамически
cert_path = BASE_DIR / "Base" / "certificate.crt"
key_path = BASE_DIR / "Base" / "private_key.pem"


server = Server('127.0.0.1', 5000, Zero_Handler, certificate = cert_path, private_key = key_path)