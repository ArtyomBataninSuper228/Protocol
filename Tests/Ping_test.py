from Base.protocol_core import *
import random

num = 1000

con = Connection("46.45.15.136", 6552)
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
print(f"Test 3 inner channel ping ended avg:{sum(ping)/len(ping)} ms, max:{max(ping)} ms, min:{min(ping)} ms")