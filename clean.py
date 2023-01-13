import os

m = {}
for line in open('address.txt'):
    m[line] = 1

with open('address-temp.txt', 'w') as f:
    for k in m:
        f.write(k)

os.remove('address.txt')
os.rename('address-temp.txt', 'address.txt')
