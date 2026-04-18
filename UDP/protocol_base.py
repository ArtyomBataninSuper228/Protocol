import binascii
import queue
import socket
import threading
import time
import numpy as np
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


class Datagram_Object:
    def __init__(self, soc, ip, port, timeout=1, buffersz=1024 * 1024 * 10):
        self.ip = ip
        self.port = port
        self.socket = soc#socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.timeout = timeout
        self.buffersz = buffersz
        self.psz = 1280
        self.delay = 1000
        self.frame = 2
        self.loss = 0
        self.time_of_start = time.time()
        self.send_block_number = 0
        self.recieve_block_number = 0
        self.is_alive = True

    def send_packet(self, id, block_id, data, to ,  num, ):
        '''

        Args:
            id: short Тип пакета (0 - handshake, 1 - keepalive, 2 - data, 3 - non-block data, 4 - start of block, 5 - ack, 6 - end of block, 7 - logic ( num = 0 - starting block, num = 1 - ending block, ), )
            block_id: short Номер блока
            data: bytearray Данные
            to: (str ip, int port)
            num: short Позиция стартового байта дынных пакета в блоке

        Returns: None

        '''
        all_data = id.to_bytes(1,byteorder='big')+block_id.to_bytes(4,byteorder='big')+num.to_bytes(4,byteorder='big')+bytes(data)
        hesh = binascii.crc32(all_data)
        all_data = all_data +hesh.to_bytes(4,byteorder='big')
        self.socket.sendto(all_data, to)




    def close(self):
        self.recieved_packets.clear()
        self.socket.close()
        self.is_alive = False

class Dock_sender:
    def __init__(self,  conn:Connection, id):
        self.conn = conn
        self.is_started = False
        self.id = id
        self.ack_buffer = queue.Queue()
        self.is_alive = True
        th = threading.Thread(target=self.answer_ack)
        th.start()
        th2=threading.Thread(target=self.start())
        th2.start()

    def start(self):
        self.is_started = False
        while self.is_alive:
            if self.id > self.conn.frame:
                self.conn.send_docks.pop(self.id)
                self.conn.send_docks.pop(self.id)
                self.is_started = False
                self.is_alive = False
                return
            self.buffer = self.conn.input_buffer.extract_block(self.conn.buffersz)
            if len(self.buffer) == 0:
                self.conn.send_docks.pop(self.id)
                self.conn.send_docks.pop(self.id)
                self.is_started = False
                self.is_alive = False
                return
            self.block_id = self.conn.lasst_block_id + 1
            self.conn.block_docks[self.block_id] = self
            self.conn.last_block_id += 1
            hesh = binascii.crc32(self.buffer)
            data = len(self.buffer).to_bytes(4, byteorder='big') + hesh.to_bytes(4, byteorder='big')

            while self.is_started == False:
                self.conn.add_packet(4, self.block_id, 0, data)
                time.sleep(1 / 10000)

            i = 0
            while i < len(self.buffer):
                end = min(i + self.conn.psz, len(self.buffer))
                data = self.buffer[i:end]
                self.conn.add_packet(2, self.block_id, i, data)
                i = end

            while self.is_started == True:
                self.conn.add_packet(6, self.block_id, 0, b'')
                time.sleep(1 / 10000)



    def answer_ack(self):
        while self.is_alive:
            while self.ack_buffer.empty() == False:
                ack = self.ack_buffer.get()
                for i in range(0, len(ack), 4):
                    byte = int.from_bytes(ack[i:i+4], byteorder='big')
                    self.conn.add_packet(2, self.block_id, byte, self.buffer[byte:byte+self.conn.psz])
            time.sleep(1/10000)


class Dock_reciever:
    def __init__(self, conn:Connection, id, bufsz, hesh):
        self.conn = conn
        self.id = id
        self.buffer = bytes(bufsz)
        self.hesh = hesh
        self.input_buffer = queue.Queue()
        self.spaces = [0, bufsz-1]
    def construct(self):
        while self.spaces != []:
            while self.input_buffer.empty() == False:
                num, block_id, data = self.input_buffer.get() 












class Connection(Datagram_Object):
    def __init__(self,ip,port, timeout = 1, buffersz = 1024*1024*10):
        soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        super().__init__(soc, ip, port, timeout, buffersz)
        self.recieved_packets  = queue.Queue()
        self.packets_to_send = queue.Queue()
        self.input_buffer = GlobalDataStream()
        self.last_block_id = 0
        self.last_thread_id = 0
        self.send_docks = dict()
        self.block_docks = dict()
        self.output_buffer = GlobalDataStream()
        self.last_recieved_block_id = 0


        ### Trying_to_connect

        is_recieved = False
        for i in range(timeout*10):
            self.send_packet(0, 0,data = b'', to=(self.ip, self.port), num =0)
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
            id_p = int.from_bytes(data[:1], byteorder='big')
            block_id = int.from_bytes(data[1:5], byteorder='big')
            num = int.from_bytes(data[5:9], byteorder='big')
            data = data[9:]
            if id_p == 0:
                is_recieved = True
                break
        if not is_recieved:
            raise TimeoutError()
        sender_thread = threading.Thread(target=self.sender)
        sender_thread.start()

        reciver_thread = threading.Thread(target=self.reciever)
        reciver_thread.start()

    def reciever(self):
        """
        Эта функция принимает пакеты с сервера и складывает в буфер

        Исполнять в отдельном потоке!

        Returns: None

        """

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
            id_p = int.from_bytes(data[:1], byteorder='big')
            block_id = int.from_bytes(data[1:5], byteorder='big')
            num = int.from_bytes(data[5:9], byteorder='big')
            data = data[9:]
            if id_p == 7:
                if num == 0:
                    try:
                        self.block_docks[block_id].is_started = True
                    except Exception as e:
                        pass
                if num == 1:
                    try:
                        self.block_docks[block_id].is_started = False
                    except Exception as e:
                        pass
                continue
            if id_p == 5:
                self.block_docks[block_id].ack_buffer.put(data)

            self.recieved_packets.put((num, id_p, block_id, data))

    def sender(self):
        """
        Эта функция отправляет пакеты на сервер с соблюдением необходимых задержек

        Исполнять в отдельном потоке!

        Returns: None
        """

        number = 0
        t = time.time_ns()


        NSEC = 10 ** 9

        while self.is_alive:

            if self.packets_to_send.empty() == False:

                id_p, block_id, num, data = self.packets_to_send.get()


                t += (1 / self.delay) * NSEC
                self.send_packet(id_p, block_id, data, to=(self.ip, self.port), num=num)


                while time.time_ns() < t:
                    pass

            else:
                t += (1 / self.delay) * NSEC
                self.send_packet(3, 0, b'', to=(self.ip, self.port), num=number)

                number = (number + 1) % (2 ** 32)

                while time.time_ns() < t:
                    pass
    def add_packet(self,id_p, block_id, num, data):
        self.packets_to_send.put((id_p, block_id, num, data))


    def close(self):
        self.is_alive = False
        time.sleep(1/5)
        self.socket.close()








class Server (Datagram_Object):
    def __init__(self,ip,port, handler, timeout = 1, buffersz = 1024*1024*10, ):
        soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        soc.settimeout(None)
        super().__init__(soc, ip, port, timeout, buffersz)
        self.socket.bind((self.ip, self.port))
        self.socket.settimeout(timeout)
        self.connections = {}
        self.handler = handler
        reciever_thread = threading.Thread(target=self.reciever)
        reciever_thread.start()
    def reciever(self):
        while self.is_alive:
            try:
                data, addr = self.socket.recvfrom(1500)
            except socket.timeout:
                continue
            except ConnectionResetError, ConnectionAbortedError, ConnectionRefusedError:
                continue
            data_hash = data[-4:]
            data = data[:-4]
            if binascii.crc32(data).to_bytes(4, 'big') != data_hash:
                del data, addr
                continue
            id_p = int.from_bytes(data[:1],byteorder='big')
            block_id = int.from_bytes(data[1:5],byteorder='big')
            num = int.from_bytes(data[5:9],byteorder='big')
            data = data[9:]
            if addr in self.connections:
                self.connections[addr].recieved_packets.put((id_p, block_id, num, data))
            else:
                if id_p !=0:
                    continue
                print('Connected from', addr)
                #self.send_packet(0, 0, b'', addr, 0)### АСК
                New_connection = Server_Connection(self.socket, addr[0], addr[1], data, self.timeout, self.buffersz)
                self.connections[addr] = New_connection
                handler_thread = threading.Thread(target=self.handler, args=(New_connection,))
                handler_thread.start()









