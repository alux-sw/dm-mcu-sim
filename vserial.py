"""가상 UART 쌍: pty 2개를 만들어 서로 이어 준다 (1행 DM 포트, 2행 MCU 포트 출력)"""
import os
import select
import sys
import tty

kChunk = 4096

master_a, slave_a = os.openpty()
master_b, slave_b = os.openpty()
tty.setraw(slave_a)
tty.setraw(slave_b)
print(os.ttyname(slave_a))
print(os.ttyname(slave_b))
sys.stdout.flush()

while True:
    ready, _, _ = select.select([master_a, master_b], [], [])
    if master_a in ready:
        os.write(master_b, os.read(master_a, kChunk))
    if master_b in ready:
        os.write(master_a, os.read(master_b, kChunk))
