from Base.protocol_core import *
import binascii
def test():
    con = Connection('127.0.0.1', 55432, timeout=5)
    con.psz = 1000
    #f = open('/Users/artembatanin/PycharmProjects/Science/DSC03411.ARW', mode='rb')
    #data = f.read()
    #data = data[:1000 * 255]
    #f.close()
    #t1 = time.time()
    #con.send_inner(data)
    #t2 = time.time()
    #recieved_data = con.recv_inner()
    con.close()
    #print('Closed')
    #if binascii.crc32(data) != binascii.crc32(recieved_data):
    #    print('CRC32 error')
    #    raise Exception('Хэши не совпадают')
    #print(binascii.crc32(data), binascii.crc32(recieved_data))
    #print(1280 * 255 / 1024 / (t2 - t1))
errors = 0
all = 0
con = Connection('127.0.0.1', 5000, timeout=5)
f = open('/Users/artembatanin/PycharmProjects/Science/DSC03411.ARW', mode='rb')
data = f.read()
data = data[:1200*255]

t1 = time.time_ns()
con.send_inner(data)
t2 = time.time_ns()
time.sleep(1)
con.close()
print(len(data)/1024/1024/(t2 - t1)*10**9)
'''
for i in range(1000):
    all += 1
    try:
        test()
    except Exception as e:
        print(e)
        errors += 1

    print(errors/all, i)
'''


