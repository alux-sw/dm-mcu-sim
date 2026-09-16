"""MCU 슬레이브 시뮬레이터: ICD-XS-DM-MCU v0.1 레지스터 맵·명령·인터락을 흉내 낸다"""
import collections
import os
import sys
import threading
import time

import icd
import modbus_rtu as mb
import webapi

kDefaultPort = "/dev/ttyUSB0"
kHttpPort = 8881
kTickSec = 0.1
kCoverMoveSec = 3.0
kSlideMoveSec = 4.0
kMotionCurrentmA = 1200
kChargerDefaultLimit10mA = 1000
kChargerVoltage10mV = 5040
kChargerCurrent10mA = 500
kFwVersion = (0, 1, 0)
kResetDelaySec = 0.5
kLogLen = 100
kValueMax = {icd.SET_CLIMATE_MODE: 1, icd.SET_LIGHT: 3, icd.SET_ALARM_OUT: 3, icd.SET_LED_PATTERN: 9}
kReadback = {
    icd.SET_CLIMATE_MODE: icd.CLIMATE_MODE,
    icd.SET_LIGHT: icd.LIGHT_STATE,
    icd.SET_ALARM_OUT: icd.ALARM_OUT_STATE,
    icd.SET_LED_PATTERN: icd.LED_PATTERN,
}
kInjectDefaults = {
    "estop": False, "ac_ok": True, "flood": False, "drone_detected": False, "bms_link": True,
    "overcurrent": False, "limit_conflict": False, "mute": False,
    "contact_temp": 25.0, "temp_in": 25.0, "hum_in": 45.0,
}


def u16(value):
    return value & 0xFFFF


def to_signed(value):
    if value >= 0x8000:
        return value - 0x10000
    return value


def approach(pos, target, step):
    if pos < target:
        return min(pos + step, target)
    if pos > target:
        return max(pos - step, target)
    return pos


class Mcu:
    def __init__(self):
        self.lock = threading.Lock()
        self.log = collections.deque(maxlen=kLogLen)
        self.inject = dict(kInjectDefaults)
        self.now = 0.0
        self.reset()

    def reset(self):
        self.holding = {addr: icd.HOLDING_DEFAULTS.get(addr, 0) for addr in icd.HOLDING_NAMES}
        self.inputs = [0] * icd.INPUT_COUNT
        self.boot_at = self.now
        self.last_rx = self.now
        self.last_cmd_seq = 0
        self.safe_hold = False
        self.hb_timeout = False
        self.fault_code = 0
        self.hard_block = 0
        self.active = None
        self.front_pos = 0.0
        self.side_pos = 0.0
        self.slide_pos = 0.0
        self.chg_on = False
        self.chg_fault = 0
        self.chg_limit_arg = 0
        self.bms_pwr = 1
        self.bms_regs = {}
        self.bms_lost_at = None
        self.timers = []
        self.note("MCU boot")

    def note(self, msg):
        line = "%8.1f %s" % (self.now, msg)
        self.log.append(line)
        print(line, flush=True)

    # --- Modbus ---
    def on_rx(self):
        self.last_rx = self.now
        if self.hb_timeout:
            self.hb_timeout = False
            self.note("heartbeat restored")

    def handle(self, frame):
        """요청 프레임 → 응답 프레임"""
        fc = frame[1]
        addr = (frame[2] << 8) | frame[3]
        if fc == mb.FC_READ_INPUT:
            count = (frame[4] << 8) | frame[5]
            is_in_range = (count >= 1) and (addr + count <= icd.INPUT_COUNT)
            if not is_in_range:
                return mb.resp_exception(fc, mb.EX_ILLEGAL_ADDR)
            return mb.resp_read(fc, self.inputs[addr:addr + count])
        if fc == mb.FC_READ_HOLDING:
            count = (frame[4] << 8) | frame[5]
            addrs = range(addr, addr + count)
            is_defined = (count >= 1) and all(a in self.holding for a in addrs)
            if not is_defined:
                return mb.resp_exception(fc, mb.EX_ILLEGAL_ADDR)
            return mb.resp_read(fc, [self.holding[a] for a in addrs])
        if fc == mb.FC_WRITE_SINGLE:
            value = (frame[4] << 8) | frame[5]
            return self.write({addr: value}, frame)
        if fc == mb.FC_WRITE_MULTI:
            count = (frame[4] << 8) | frame[5]
            values = {}
            for i in range(count):
                values[addr + i] = (frame[7 + 2 * i] << 8) | frame[8 + 2 * i]
            return self.write(values, frame)
        return mb.resp_exception(fc, mb.EX_ILLEGAL_FUNCTION)

    def write(self, values, frame):
        is_defined = all(a in self.holding for a in values)
        if not is_defined:
            return mb.resp_exception(frame[1], mb.EX_ILLEGAL_ADDR)
        is_valid = all(self.is_value_ok(a, v) for a, v in values.items())
        if not is_valid:
            return mb.resp_exception(frame[1], mb.EX_ILLEGAL_VALUE)
        self.holding.update(values)
        for a in values:
            if a in kReadback:
                self.inputs[kReadback[a]] = self.holding[a]
        if icd.CMD_SEQ in values:
            self.on_command()
        return mb.resp_write_ok(frame)

    def is_value_ok(self, addr, value):
        if addr in kValueMax:
            return value <= kValueMax[addr]
        if addr == icd.CFG_HB_TIMEOUT:
            return value >= 10
        return True

    # --- 명령 ---
    def on_command(self):
        seq = self.holding[icd.CMD_SEQ]
        code = self.holding[icd.CMD_CODE]
        a0 = self.holding[icd.CMD_ARG0]
        a1 = self.holding[icd.CMD_ARG1]
        is_new = (seq != 0) and (seq != self.last_cmd_seq)
        if not is_new:
            return
        self.last_cmd_seq = seq
        name = icd.CMD_NAMES.get(code, hex(code))
        reason = self.reject_reason(code, a0, a1)
        self.inputs[icd.ACK_SEQ] = seq
        self.inputs[icd.ACK_REASON] = reason
        if reason != icd.OK:
            self.inputs[icd.ACK_RESULT] = 1
            self.note("seq %d %s REJECT %s" % (seq, name, icd.REASON_NAMES.get(reason, hex(reason))))
            return
        self.inputs[icd.ACK_RESULT] = 0
        self.note("seq %d %s ACK" % (seq, name))
        self.execute(seq, code, a0, a1)

    def reject_reason(self, code, a0, a1):
        if code not in icd.CMD_NAMES:
            return icd.UNKNOWN_CMD
        is_motion = code in icd.MOTION_CMDS
        is_busy = self.active is not None
        is_cover = code in (icd.COVER_OPEN, icd.COVER_CLOSE)
        if is_cover and a0 > 3:
            return icd.BAD_ARG
        if is_motion:
            if self.fault_code != 0:
                return icd.FAULT_LATCHED
            if self.safe_hold:
                return icd.SAFE_HOLD
            if is_busy:
                return icd.BUSY
        for hi_no in icd.CMD_HI_REJECT.get(code, ()):
            is_blocked = (self.hard_block & (1 << (hi_no - 1))) != 0
            if is_blocked:
                return hi_no
        if code == icd.CHARGE_ON:
            is_overtemp = self.inject["contact_temp"] * 10 > to_signed(self.holding[icd.CFG_CONTACT_TEMP_MAX])
            if is_overtemp:
                return icd.CONTACT_OVERTEMP
            if not self.inject["ac_ok"]:
                return icd.NO_AC
        if code in icd.BMS_CMDS:
            if not self.inject["bms_link"]:
                return icd.BMS_NO_LINK
        if code == icd.BMS_WRITE_WORD:
            if a0 not in icd.BMS_WRITE_ALLOWED:
                return icd.BAD_ARG
        if code in (icd.CLEAR_HOLD, icd.CLEAR_FAULT):
            if self.inject["estop"]:
                return icd.HI6
        if code == icd.CLEAR_FAULT:
            if self.is_fault_cause_active():
                return self.fault_code
        if code == icd.MCU_RESET:
            if a0 != icd.MCU_RESET_MAGIC:
                return icd.BAD_ARG
            if is_busy:
                return icd.BUSY
        if code == icd.STATION_POWER_CYCLE:
            if a0 != icd.POWER_CYCLE_MAGIC:
                return icd.BAD_ARG
            is_unsafe = is_busy or self.chg_on or self.is_cover_open()
            if is_unsafe:
                return icd.BUSY
        return icd.OK

    def is_fault_cause_active(self):
        if self.fault_code == icd.HI4:
            return self.inject["overcurrent"]
        if self.fault_code == icd.HI6:
            return self.inject["estop"]
        if self.fault_code == icd.LIMIT_CONFLICT:
            return self.inject["limit_conflict"]
        return False

    def is_cover_open(self):
        return (self.front_pos > 0.0) or (self.side_pos > 0.0)

    def execute(self, seq, code, a0, a1):
        if code in icd.MOTION_CMDS:
            timeout_reg = icd.CFG_COVER_TIMEOUT
            if code in (icd.SLIDE_EXTEND, icd.SLIDE_RETRACT):
                timeout_reg = icd.CFG_SLIDE_TIMEOUT
            self.active = {"seq": seq, "code": code, "mask": a0, "t0": self.now,
                           "deadline": self.now + self.holding[timeout_reg] * 0.1}
            self.inputs[icd.ACTIVE_SEQ] = seq
            self.inputs[icd.PROGRESS_PCT] = 0
            return
        if code == icd.CHARGE_ON:
            self.chg_limit_arg = a0
            self.chg_fault = 0
            self.chg_on = True
            if not self.inject["drone_detected"]:
                self.chg_on = False
                self.chg_fault = 3
                self.done(seq, 3, 0)
                return
            self.done(seq, 0, 0)
            return
        if code == icd.CHARGE_OFF:
            self.chg_on = False
            self.chg_fault = 0
            self.done(seq, 0, 0)
            return
        if code == icd.BMS_POWER_ON:
            self.bms_pwr = 1
            self.done(seq, 0, 0)
            return
        if code == icd.BMS_POWER_OFF:
            self.bms_pwr = 0
            self.done(seq, 0, 0)
            return
        if code == icd.MOTION_STOP:
            self.abort_motion(2)
            self.enter_safe_hold("MOTION_STOP")
            self.done(seq, 0, 0)
            return
        if code == icd.CLEAR_HOLD:
            self.safe_hold = False
            self.done(seq, 0, 0)
            return
        if code == icd.CLEAR_FAULT:
            self.fault_code = 0
            self.done(seq, 0, 0)
            return
        if code == icd.BMS_READ_WORD:
            self.done(seq, 0, self.bms_regs.get(a0, 0))
            return
        if code == icd.BMS_WRITE_WORD:
            self.bms_regs[a0] = a1
            if a0 == 0x80:
                self.bms_pwr = a1 & 1
            self.done(seq, 0, 0)
            return
        if code == icd.MCU_RESET:
            self.timers.append((self.now + kResetDelaySec, self.reset))
            return
        if code == icd.STATION_POWER_CYCLE:
            delay = a1
            if delay == 0:
                delay = icd.POWER_CYCLE_DEFAULT_DELAY_S
            self.timers.append((self.now + delay, lambda: self.power_cycle(seq)))
            return

    def power_cycle(self, seq):
        self.note("station power cycle (Orin off → on)")
        self.done(seq, 0, 0)

    def done(self, seq, result, data):
        self.inputs[icd.DONE_SEQ] = seq
        self.inputs[icd.DONE_RESULT] = result
        self.inputs[icd.DONE_DATA] = u16(data)
        self.note("seq %d DONE %s data=%d" % (seq, icd.DONE_RESULT_NAMES.get(result, result), data))

    def abort_motion(self, result):
        if self.active is None:
            return
        elapsed = int((self.now - self.active["t0"]) * 10)
        self.done(self.active["seq"], result, elapsed)
        self.active = None
        self.inputs[icd.ACTIVE_SEQ] = 0

    def enter_safe_hold(self, why):
        if self.safe_hold:
            return
        self.safe_hold = True
        self.abort_motion(2)
        self.note("SAFE-HOLD (%s)" % why)

    def latch_fault(self, code):
        if self.fault_code != 0:
            return
        self.fault_code = code
        self.abort_motion(4)
        self.note("FAULT latched %s" % icd.REASON_NAMES.get(code, hex(code)))

    # --- 주기 처리 ---
    def tick(self):
        self.now += kTickSec
        self.run_timers()
        self.tick_heartbeat()
        self.tick_interlocks()
        self.tick_motion()
        self.tick_charger()
        self.fill_inputs()

    def run_timers(self):
        due = [t for t in self.timers if t[0] <= self.now]
        self.timers = [t for t in self.timers if t[0] > self.now]
        for _, fn in due:
            fn()

    def tick_heartbeat(self):
        is_timed_out = (self.now - self.last_rx) > self.holding[icd.CFG_HB_TIMEOUT] * 0.1
        if is_timed_out and not self.hb_timeout:
            self.hb_timeout = True
            self.note("heartbeat timeout")
            self.enter_safe_hold("heartbeat timeout")

    def tick_interlocks(self):
        is_slide_home = self.slide_pos <= 0.0
        is_cover_open = (self.front_pos >= 1.0) and (self.side_pos >= 1.0)
        block = 0
        if not is_slide_home:
            block |= (1 << 0) | (1 << 4)
        if not is_cover_open:
            block |= (1 << 1)
        if self.chg_on:
            block |= (1 << 2)
        if self.inject["overcurrent"]:
            block |= (1 << 3)
        if self.inject["estop"]:
            block |= (1 << 5)
        self.hard_block = block
        if self.inject["overcurrent"]:
            self.latch_fault(icd.HI4)
        if self.inject["limit_conflict"]:
            self.latch_fault(icd.LIMIT_CONFLICT)
        if self.inject["estop"]:
            self.latch_fault(icd.HI6)
            self.enter_safe_hold("E-Stop")

    def tick_motion(self):
        a = self.active
        if a is None:
            return
        code = a["code"]
        if code in (icd.COVER_OPEN, icd.COVER_CLOSE):
            target = 0.0
            if code == icd.COVER_OPEN:
                target = 1.0
            step = kTickSec / kCoverMoveSec
            is_front = (a["mask"] == 0) or (a["mask"] & 1) != 0
            is_side = (a["mask"] == 0) or (a["mask"] & 2) != 0
            moved = []
            if is_front:
                self.front_pos = approach(self.front_pos, target, step)
                moved.append(self.front_pos)
            if is_side:
                self.side_pos = approach(self.side_pos, target, step)
                moved.append(self.side_pos)
            is_done = all(p == target for p in moved)
            progress = min(abs(p - (1.0 - target)) for p in moved)
        else:
            target = 0.0
            if code == icd.SLIDE_EXTEND:
                target = 1.0
            self.slide_pos = approach(self.slide_pos, target, kTickSec / kSlideMoveSec)
            is_done = self.slide_pos == target
            progress = abs(self.slide_pos - (1.0 - target))
        self.inputs[icd.PROGRESS_PCT] = int(progress * 100)
        elapsed = int((self.now - a["t0"]) * 10)
        if is_done:
            self.inputs[icd.PROGRESS_PCT] = 100
            self.done(a["seq"], 0, elapsed)
            self.active = None
            self.inputs[icd.ACTIVE_SEQ] = 0
            return
        if self.now > a["deadline"]:
            self.done(a["seq"], 1, elapsed)
            self.active = None
            self.inputs[icd.ACTIVE_SEQ] = 0
            self.latch_fault(icd.MOTION_TIMEOUT)

    def tick_charger(self):
        if not self.chg_on:
            return
        is_overtemp = self.inject["contact_temp"] * 10 > to_signed(self.holding[icd.CFG_CONTACT_TEMP_MAX])
        if is_overtemp:
            self.chg_on = False
            self.chg_fault = 1
            self.note("charger off: contact overtemp")
            return
        if not self.inject["ac_ok"]:
            self.chg_on = False
            self.chg_fault = 3
            self.note("charger off: no AC")

    def applied_chg_limit(self):
        limit = self.chg_limit_arg
        if limit == 0:
            limit = self.holding[icd.SET_CHG_CURRENT_LIMIT]
        if limit == 0:
            limit = kChargerDefaultLimit10mA
        return limit

    def fill_inputs(self):
        inp = self.inputs
        inj = self.inject
        is_motion = self.active is not None
        status = 0
        if inj["estop"]:
            status |= 1 << 0
        if self.safe_hold:
            status |= 1 << 1
        if self.fault_code != 0:
            status |= 1 << 2
        if self.hb_timeout:
            status |= 1 << 3
        status |= 1 << 4
        if inj["bms_link"]:
            status |= 1 << 5
        if inj["drone_detected"]:
            status |= 1 << 6
        if is_motion:
            status |= 1 << 7
        inp[icd.MCU_STATUS] = status
        inp[icd.HARD_BLOCK] = self.hard_block
        inp[icd.FAULT_CODE] = self.fault_code
        inp[icd.MCU_TICK] = u16(int(self.now * 10))
        inp[icd.FW_VER_MAJ_MIN] = (kFwVersion[0] << 8) | kFwVersion[1]
        inp[icd.FW_VER_PATCH] = kFwVersion[2]
        uptime = int(self.now - self.boot_at)
        inp[icd.UPTIME_HI] = u16(uptime >> 16)
        inp[icd.UPTIME_LO] = u16(uptime)
        self.fill_cover_slide(is_motion)
        self.fill_charger()
        inp[icd.TEMP_IN] = u16(int(inj["temp_in"] * 10))
        inp[icd.HUM_IN] = int(inj["hum_in"] * 10)
        inp[icd.FLOOD] = int(inj["flood"])
        inp[icd.ENV_STALE] = 0
        pwr = 0
        if inj["ac_ok"]:
            pwr |= 1 << 0
        else:
            pwr |= 1 << 1
        inp[icd.PWR_FLAGS] = pwr
        inp[icd.UPS_VOLTAGE] = 2700
        inp[icd.UPS_SOC] = 100
        inp[icd.BUS24_V] = 2400
        inp[icd.BUS24_A] = 150
        inp[icd.BUS48_V] = 4800
        inp[icd.BUS48_A] = 20
        if self.chg_on:
            inp[icd.BUS48_A] = inp[icd.CHG_CURRENT]
        climate_out = 0
        is_auto = self.holding[icd.SET_CLIMATE_MODE] == 1
        if is_auto and inj["temp_in"] < 15:
            climate_out = (1 << 0) | (1 << 2)
        if is_auto and inj["temp_in"] > 35:
            climate_out = (1 << 1) | (1 << 2)
        inp[icd.CLIMATE_OUT] = climate_out
        self.fill_bms()

    def fill_cover_slide(self, is_motion):
        inp = self.inputs
        is_front_closed = self.front_pos <= 0.0
        is_front_open = self.front_pos >= 1.0
        is_side_closed = self.side_pos <= 0.0
        is_side_open = self.side_pos >= 1.0
        is_cover_motion = is_motion and self.active["code"] in (icd.COVER_OPEN, icd.COVER_CLOSE)
        state = 4
        if is_cover_motion and self.active["code"] == icd.COVER_OPEN:
            state = 1
        elif is_cover_motion:
            state = 3
        elif is_front_closed and is_side_closed:
            state = 0
        elif is_front_open and is_side_open:
            state = 2
        inp[icd.COVER_STATE] = state
        limits = 0
        if is_front_closed:
            limits |= (1 << 0) | (1 << 4)
        if is_front_open:
            limits |= 1 << 1
        if is_side_closed:
            limits |= (1 << 2) | (1 << 5)
        if is_side_open:
            limits |= 1 << 3
        if self.inject["limit_conflict"]:
            limits |= (1 << 0) | (1 << 1)
        inp[icd.COVER_LIMITS] = limits
        inp[icd.COVER_CURRENT] = 0
        if is_cover_motion:
            inp[icd.COVER_CURRENT] = kMotionCurrentmA
        is_slide_motion = is_motion and not is_cover_motion
        state = 4
        if is_slide_motion and self.active["code"] == icd.SLIDE_EXTEND:
            state = 1
        elif is_slide_motion:
            state = 3
        elif self.slide_pos <= 0.0:
            state = 0
        elif self.slide_pos >= 1.0:
            state = 2
        inp[icd.SLIDE_STATE] = state
        limits = 0
        if self.slide_pos <= 0.0:
            limits |= 1 << 0
        if self.slide_pos >= 1.0:
            limits |= 1 << 1
        inp[icd.SLIDE_LIMITS] = limits
        inp[icd.SLIDE_CURRENT] = 0
        if is_slide_motion:
            inp[icd.SLIDE_CURRENT] = kMotionCurrentmA
        inp[icd.SLIDE_ENCODER] = int(self.slide_pos * 1000)

    def fill_charger(self):
        inp = self.inputs
        state = 0
        if self.chg_on:
            state = 1
        if self.chg_fault != 0:
            state = 2
        inp[icd.CHG_STATE] = state
        inp[icd.CHG_OUTPUT_ON] = int(self.chg_on)
        inp[icd.CHG_VOLTAGE] = 0
        inp[icd.CHG_CURRENT] = 0
        if self.chg_on:
            inp[icd.CHG_VOLTAGE] = kChargerVoltage10mV
            inp[icd.CHG_CURRENT] = min(kChargerCurrent10mA, self.applied_chg_limit())
        inp[icd.CHG_CURRENT_LIMIT] = self.applied_chg_limit()
        inp[icd.CONTACT_TEMP] = u16(int(self.inject["contact_temp"] * 10))
        inp[icd.CHG_FAULT_CODE] = self.chg_fault

    def fill_bms(self):
        inp = self.inputs
        if not self.inject["bms_link"]:
            if self.bms_lost_at is None:
                self.bms_lost_at = self.now
                self.note("BMS link lost")
            inp[icd.BMS_LINK] = 0
            inp[icd.BMS_AGE] = u16(int((self.now - self.bms_lost_at) * 10))
            return
        if self.bms_lost_at is not None:
            self.bms_lost_at = None
            self.note("BMS link up")
        current_ma = -200
        if self.chg_on:
            current_ma = inp[icd.CHG_CURRENT] * 10
        inp[icd.BMS_LINK] = 1
        inp[icd.BMS_AGE] = 0
        inp[icd.BMS_BATTERY_STATUS] = 0x00C0
        inp[icd.BMS_VOLTAGE] = 24600
        inp[icd.BMS_CURRENT_HI] = u16(current_ma >> 16)
        inp[icd.BMS_CURRENT_LO] = u16(current_ma)
        inp[icd.BMS_RSOC] = 80
        inp[icd.BMS_REMAIN] = 8000
        inp[icd.BMS_TEMP] = 2980
        for i in range(6):
            inp[icd.BMS_CELL1 + i] = 4100
        inp[icd.BMS_CYCLE_COUNT] = 12
        inp[icd.BMS_FAULT_FLAGS_HI] = 0
        inp[icd.BMS_FAULT_FLAGS_LO] = 0
        inp[icd.BMS_PWR_STATE] = self.bms_pwr
        inp[icd.BMS_CHG_FET] = 1
        inp[icd.BMS_DSG_FET] = 1
        inp[icd.BMS_CHARGING_CURRENT] = 5000
        inp[icd.BMS_CHARGING_VOLTAGE] = 25200
        inp[icd.BMS_SNAPSHOT_AGE] = 50
        inp[icd.BMS_TEMP_SHUNT] = 250
        inp[icd.BMS_TEMP_CELL] = 250
        inp[icd.BMS_TEMP_FET] = 260
        inp[icd.BMS_TEMP_INT] = 270
        inp[icd.BMS_PF_STATUS_HI] = 0
        inp[icd.BMS_PF_STATUS_LO] = 0
        inp[icd.BMS_SAFETY_STATUS_HI] = 0
        inp[icd.BMS_SAFETY_STATUS_LO] = 0
        inp[icd.BMS_AVG_TIME_TO_FULL] = 30
        inp[icd.BMS_CELL_MAX] = 4100
        inp[icd.BMS_CELL_MIN] = 4100
        inp[icd.BMS_SERIAL_NUMBER] = 1234
        inp[icd.BMS_MANUFACTURE_DATE] = ((2026 - 1980) << 9) | (9 << 5) | 1
        inp[icd.BMS_DESIGN_CAPACITY] = 10000
        inp[icd.BMS_DESIGN_VOLTAGE] = 22200
        inp[icd.BMS_FULL_CHARGE_CAPACITY] = 9800
        inp[icd.BMS_DEVICE_TYPE] = 1
        inp[icd.BMS_FW_VERSION] = 0x0102
        inp[icd.BMS_HW_VERSION] = 0x0001

    # --- HTTP ---
    def snapshot(self):
        with self.lock:
            active = None
            if self.active is not None:
                active = {"seq": self.active["seq"], "name": icd.CMD_NAMES[self.active["code"]]}
            return {
                "inject": dict(self.inject),
                "internal": {
                    "time": round(self.now, 1),
                    "front_pos": round(self.front_pos, 2),
                    "side_pos": round(self.side_pos, 2),
                    "slide_pos": round(self.slide_pos, 2),
                    "active": active,
                    "safe_hold": self.safe_hold,
                    "fault": icd.REASON_NAMES.get(self.fault_code, hex(self.fault_code)),
                    "hb_timeout": self.hb_timeout,
                    "hb_age": round(self.now - self.last_rx, 1),
                    "chg_on": self.chg_on,
                    "bms_pwr": self.bms_pwr,
                    "last_cmd_seq": self.last_cmd_seq,
                },
                "holding": {icd.HOLDING_NAMES[a]: v for a, v in self.holding.items()},
                "log": list(self.log),
            }

    def set_inject(self, body):
        with self.lock:
            for key, value in body.items():
                if key in self.inject:
                    self.inject[key] = type(kInjectDefaults[key])(value)
                    self.note("inject %s=%s" % (key, self.inject[key]))
        return self.snapshot()


def serve_serial(mcu, fd):
    while True:
        frame = mb.read_frame(fd, mb.request_len, 1.0)
        if frame is None:
            continue
        if frame[0] != icd.SLAVE_ADDR:
            continue
        with mcu.lock:
            mcu.on_rx()
            resp = mcu.handle(frame)
            is_muted = mcu.inject["mute"]
        if is_muted:
            continue
        os.write(fd, resp)


def main():
    port = kDefaultPort
    if len(sys.argv) > 1:
        port = sys.argv[1]
    fd = mb.open_serial(port)
    mcu = Mcu()
    threading.Thread(target=serve_serial, args=(mcu, fd), daemon=True).start()
    webapi.serve(kHttpPort, {
        ("GET", "/api/state"): lambda body: mcu.snapshot(),
        ("POST", "/api/inject"): mcu.set_inject,
    })
    print("mcu_sim: %s, http :%d" % (port, kHttpPort), flush=True)
    next_at = time.monotonic()
    while True:
        next_at += kTickSec
        time.sleep(max(0.0, next_at - time.monotonic()))
        with mcu.lock:
            mcu.tick()


if __name__ == "__main__":
    main()
