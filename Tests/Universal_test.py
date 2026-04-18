import subprocess
import time
#
import unittest
import os
import signal
from Logging import *
import random

from Base.protocol_core import *

class TestProtocolSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Запускаем сервер один раз для всех тестов в этом классе
        cls.server_proc = subprocess.Popen(
            ['python3', 'server.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Чтобы можно было убить дерево процессов
        )
        baselogger = Logger("log.log", "wb", level=5)
        set_baselogger(baselogger)
        debug("Starting server")
        time.sleep(1)  # Даем серверу время "поднять" сокет


    @classmethod
    def tearDownClass(cls):
        # Жестко завершаем сервер после всех тестов
        os.killpg(os.getpgid(cls.server_proc.pid), signal.SIGTERM)
        info("Stopping server")

    def test_01_handshake(self, num = 100):
        """Проверка базового соединения"""
        all = 0
        errors = 0
        for i in range(num):
            try:
                client = Connection("127.0.0.1", 5000)
                client.close()
            except Exception as e:
                exception(str(e))
                errors += 1
            all += 1
        info(f"Handshake test completed, all:{all}, errors:{errors}, Loss:{errors/all}")


    def test_02_inner_channel_stress(self):
        con = Connection("127.0.0.1", 5000)

        data = []
        for i in range(con.psz*255):
            data.append(random.randint(0, 255))
        t1 = time.time_ns()
        for i in range(100):
            con.send_inner(bytes(data))
        t2 = time.time_ns()
        con.close()
        info(f"Inner channel stress test ended, speed:{100*255*con.psz/(t2-t1)/1024/1024*10**9} MB/s")


    def test_03_inner_channel_ping(self, num = 100):
        con = Connection("127.0.0.1", 5000)

        ping = []
        dat = []
        for i in range(1280):
            dat.append(random.randint(0, 255))

        for i in range(num):
            t1 = time.time_ns()
            con.send_inner(bytes(dat))
            t2 = time.time_ns()
            ping.append((t2-t1)/1000000)
        con.close()
        info(f"Test 3 inner channel ping ended avg:{sum(ping)/len(ping)} ms, max:{max(ping)} ms, min:{min(ping)} ms")






if __name__ == '__main__':
    unittest.main()