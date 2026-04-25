from __future__ import annotations
import binascii
import queue
import socket
import threading
import time
import math
from collections import deque
import secrets
import os
import zlib
from ssl import cert_time_to_seconds
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import datetime



class GlobalDataStream:
    def __init__(self):
        self.buffer = bytearray()
        self.lock = threading.Lock()

    def feed(self, data):
        with self.lock:
            self.buffer.extend(data)

    def extract_block(self, max_size=10 * 1024 * 1024):
        with self.lock:
            if not self.buffer:
                return None

            size_to_take = min(len(self.buffer), max_size)

            block_data = self.buffer[:size_to_take]

            del self.buffer[:size_to_take]

            return block_data

class Block_Builder():
    def __init__(self):
        self.buffer = GlobalDataStream()
        self.num = 0
        self.is_running = True
        pass
    def get_block(self, blocksize):
        if self.num == 2**32 -1:
            self.num = 0
        self.num += 1
        while len(self.buffer.buffer) == 0 and self.is_running:
            time.sleep(1/1000)
        data = self.buffer.extract_block(blocksize)
        return  data, b'0' #block, user_data




class Block_Getter:
    def __init__(self):
        self.buffer = GlobalDataStream()

    def process_block(self, num, block):
        self.buffer.feed(block)




'''
Global Packet ID:
0 - Send in inner chanel
1 - Ack in inner channel
2 - Packet in Outer channel
3 - ACK in Outer channel
4 - keepalive
5 - Registrate New packet_sender
'''
"""
Inner Packet ID:
0 - Handshake
1 - Start of block
2 - End of block
3 - User data
4 - Block is ended
5 - Send certificate (server) / send key (client)
6 - Send id + salt
"""
'''
Packet Structure:
ID (Global id (0-9) + inner id (0-9)) ||| Connection ID ||| DATA ||| HESH 

Inner packet structure:
ID (Global id (0-9) + inner id (0-9)) ||| Connection ID  ||| packet_id ||| Num (0-256) ||| Total message len (0-256) ||| Message_ID ||| DATA ||| HESH 
'''


class Inner_Client_Connection:
    def __init__(self, conn:Connection):
        self.buffer = GlobalDataStream()
        self.conn = conn
        self.packets = []
        self.waiting = dict()
        self.message_docks = dict()
        self.last_sended_packet_id = 0
        self.last_recieved_id = -1
        self.message_id = 0
        self.key_sended_event = threading.Event()
        self.sending_shifr = False
    def put_packet(self, id, data):

        num = int.from_bytes(data[0:1], byteorder='big')
        length = int.from_bytes(data[1:2], byteorder='big')
        packet_id = int.from_bytes(data[2:6], byteorder='big')
        msg_id = int.from_bytes(data[6:10], byteorder='big')

        ack_pack = data[2:6]
        self.conn.send_packet(10, ack_pack)
        # self.conn.add_packet(global_id= 1, inner_id = 0, data = ack_pack, is_left=True)

        data = data[10:]
        self.last_recieved_id = max(self.last_recieved_id, packet_id)
        if self.last_recieved_id == 2 ** 32 - 1:
            self.last_recieved_id = -1

        if msg_id not in self.message_docks:
            dock = []
            for i in range(length):
                dock.append([])
            self.message_docks[msg_id] = dock
        else:
            dock = self.message_docks[msg_id]

        dock[num] = data
        dock[num] = data
        if num == length - 1:
            message = bytes()
            for i in dock:
                message += bytes(i)
            self.message_docks.pop(msg_id)
            t = threading.Thread(target=self.process_message, args=(id, message,))
            t.start()
    def process_message(self, id,  message):
        if id == 0:
            self.conn.is_started = True

            connection_id = int.from_bytes(message[:4], byteorder='big')

            self.conn.id_hash = connection_id
            a = 1
            self.conn.send_packet(10, a.to_bytes(4, byteorder='big'))
            self.conn.event.set()
        elif id == 3:
            self.conn.user_inner_buffer.put(message)
        elif id == 5:
            cert_data = message
            cert = x509.load_pem_x509_certificate(cert_data)
            public_key = cert.public_key()
            self.conn.cert = cert
            self.conn.public_key = public_key
            print('___Проверка Сертификата___')
            print(f"Субъект: {cert.subject}")
            print(f"Действителен до: {cert.not_valid_after_utc}")
            if cert.not_valid_after_utc < datetime.datetime.now(datetime.timezone.utc):
                print("ВНИМАНИЕ: Сертификат просрочен!")
                raise PermissionError('Сертификат просрочен')
            print('KEY', self.conn.key)

            ciphertext = public_key.encrypt(
                self.conn.key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),  # Функция генерации маски
                    algorithm=hashes.SHA256(),  # Хеш-алгоритм
                    label=None
                )
            )
            if self.key_sended_event.is_set() or self.sending_shifr:
                return
            self.sending_shifr = True
            self.send_msg(5, ciphertext)
            print("shiphr sended")
            self.key_sended_event.set()
        if id == 6:
            conn_id = int.from_bytes(message[:4], byteorder='big')
            salt = message[4:12]
            print(conn_id, salt)
            self.conn.id = conn_id
            self.conn.id_hash = binascii.crc32(message[:4]+salt)
            while not self.key_sended_event.wait(0.5):
                pass
            self.conn.cert_event.set()


    def send_msg(self, id, msg):
        num_packets = math.ceil(len(msg)/self.conn.psz)
        msg_id = self.message_id
        self.message_id += 1
        self.message_id = self.message_id % (2 ** 32)
        if num_packets == 0:
            num_packets = 1

        for i in range(num_packets):
            packet = msg[i*self.conn.psz:(i+1)*self.conn.psz]
            self.send(id, packet, i, num_packets, msg_id)

    def send(self, id, packet, message_num, total_num, message_id):
        self.last_sended_packet_id += 1
        self.last_sended_packet_id = self.last_sended_packet_id % (2 ** 32)
        my_id = self.last_sended_packet_id
        packet = message_num.to_bytes(1, byteorder='big') + total_num.to_bytes(1,
                                                                               byteorder='big') + self.last_sended_packet_id.to_bytes(
            4, byteorder='big') + message_id.to_bytes(4, byteorder = "big")  +bytes(packet)
        event = threading.Event()
        self.waiting[my_id] = event
        for i in range(int(self.conn.timeout / 0.2)):
            self.conn.send_packet(id, packet)
            #self.conn.add_packet(global_id=0, inner_id=id, data=packet, is_left=True)
            if event.wait(0.2):
                self.waiting.pop(my_id)
                return
        raise TimeoutError


ICC = Inner_Client_Connection






class Connection():
    def __init__(self, ip, port, timeout = 1, buffersz = 1024 * 1024 * 10, is_coding = True):
        self.buffer = GlobalDataStream()
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffersz)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffersz)
        self.timeout = timeout
        self.buffersz = buffersz
        self.is_coding = False


        self.psz = 1280
        self.delay = 100000
        self.ping = 50
        self.frame = 2
        self.loss = 0

        self.is_started = False
        self.time_of_start = time.time()
        self.send_block_number = 0
        self.recieve_block_number = 0
        self.is_alive = True
        self.recieved_packets = deque()
        self.packets_to_send = deque()
        self.blocks_in_process = []
        self.salt = None
        self.secret_noise = secrets.token_bytes(32)
        self.certificate = None
        self.key = secrets.token_bytes(32)
        self.id_hash = 0

        self.block_builder = None
        sender = threading.Thread(target=self.packet_sender)
        sender.start()
        reciever = threading.Thread(target=self.packet_reciever)
        reciever.start()
        self.user_inner_buffer = queue.Queue()
        self.event = threading.Event()
        self.cert_event = threading.Event()
        self.inner_channel = ICC(self)
        #data = self.secret_noise + int(is_coding).to_bytes(1, byteorder='big')
        # Global ID (0) ||| Inner ID (0) ||| Secret_noise ||| coding |||
        ok = 0
        for i in range(int(timeout/0.5)):
            self.add_packet(0, 0, b"", True)
            if self.event.wait(0.5):
                self.is_coding= is_coding
                ok = 1
                break
        if ok == 0:
            raise ConnectionError
        self.event.clear()

        while not self.cert_event.wait(0.5):
            pass
        print("Connected")



    def send_inner(self, msg):
        self.inner_channel.send_msg(3, msg)
    def recv_inner(self):
         while self.is_alive:
             if self.user_inner_buffer.empty() == False:
                 return self.user_inner_buffer.get()
             time.sleep(1/10000)
         return None


    def block_sender(self):
        while self.is_alive:
            while len(self.blocks_in_process) < self.frame or self.block_builder is None:
                time.sleep(1/10000)
            block = self.block_builder.get_block(self.buffersz)
            self.blocks_in_process.append(block)
            num =  math.ceil(len(block)/self.psz)
            self.send_block_number += 1
            block_number = self.send_block_number
            self.inner_channel.send_msg(1, block_number.to_bytes(4, byteorder='big'))
            for i in range(num):
                self.add_packet(2, 0, block[i*self.psz:(i+1)*self.psz])



    def add_packet(self, global_id, inner_id, data, is_left = False):
        if is_left:
            self.packets_to_send.appendleft((global_id * 10 + inner_id, data))
        else:
            self.packets_to_send.append((global_id * 10 + inner_id,  data))

    def send_packet(self, id,  data):
        all_data = id.to_bytes(1, byteorder='big') + self.id_hash.to_bytes(4, byteorder='big') + bytes(data)
        hesh = binascii.crc32(all_data)
        all_data = all_data + hesh.to_bytes(4, byteorder='big')
        try:
            self.socket.sendto(all_data, (self.ip, self.port))
        except:
            pass


    def packet_sender(self):
        t = time.time_ns()
        NSEC = 10 ** 9

        while self.is_alive or len(self.packets_to_send) != 0:
            if len(self.packets_to_send) != 0:
                id_p, data = self.packets_to_send.popleft()
                t += (1 / self.delay) * NSEC
                self.send_packet(id_p, data)
                while time.time_ns() < t:
                    pass
            else:
                time.sleep(1/10000)

                #t += 2 * (1 / self.delay) * NSEC
                #self.send_packet(40, b'')
                #while time.time_ns() < t:
                #    pass
        time.sleep(1/5)
        self.socket.close()


    def packet_reciever(self):
        while self.is_alive:
            self.socket.settimeout(1/10)
            try:
                data, addr = self.socket.recvfrom(1500)
            except socket.timeout:
                continue
            data_hash = data[-4:]
            data = data[:-4]
            if binascii.crc32(data).to_bytes(4, 'big') != data_hash:
                del data, addr
                continue
            id = int.from_bytes(data[:1], byteorder='big')
            data = data[1:]
            global_id = id//10
            inner_id = id%10
            if global_id in (0, 1): ## Inner Channel
                if global_id == 0:
                    self.inner_channel.put_packet(inner_id, data)
                if global_id == 1:
                    message_id = int.from_bytes(data[:4], byteorder='big')
                    if message_id in self.inner_channel.waiting:
                        self.inner_channel.waiting[message_id].set()
            if global_id == 2:
                pass ### To construct block from packets
            if global_id == 3:
                pass ### To resend loss
            if global_id == 4:
                pass ### Keep alive
    def close(self):
        self.is_alive = False
        time.sleep(1 / 5)





'''
Packet Structure:
ID (Global id (0-9) + inner id (0-9)) ||| DATA ||| HESH 

Inner packet structure:
ID (Global id (0-9) + inner id (0-9))  ||| packet_id ||| Num (0-256) ||| Total message len (0-256) ||| DATA ||| HESH 


'''


class Inner_Server_Connection:
    def __init__(self, conn:Server_Connection):
        self.buffer = GlobalDataStream()
        self.conn = conn
        self.packets = []
        self.waiting = dict()
        self.message_docks = dict()
        self.last_sended_packet_id = 0
        self.last_recieved_id = -1
        self.message_id = 0
        self.is_encoding = False

    def put_packet(self, id, data):

        num = int.from_bytes(data[0:1], byteorder='big')
        length = int.from_bytes(data[1:2], byteorder='big')
        packet_id = int.from_bytes(data[2:6], byteorder='big')
        msg_id = int.from_bytes(data[6:10], byteorder='big')

        ack_pack = data[2:6]

        self.conn.send_packet(10, ack_pack)
        # self.conn.add_packet(global_id= 1, inner_id = 0, data = ack_pack, is_left=True)

        data = data[10:]
        self.last_recieved_id = max(self.last_recieved_id, packet_id)
        if self.last_recieved_id == 2 ** 32 - 1:
            self.last_recieved_id = -1

        if msg_id not in self.message_docks:
            dock = []
            for i in range(length):
                dock.append([])
            self.message_docks[msg_id] = dock
        else:
            dock = self.message_docks[msg_id]

        dock[num] = data
        dock[num] = data
        if num == length - 1:
            message = bytes()
            for i in dock:
                message += bytes(i)
            self.message_docks.pop(msg_id)
            t = threading.Thread(target = self.process_message, args = (id, message,))
            t.start()
            #self.process_message(id, message)
    def process_message(self, id,  message):
        if id == 0:
            pass
        elif id == 3:
            self.conn.inner_queue.put(message)
        elif id == 5:
            decrypted_key = self.conn.server.private_key.decrypt(
                message,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            self.conn.key = decrypted_key
            print('key',self.conn.key)
            id = int.from_bytes(secrets.token_bytes(4), byteorder='big')
            data = id.to_bytes(4, byteorder='big') + self.conn.salt
            hash = binascii.crc32(self.conn.salt + self.conn.id.to_bytes(4, byteorder='big'))
            while hash in self.conn.server.connections:
                hash = binascii.crc32(self.conn.salt + id.to_bytes(4, byteorder='big'))
                self.conn.salt = secrets.token_bytes(4)
            self.conn.server.connections[hash] = self.conn
            self.conn.hashes = [hash]
            self.send_msg(6, data)
            self.conn.server.connections.pop(self.conn.id)
            self.conn.id = id


    def send_msg(self, id, msg):
        num_packets = math.ceil(len(msg)/self.conn.psz)
        msg_id = self.message_id
        self.message_id += 1
        self.message_id = self.message_id % (2 ** 32)
        if num_packets == 0:
            num_packets = 1

        for i in range(num_packets):
            packet = msg[i*self.conn.psz:(i+1)*self.conn.psz]
            self.send(id, packet, i, num_packets, msg_id)

    def send(self, id, packet, message_num, total_num, message_id):
        self.last_sended_packet_id += 1

        self.last_sended_packet_id = self.last_sended_packet_id % (2 ** 32)
        my_id = self.last_sended_packet_id
        packet = (message_num.to_bytes(1, byteorder='big') +
                  total_num.to_bytes(1,byteorder='big')
                  + my_id.to_bytes(4, byteorder='big')
                  + message_id.to_bytes(4, byteorder = "big")  +bytes(packet))
        event = threading.Event()
        self.waiting[my_id] = event
        for i in range(int(self.conn.timeout / 0.2)):
            self.conn.send_packet(id, packet)
            #self.conn.add_packet(global_id=0, inner_id=id, data=packet, is_left=True)
            if event.wait(0.2):
                self.waiting.pop(my_id)
                return
        raise TimeoutError


ISC = Inner_Server_Connection

class Server_Connection():
    def __init__(self,socket, id,  ip,port,  raw_parametrs, server: Server, timeout = 10, buffersz = 1024*1024*10):
        self.socket = socket
        self.ip = ip
        self.id = id
        self.psz = 1280
        self.delay = 100000
        self.ping = 50
        self.frame = 2
        self.loss = 0
        self.port = port
        self.raw_parametrs = raw_parametrs
        self.server = server
        self.timeout = timeout
        self.buffersz = buffersz
        self.recieved_packets = queue.Queue()
        self.packets_to_send = deque()
        self.is_alive = True
        #self.user_inner_buffer = queue.Queue()
        self.recieved_packets_num = 0
        self.inner_queue = queue.Queue()
        self.salt = secrets.token_bytes(4)
        self.hashes = [binascii.crc32(self.salt + self.id.to_bytes(4, byteorder='big'))]
        self.key = None



        process_thread = threading.Thread(target = self.packet_process)
        process_thread.start()
        sender_thread = threading.Thread(target=self.packet_sender)
        sender_thread.start()
        handler_thread = threading.Thread(target=self.server.handler, args = (self, ))
        handler_thread.start()
        self.server.connections[self.id] = self
        self.inner_channel = ISC(self)
        self.inner_channel.send_msg(0, self.id.to_bytes(4, byteorder='big'))
        self.inner_channel.send_msg(5, self.server.cert_data)
        print('Certificate sended')
        self.user_inner_buffer = queue.Queue()
        self.server = server

        self.server.addr_id[(self.ip, self.port)] = id



        self.add_packet(global_id= 1, inner_id = 0, data = self.id.to_bytes(4, byteorder='big'), is_left=True)


    def send_inner(self, msg):
        self.inner_channel.send_msg(3, msg)

    def recv_inner(self):
         while self.is_alive:
             if self.user_inner_buffer.empty() == False:
                 return self.user_inner_buffer.get()
             time.sleep(1/10000)


    def packet_process(self):
        last_con = time.time()
        while self.is_alive:
            if not self.recieved_packets.empty():
                while not self.recieved_packets.empty():
                    self.recieved_packets_num += 1
                    id, data, addr = self.recieved_packets.get()


                    global_id = id // 10
                    inner_id = id % 10
                    if global_id in (0, 1):## Inner Channel

                        if addr != (self.ip, self.port):
                            try:
                                self.server.addr_id.pop((self.ip, self.port))
                            except KeyError:
                                pass
                            self.server.addr_id[addr] = id
                            self.ip = addr[0]
                            self.port = addr[1]

                        if global_id == 0:
                            self.inner_channel.put_packet(inner_id, data)
                        if global_id == 1:

                            message_id = int.from_bytes(data[:4], byteorder='big')
                            if message_id in self.inner_channel.waiting:
                                self.inner_channel.waiting[message_id].set()
                    if global_id == 2:
                        pass  ### To construct block from packets
                    if global_id == 3:
                        pass  ### To resend loss
                    if global_id == 4:
                        pass  ### Keep alive
                last_con = time.time()
            time.sleep(1/10000)
            if time.time() - last_con > self.timeout:

                self.close()
                break
    def add_packet(self, global_id, inner_id, data, is_left = False):
        if is_left:
            self.packets_to_send.appendleft((global_id * 10 + inner_id, data))
        else:
            self.packets_to_send.append((global_id * 10 + inner_id,  data))
    def send_packet(self, id,  data):
        all_data = id.to_bytes(1, byteorder='big')  + bytes(data)
        hesh = binascii.crc32(all_data)
        all_data = all_data + hesh.to_bytes(4, byteorder='big')
        self.socket.sendto(all_data, (self.ip, self.port))
    def close(self):
        print('close')
        self.is_alive = False
        for i in self.hashes:
            self.server.connections.pop(i)

    def packet_sender(self):
        t = time.time_ns()
        NSEC = 10 ** 9

        while self.is_alive:
            if len(self.packets_to_send) != 0:
                id_p, data = self.packets_to_send.popleft()
                t += (1 / self.delay) * NSEC
                self.send_packet(id_p,  data)
                while time.time_ns() < t:
                    pass


            else:
                time.sleep(1/10000)
                #t += 2 * (1 / self.delay) * NSEC
                ##self.send_packet(40,  b'')
                #while time.time_ns() < t:
                #    pass




class Server :
    def __init__(self,ip,port, handler, timeout = 10, buffersz = 1024*1024*10, certificate = "certificate.crt", private_key = "private_key.pem" ):
        soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        soc.settimeout(None)
        self.socket = soc
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffersz)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffersz)
        self.ip = ip
        self.port = port
        self.handler = handler
        self.timeout = timeout
        self.buffersz = buffersz
        self.socket.bind((self.ip, self.port))
        self.connections = {}
        self.is_alive = True

        self.addr_id = dict()
        self.last_id = 0


        with open(certificate, "rb") as cert_file:
            cert_data = cert_file.read()

        cert = x509.load_pem_x509_certificate(cert_data)
        public_key = cert.public_key()


        with open(private_key, "rb") as key_file:
            key_data = key_file.read()
        private_key = serialization.load_pem_private_key(
            key_data,
            password=None
        )
        self.certificate = cert
        self.cert_data = cert_data
        self.public_key = public_key
        self.private_key = private_key
        print('___Проверка Сертификата___')
        print(f"Субъект: {cert.subject}")
        print(f"Действителен до: {cert.not_valid_after_utc}")
        if cert.not_valid_after_utc < datetime.datetime.now(datetime.timezone.utc):
            print("ВНИМАНИЕ: Сертификат просрочен!")
            raise PermissionError ('Сертификат просрочен')

        reciever_thread = threading.Thread(target=self.packet_reciever)
        reciever_thread.start()


    def packet_reciever(self):
        buff = bytearray(1500)
        self.socket.settimeout(1)
        while self.is_alive:
            try:
                len, addr = self.socket.recvfrom_into(buff, 1500)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except ConnectionAbortedError:
                continue
            except ConnectionError:
                continue
            except:
                continue
            mv = memoryview(buff)
            data = mv[:len]
            data_hash = data[-4:]
            data = data[:-4]
            if binascii.crc32(data).to_bytes(4, 'big') != data_hash:
                del data, addr
                continue
            id = int.from_bytes(data[:1], byteorder='big')
            connection_id = int.from_bytes(data[1:5], byteorder='big')
            data = data[5:]
            if id == 0 and connection_id == 0 and addr not in self.addr_id :
                self.last_id += 1
                print("Start New Connection", addr, self.last_id)
                ip = addr[0]
                port = addr[1]
                t = threading.Thread(target = Server_Connection, args = (self.socket, self.last_id, ip, port, data, self, self.timeout,  self.buffersz))
                t.start()
                continue
            try:
                self.connections[connection_id].recieved_packets.put((id, bytes(data), addr))
            except :
                pass






