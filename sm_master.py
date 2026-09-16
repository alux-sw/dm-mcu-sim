"""SM(Station Manager) 마스터 프로토타입: ICD 폴링 주기로 MCU 를 읽고 명령·설정을 쓴다"""
import collections
import os
import queue
import sys
import threading
import time

import icd
import modbus_rtu as mb
import webapi

kDefaultPort = "/dev/ttyTHS1"
kHttpPort = 8880
kStatusPeriod = 0.1
kBmsChargingPeriod = 1.0
kBmsIdlePeriod = 5.0
kHeartbeatPeriod = 1.0
kResponseTimeout = 0.1
kRetries = 1
kFrameLogLen = 40
kCmdLogLen = 50
kGuiFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui.html")


def to_signed(value):
    if value >= 0x8000:
        return value - 0x10000
    return value


def bits(value, names):
    return [names[i] for i in range(len(names)) if (value >> i) & 1]


class Sm:
    def __init__(self, fd, port):
        self.fd = fd
        self.port = port
        self.lock = threading.Lock()
        self.jobs = queue.Queue()
        self.regs = [0] * icd.INPUT_COUNT
        self.holding = {addr: 0 for addr in icd.HOLDING_NAMES}
        self.stats = {"ok": 0, "timeout": 0, "exception": 0}
        self.frames = collections.deque(maxlen=kFrameLogLen)
        self.cmds = collections.deque(maxlen=kCmdLogLen)
        self.hb_seq = 0
        self.cmd_seq = 0
        self.last_status_at = 0.0
        self.last_error = ""
        self.is_bms_ident_read = False

    # --- Modbus 왕복 ---
    def transact(self, request):
        """요청 (+재시도 1회) → 응답 프레임, 실패 시 None"""
        for _ in range(kRetries + 1):
            self.frames.append([time.time(), "TX", request.hex()])
            resp = mb.transact(self.fd, request, kResponseTimeout)
            if resp is None:
                self.stats["timeout"] += 1
                self.last_error = "timeout"
                continue
            self.frames.append([time.time(), "RX", resp.hex()])
            is_exception = (resp[1] & 0x80) != 0
            if is_exception:
                self.stats["exception"] += 1
                self.last_error = "exception fc=0x%02x code=0x%02x" % (resp[1] & 0x7F, resp[2])
                return None
            self.stats["ok"] += 1
            return resp
        return None

    def read_inputs(self, start, count):
        resp = self.transact(mb.req_read(mb.FC_READ_INPUT, start, count))
        if resp is None:
            return False
        values = mb.parse_read_values(resp)
        with self.lock:
            self.regs[start:start + count] = values
        return True

    def write_single(self, addr, value):
        resp = self.transact(mb.req_write_single(addr, value))
        if resp is None:
            return False
        with self.lock:
            self.holding[addr] = value
        return True

    def write_multi(self, addr, values):
        resp = self.transact(mb.req_write_multi(addr, values))
        if resp is None:
            return False
        with self.lock:
            for i, v in enumerate(values):
                self.holding[addr + i] = v
        return True

    def read_holding_all(self):
        """정의된 보유 레지스터를 연속 구간별로 0x03 읽어 holding 에 채운다"""
        addrs = sorted(icd.HOLDING_NAMES)
        start = addrs[0]
        prev = addrs[0]
        for a in addrs[1:] + [None]:
            is_contiguous = (a is not None) and (a == prev + 1)
            if is_contiguous:
                prev = a
                continue
            resp = self.transact(mb.req_read(mb.FC_READ_HOLDING, start, prev - start + 1))
            if resp is not None:
                with self.lock:
                    for i, v in enumerate(mb.parse_read_values(resp)):
                        self.holding[start + i] = v
            start = a
            prev = a

    # --- 폴링 루프 ---
    def loop(self):
        self.read_holding_all()
        now = time.monotonic()
        next_status = now
        next_bms = now
        next_hb = now
        while True:
            self.run_jobs()
            now = time.monotonic()
            if now >= next_hb:
                next_hb = now + kHeartbeatPeriod
                self.hb_seq = (self.hb_seq + 1) & 0xFFFF
                self.write_single(icd.HB_SEQ, self.hb_seq)
            if now >= next_status:
                next_status = now + kStatusPeriod
                self.poll_status()
            if now >= next_bms:
                next_bms = now + self.bms_period()
                self.poll_bms()
            wait = min(next_status, next_bms, next_hb) - time.monotonic()
            if wait > 0:
                time.sleep(wait)

    def run_jobs(self):
        while not self.jobs.empty():
            job = self.jobs.get()
            kind = job[0]
            if kind == "cmd":
                is_sent = self.write_multi(icd.CMD_SEQ, job[1:])
                with self.lock:
                    for c in self.cmds:
                        if c["seq"] == job[1]:
                            c["sent"] = is_sent
            if kind == "write":
                self.write_single(job[1], job[2])

    def poll_status(self):
        is_ok = self.read_inputs(*icd.STATUS_BLOCK)
        if not is_ok:
            return
        with self.lock:
            self.last_status_at = time.monotonic()
            self.track_cmds()

    def poll_bms(self):
        is_ok = self.read_inputs(*icd.BMS_BLOCK)
        if not is_ok:
            return
        is_linked = self.regs[icd.BMS_LINK] == 1
        if not is_linked:
            self.is_bms_ident_read = False
            return
        if not self.is_bms_ident_read:
            self.is_bms_ident_read = self.read_inputs(*icd.BMS_IDENT_BLOCK)

    def bms_period(self):
        is_charging = self.regs[icd.CHG_STATE] == 1
        if is_charging:
            return kBmsChargingPeriod
        return kBmsIdlePeriod

    def track_cmds(self):
        r = self.regs
        now = time.time()
        for c in self.cmds:
            is_acked = (c["ack"] is None) and (r[icd.ACK_SEQ] == c["seq"])
            if is_acked:
                c["ack"] = {"result": r[icd.ACK_RESULT], "reason": icd.REASON_NAMES.get(r[icd.ACK_REASON], hex(r[icd.ACK_REASON])), "t": now}
            is_done = (c["done"] is None) and (r[icd.DONE_SEQ] == c["seq"])
            if is_done:
                c["done"] = {"result": icd.DONE_RESULT_NAMES.get(r[icd.DONE_RESULT], r[icd.DONE_RESULT]), "data": r[icd.DONE_DATA], "t": now}

    # --- HTTP ---
    def send_command(self, body):
        code = int(body["code"])
        arg0 = int(body.get("arg0", 0))
        arg1 = int(body.get("arg1", 0))
        with self.lock:
            self.cmd_seq = self.cmd_seq % 65535 + 1
            seq = self.cmd_seq
            self.cmds.appendleft({"seq": seq, "name": icd.CMD_NAMES.get(code, hex(code)), "code": code,
                                  "arg0": arg0, "arg1": arg1, "t": time.time(), "sent": None, "ack": None, "done": None})
        self.jobs.put(("cmd", seq, code, arg0, arg1))
        return {"seq": seq}

    def write_setting(self, body):
        self.jobs.put(("write", int(body["addr"]), int(body["value"])))
        return {"ok": True}

    def icd_info(self, body):
        """툴팁용 ICD 설명: 이름 → [주소, 설명]"""
        return {
            "inputs": {name: [addr, icd.INPUT_DESC.get(addr, "")] for addr, name in icd.INPUT_NAMES.items()},
            "holding": {name: [addr, icd.HOLDING_DESC.get(addr, "")] for addr, name in icd.HOLDING_NAMES.items()},
            "cmds": {code: [name, icd.CMD_DESC.get(code, "")] for code, name in icd.CMD_NAMES.items()},
            "reasons": {name: icd.REASON_DESC.get(code, "") for code, name in icd.REASON_NAMES.items()},
        }

    def snapshot(self, body):
        with self.lock:
            r = list(self.regs)
            cmds = list(self.cmds)
            frames = list(self.frames)
            holding = dict(self.holding)
            age = time.monotonic() - self.last_status_at
        regs = {}
        for addr, name in icd.INPUT_NAMES.items():
            value = r[addr]
            if addr in icd.SIGNED_INPUTS:
                value = to_signed(value)
            regs[name] = value
        current = (r[icd.BMS_CURRENT_HI] << 16) | r[icd.BMS_CURRENT_LO]
        if current >= 0x80000000:
            current -= 0x100000000
        regs["BMS_CURRENT_mA"] = current
        regs["BMS_FAULT_FLAGS"] = (r[icd.BMS_FAULT_FLAGS_HI] << 16) | r[icd.BMS_FAULT_FLAGS_LO]
        regs["BMS_PF_STATUS"] = (r[icd.BMS_PF_STATUS_HI] << 16) | r[icd.BMS_PF_STATUS_LO]
        regs["BMS_SAFETY_STATUS"] = (r[icd.BMS_SAFETY_STATUS_HI] << 16) | r[icd.BMS_SAFETY_STATUS_LO]
        decoded = {
            "mcu_status": bits(r[icd.MCU_STATUS], icd.MCU_STATUS_BITS),
            "hard_block": bits(r[icd.HARD_BLOCK], icd.HARD_BLOCK_BITS),
            "fault": icd.REASON_NAMES.get(r[icd.FAULT_CODE], hex(r[icd.FAULT_CODE])),
            "local_btn": bits(r[icd.LOCAL_BTN], icd.LOCAL_BTN_BITS),
            "maint_source": icd.MAINT_SOURCE_NAMES.get(r[icd.MAINT_SOURCE], r[icd.MAINT_SOURCE]),
            "ack_reason": icd.REASON_NAMES.get(r[icd.ACK_REASON], hex(r[icd.ACK_REASON])),
            "done_result": icd.DONE_RESULT_NAMES.get(r[icd.DONE_RESULT], r[icd.DONE_RESULT]),
            "cover_state": icd.COVER_STATE_NAMES.get(r[icd.COVER_STATE], r[icd.COVER_STATE]),
            "cover_limits": bits(r[icd.COVER_LIMITS], icd.COVER_LIMIT_BITS),
            "slide_state": icd.SLIDE_STATE_NAMES.get(r[icd.SLIDE_STATE], r[icd.SLIDE_STATE]),
            "slide_limits": bits(r[icd.SLIDE_LIMITS], icd.SLIDE_LIMIT_BITS),
            "chg_state": icd.CHG_STATE_NAMES.get(r[icd.CHG_STATE], r[icd.CHG_STATE]),
            "chg_fault": icd.CHG_FAULT_NAMES.get(r[icd.CHG_FAULT_CODE], r[icd.CHG_FAULT_CODE]),
            "env_stale": bits(r[icd.ENV_STALE], icd.ENV_STALE_BITS),
            "pwr_flags": bits(r[icd.PWR_FLAGS], icd.PWR_FLAG_BITS),
            "climate_out": bits(r[icd.CLIMATE_OUT], icd.CLIMATE_OUT_BITS),
            "light": bits(r[icd.LIGHT_STATE], icd.LIGHT_BITS),
            "alarm": bits(r[icd.ALARM_OUT_STATE], icd.ALARM_BITS),
            "led_pattern": icd.LED_PATTERN_NAMES.get(r[icd.LED_PATTERN], r[icd.LED_PATTERN]),
            "fw": "%d.%d.%d" % (r[icd.FW_VER_MAJ_MIN] >> 8, r[icd.FW_VER_MAJ_MIN] & 0xFF, r[icd.FW_VER_PATCH]),
        }
        return {
            "link": {"port": self.port, "stats": dict(self.stats), "status_age": round(age, 2),
                     "hb_seq": self.hb_seq, "last_error": self.last_error},
            "regs": regs,
            "decoded": decoded,
            "holding": {icd.HOLDING_NAMES[a]: v for a, v in holding.items()},
            "cmds": cmds,
            "frames": frames,
        }


def main():
    port = kDefaultPort
    if len(sys.argv) > 1:
        port = sys.argv[1]
    fd = mb.open_serial(port)
    sm = Sm(fd, port)
    webapi.serve(kHttpPort, {
        ("GET", "/api/state"): sm.snapshot,
        ("GET", "/api/icd"): sm.icd_info,
        ("POST", "/api/cmd"): sm.send_command,
        ("POST", "/api/write"): sm.write_setting,
    }, html_path=kGuiFile)
    print("sm_master: %s, http :%d" % (port, kHttpPort), flush=True)
    sm.loop()


if __name__ == "__main__":
    main()
