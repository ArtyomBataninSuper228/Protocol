import socket
import threading
import time
import json
to = ("46.45.15.136", 6553)
b =[]
for i in range(0, 1400):
    b.append(i%256)
b = bytes(b)


UDP_IP = "46.45.15.136"
UDP_PORT = 6553
sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sender.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024*10)
sender.settimeout(1)
speed = 10000
num = 10000

def send(speed, num, p_size):
    for i in range(0, num):
        sender.sendto(b[:p_size], to)
        time.sleep(1/speed)
def recieve():
    num = 0
    try:
        while 1:
            sender.recvfrom(1424)
            num += 1
    except TimeoutError:
        return num
m = []

def test():
    for speed in range(500, 10000, 500):
        m.append([])
        for p_size in range(1000, 1001, 100):
            t = threading.Thread(target=send, args=(speed, num, p_size))
            t.start()
            recieved = recieve()
            m[-1].append(recieved/num)
            print(f"speed: {speed}, packetsz: {p_size}, %: {recieved/num}")
test()
f = open("result.txt", "w")
json.dump([m, 1000, 500, 100, 100], f)
f.close()

