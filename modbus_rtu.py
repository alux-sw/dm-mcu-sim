import os
import select
import termios
import time

import icd

kBaud = termios.B115200
kReadChunk = 512

FC_READ_HOLDING = 0x03
FC_READ_INPUT = 0x04
FC_WRITE_SINGLE = 0x06
FC_WRITE_MULTI = 0x10

EX_ILLEGAL_FUNCTION = 0x01
EX_ILLEGAL_ADDR = 0x02
EX_ILLEGAL_VALUE = 0x03
EX_DEVICE_FAIL = 0x04


def crc16(data):
    """Modbus CRC-16 (poly 0xA001, init 0xFFFF)"""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            is_lsb_set = (crc & 1) == 1
            crc >>= 1
            if is_lsb_set:
                crc ^= 0xA001
    return crc


def with_crc(pdu):
    crc = crc16(pdu)
    return bytes(pdu) + bytes([crc & 0xFF, crc >> 8])


def is_crc_ok(frame):
    return crc16(frame[:-2]) == (frame[-2] | (frame[-1] << 8))


def u16_pair(value):
    return bytes([(value >> 8) & 0xFF, value & 0xFF])


def open_serial(path):
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = kBaud
    attrs[5] = kBaud
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


# 요청 프레임 (마스터 → 슬레이브)
def req_read(fc, addr, count):
    return with_crc(bytes([icd.SLAVE_ADDR, fc]) + u16_pair(addr) + u16_pair(count))


def req_write_single(addr, value):
    return with_crc(bytes([icd.SLAVE_ADDR, FC_WRITE_SINGLE]) + u16_pair(addr) + u16_pair(value))


def req_write_multi(addr, values):
    body = bytes([icd.SLAVE_ADDR, FC_WRITE_MULTI]) + u16_pair(addr) + u16_pair(len(values)) + bytes([len(values) * 2])
    for v in values:
        body += u16_pair(v)
    return with_crc(body)


# 응답 프레임 (슬레이브 → 마스터)
def resp_read(fc, values):
    body = bytes([icd.SLAVE_ADDR, fc, len(values) * 2])
    for v in values:
        body += u16_pair(v)
    return with_crc(body)


def resp_write_ok(request):
    return with_crc(request[:6])


def resp_exception(fc, code):
    return with_crc(bytes([icd.SLAVE_ADDR, fc | 0x80, code]))


def parse_read_values(resp):
    count = resp[2] // 2
    return [(resp[3 + 2 * i] << 8) | resp[4 + 2 * i] for i in range(count)]


# 프레임 길이 판정 (0 = 더 필요, -1 = 모르는 FC)
def request_len(buf):
    if len(buf) < 2:
        return 0
    fc = buf[1]
    if fc in (FC_READ_HOLDING, FC_READ_INPUT, FC_WRITE_SINGLE):
        return 8
    if fc == FC_WRITE_MULTI:
        if len(buf) < 7:
            return 0
        return 9 + buf[6]
    return -1


def response_len(buf):
    if len(buf) < 2:
        return 0
    fc = buf[1]
    is_exception = (fc & 0x80) != 0
    if is_exception:
        return 5
    if fc in (FC_READ_HOLDING, FC_READ_INPUT):
        if len(buf) < 3:
            return 0
        return 5 + buf[2]
    if fc in (FC_WRITE_SINGLE, FC_WRITE_MULTI):
        return 8
    return -1


def read_frame(fd, length_fn, timeout_s):
    buf = bytearray()
    deadline = time.monotonic() + timeout_s
    while True:
        need = length_fn(buf)
        if need < 0:
            del buf[0]
            continue
        is_complete = (need > 0) and (len(buf) >= need)
        if is_complete:
            frame = bytes(buf[:need])
            if is_crc_ok(frame):
                return frame
            del buf[0]
            continue
        remain = deadline - time.monotonic()
        if remain <= 0:
            return None
        ready, _, _ = select.select([fd], [], [], remain)
        if not ready:
            return None
        chunk = os.read(fd, kReadChunk)
        if not chunk:
            return None
        buf += chunk


def transact(fd, request, timeout_s):
    """요청 1회 보내고 응답 프레임 대기"""
    termios.tcflush(fd, termios.TCIFLUSH)
    os.write(fd, request)
    return read_frame(fd, response_len, timeout_s)
