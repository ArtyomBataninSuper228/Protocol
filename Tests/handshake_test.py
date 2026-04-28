from Base.protocol_core import *
num = 1
all = 0
errors = 0
for i in range(num):
            try:
                client = Connection("127.0.0.1", 5000)
                client.delay = 50*1024*1024/1280
                b = secrets.token_bytes(1200)
                for i in range(1*1024*1024*1024//1280):
                    client.add_packet(2, 0, b)
                time.sleep(10)
                client.close()
            except ZeroDivisionError as e:
                #exception(str(e))
                errors += 1
            all += 1
time.sleep(0.5)
print(f"Handshake test completed, all:{all}, errors:{errors}, Loss:{errors/all}")

