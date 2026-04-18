import binascii
import queue
import socket
import threading
import time
import math
from collections import deque



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
        pass
    def get_block(self, blocksize):
        return self.buffer.extract_block(blocksize)

class Block_Getter:
    def __init__(self):
        self.buffer = GlobalDataStream()
    def process_block(self, block):
        self.buffer.feed(block)


'''
Global Packet ID:
0 - Send in inner chanel
1 - Ack in inner channel
2 - Packet in Outer channel
3 - ACK in Outer channel
4 - keepalive
'''

"""
Inner Packet ID:
0 - Handshake
1 - Start of block
2 - End of block
3 - User data
"""
'''
Packet Structure:
ID (Global id (0-9) + inner id (0-9)) ||| Connection ID ||| DATA ||| HESH 

Inner packet structure:
ID (Global id (0-9) + inner id (0-9)) ||| Connection ID  ||| packet_id ||| Num (0-256) ||| Total message len (0-256) ||| DATA ||| HESH 


'''


class Inner_Client_Connection:
    def __init__(self, conn):
        self.buffer = GlobalDataStream()
        self.conn = conn
        self.packets = []
        self.waiting = dict()
        self.last_sended_packet_id = 0
        self.last_recieved_id = -1
    def put_packet(self, id, data):

        num = int.from_bytes(data[0:1], byteorder='big')
        length = int.from_bytes(data[1:2], byteorder='big')
        packet_id = int.from_bytes(data[2:6], byteorder='big')

        ack_pack = data[2:6]
        self.conn.send_packet(10, ack_pack)
        #self.conn.add_packet(global_id= 1, inner_id = 0, data = ack_pack, is_left=True)
        if packet_id <= self.last_recieved_id:
            return
        data = data[6:]
        self.last_recieved_id = max(self.last_recieved_id, packet_id)
        if self.last_recieved_id == 2**32 -1 :
            self.last_recieved_id = -1


        if num == 0 and len(self.packets) != length:

            self.packets = []
            for i in range(length):
                self.packets.append([])
        self.packets[num] = data
        if num == length - 1:
            message = bytes()
            for i in self.packets:
                message += i
            self.packets = []
            self.process_message(id, message)
    def process_message(self, id,  message):
        if id == 0:
            self.conn.is_started = True
            connection_id = int.from_bytes(message[:4], byteorder='big')
            self.conn.id = connection_id
            self.conn.event.set()
        elif id == 3:
            self.conn.user_inner_buffer.put(message)

    def send_msg(self, id, msg):
        num_packets = math.ceil(len(msg)/self.conn.psz)
        if num_packets == 0:
            num_packets = 1

        for i in range(num_packets):
            packet = msg[i*self.conn.psz:(i+1)*self.conn.psz]
            self.send(id, packet, i, num_packets)

    def send(self, id, packet, message_num, total_num):
        self.last_sended_packet_id += 1
        self.last_sended_packet_id = self.last_sended_packet_id % (2 ** 32)
        my_id = self.last_sended_packet_id
        packet = message_num.to_bytes(1, byteorder='big') + total_num.to_bytes(1,
                                                                               byteorder='big') + self.last_sended_packet_id.to_bytes(
            4, byteorder='big') + bytes(packet)
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
    def __init__(self, ip, port, timeout = 1, buffersz = 1024 * 1024 * 10):
        self.buffer = GlobalDataStream()
        self.ip = ip
        self.port = port
        self.id = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffersz)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffersz)
        self.timeout = timeout
        self.buffersz = buffersz
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
        self.input_buffer = GlobalDataStream()
        self.last_block_id = 0
        self.last_recieved_block_id = 0
        sender = threading.Thread(target=self.packet_sender)
        sender.start()
        reciever = threading.Thread(target=self.packet_reciever)
        reciever.start()
        self.user_inner_buffer = queue.Queue()
        self.event = threading.Event()

        self.inner_channel = ICC(self)

        for i in range(int(timeout/0.5)):
            self.add_packet(0, 0, b"", True)
            if self.event.wait(0.5):
                return
        raise ConnectionError


    def send_inner(self, msg):
        self.inner_channel.send_msg(3, msg)
    def recv_inner(self):
         while self.is_alive:
             if self.user_inner_buffer.empty() == False:
                 return self.user_inner_buffer.get()
             time.sleep(1/10000)


    def add_packet(self, global_id, inner_id, data, is_left = False):
        if is_left:
            self.packets_to_send.appendleft((global_id * 10 + inner_id, data))
        else:
            self.packets_to_send.append((global_id * 10 + inner_id,  data))

    def send_packet(self, id,  data):
        all_data = id.to_bytes(1, byteorder='big') + self.id.to_bytes(4, byteorder='big') + bytes(data)
        hesh = binascii.crc32(all_data)
        all_data = all_data + hesh.to_bytes(4, byteorder='big')
        self.socket.sendto(all_data, (self.ip, self.port))
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





'''
Packet Structure:
ID (Global id (0-9) + inner id (0-9)) ||| DATA ||| HESH 

Inner packet structure:
ID (Global id (0-9) + inner id (0-9))  ||| packet_id ||| Num (0-256) ||| Total message len (0-256) ||| DATA ||| HESH 


'''


class Inner_Server_Connection:
    def __init__(self, conn):
        self.buffer = GlobalDataStream()
        self.conn = conn
        self.packets = []
        self.waiting = dict()
        self.last_sended_packet_id = 0
        self.last_recieved_id = -1
    def put_packet(self, id, data):


        num = int.from_bytes(data[0:1], byteorder='big')
        length = int.from_bytes(data[1:2], byteorder='big')
        packet_id = int.from_bytes(data[2:6], byteorder='big')


        ack_pack = data[2:6]
        self.conn.send_packet(10, ack_pack)
        #self.conn.add_packet(global_id= 1, inner_id = 0, data = ack_pack, is_left=True)
        if packet_id <= self.last_recieved_id:
            return
        data = data[6:]
        self.last_recieved_id = max(self.last_recieved_id, packet_id)
        if self.last_recieved_id == 2**32 -1 :
            self.last_recieved_id = -1


        if num == 0 and len(self.packets) != length:
            self.packets = []
            for i in range(length):
                self.packets.append([])
        self.packets[num] = data
        if num == length - 1:
            message = bytes()
            for i in self.packets:
                message += i
            self.packets = []
            t = threading.Thread(target = self.process_message, args = (id, message,))
            t.start()
            #self.process_message(id, message)
    def process_message(self, id,  message):
        if id == 0:
            pass
        elif id == 3:
            self.send_msg(3, message)
    def send_msg(self, id, msg):
        num_packets = math.ceil(len(msg)/self.conn.psz)
        if num_packets == 0:
            num_packets = 1
        for i in range(num_packets):
            packet = msg[i*self.conn.psz:(i+1)*self.conn.psz]
            try:
                self.send(id, packet, i, num_packets)
            except:
                pass

    def send(self, id, packet, message_num, total_num):
        self.last_sended_packet_id += 1
        self.last_sended_packet_id = self.last_sended_packet_id % (2 ** 32)
        my_id = self.last_sended_packet_id
        packet = message_num.to_bytes(1, byteorder='big') + total_num.to_bytes(1,byteorder='big') + self.last_sended_packet_id.to_bytes(4, byteorder='big') + bytes(packet)
        event = threading.Event()
        self.waiting[my_id] = event
        for i in range(int(self.conn.timeout/0.2)):
            self.conn.send_packet(id, packet)
            #self.conn.add_packet(global_id=0, inner_id=id, data=packet, is_left=True)
            if event.wait(0.2):
                self.waiting.pop(my_id)
                return
        raise TimeoutError

ISC = Inner_Server_Connection

class Server_Connection():
    def __init__(self,socket, id,  ip,port,  raw_parametrs, server, timeout = 10, buffersz = 1024*1024*10):
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
        self.user_inner_buffer = queue.Queue()
        self.recieved_packets_num = 0

        process_thread = threading.Thread(target = self.packet_process)
        process_thread.start()
        sender_thread = threading.Thread(target=self.packet_sender)
        sender_thread.start()
        self.server = server
        self.server.connections[self.id]   = self
        self.server.addr_id[(self.ip, self.port)] = id
        self.inner_channel = ISC(self)
        self.inner_channel.send_msg(0, self.id.to_bytes(4, byteorder='big'))
        self.add_packet(global_id= 1, inner_id = 0, data = self.id.to_bytes(4, byteorder='big'), is_left=True)


    def packet_process(self):
        last_con = time.time()
        while self.is_alive:
            if not self.recieved_packets.empty():
                while not self.recieved_packets.empty():
                    self.recieved_packets_num += 1
                    id, data, addr = self.recieved_packets.get()
                    if addr != (self.ip, self.port):
                        print(addr, self.ip, self.port)
                        self.server.addr_id.pop((self.ip, self.port))
                        self.server.addr_id[addr] = id
                        self.ip = addr[0]
                        self.port = addr[1]

                    global_id = id // 10
                    inner_id = id % 10
                    if global_id in (0, 1):  ## Inner Channel
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
            time.sleep(1/100000)
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
        self.server.connections.pop(self.id)

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
    def __init__(self,ip,port, handler, timeout = 10, buffersz = 1024*1024*10, ):

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
        self.handler = handler
        self.is_alive = True
        reciever_thread = threading.Thread(target=self.packet_reciever)
        reciever_thread.start()
        self.addr_id = dict()
        self.last_id = 0


    def packet_reciever(self):
        buff = bytearray(1500)

        while self.is_alive:
            self.socket.settimeout(1)
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
            except ConnectionRefusedError:
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






