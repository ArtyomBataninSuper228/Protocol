import time

from Base.protocol_core import *
import random
con = Connection("192.168.1.12", 6552)
con.timeout = 4
con.psz = 1280
data = []
num = 1
for i in range(con.psz*255):
    data.append(random.randint(0, 255))
t1 = time.time_ns()
for i in range(num):
    con.send_inner(bytes(data))
t2 = time.time_ns()
print("Sended")
print(con.recv_inner() == bytes(data))
con.close()
print(f"Inner channel stress test ended, speed:{num*255*con.psz/(t2-t1)/1024/1024*10**9} MB/s, psz:{con.psz}")
