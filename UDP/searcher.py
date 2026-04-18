import json
f = open("result.txt", "r")
data = json.load(f)
f.close()

m = data[0]
sp = data[1]
ds = data[2]
ps = data[3]
dps = data[4]

mx = [0, 0, 0]
for i in range(len(m)):
    speed = sp + i*ds
    for j in range(len(m[1])):
        size = ps+  j*dps
        A = size*m[i][j]*speed/1024/1024
        if A > mx[0]:
            mx = [A, speed, size]
print(mx)