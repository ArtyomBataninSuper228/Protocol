import socket


UDP_IP = "46.45.15.136"
UDP_PORT = 6553
sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def send(data, to):
        sender.sendto(data, to)

def resieving():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    while True:
            data, addr = sock.recvfrom(1400)
            send(data, addr)

resieving()
