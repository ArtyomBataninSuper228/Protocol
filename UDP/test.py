import binascii
import time
import socket
b =[]
for i in range(0, 1400):
    b.append(i%256)
b = bytes(b)

hesh = binascii.crc32(b)


sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sender.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024*10)
delay = 1/100000
delay *= 10**9
t1 = time.time_ns()
while 1:

    sender.sendto(b, ("192.168.1.12", 6553))
    t1 += delay
    while time.time_ns() < t1:
        pass

