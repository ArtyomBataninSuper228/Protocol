from Base.protocol_core import *
num = 100
all = 0
errors = 0
for i in range(num):
            try:
                client = Connection("46.45.15.136", 6552)
                client.close()
            except Exception as e:
                #exception(str(e))
                errors += 1
            all += 1
print(f"Handshake test completed, all:{all}, errors:{errors}, Loss:{errors/all}")