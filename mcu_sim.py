"""MCU 슬레이브 시뮬레이터: 레지스터 맵·명령·인터락·현장 버튼"""
import collections
import os
import sys
import threading
import time

import camstream
import icd
import modbus_rtu as mb
import webapi

kDefaultPort = "/dev/ttyUSB0"
kHttpPort = int(os.environ.get("MCU_SIM_HTTP_PORT", "8881"))
kGuiFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim.html")
kDroneModelFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drone.glb")
kAssetDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
kTickSec = 0.1
kCoverMoveSec = 3.0
kSlideMoveSec = 4.0
kMotionTimeoutSec = 30.0
kHbTimeoutSec = 3.0
kContactTempMaxC = 60.0
kBtnHoldSec = 0.5
kMotionCurrentmA = 1200
kChargerDefaultLimit10mA = 1000
kChargerVoltage10mV = 5040
kChargerCurrent10mA = 500
kFwVersion = (1, 1, 0)
kBmsDesignCapacitymAh = 10000
kBmsCells = 8               # 드론 배터리 직렬 셀 수 (8S)
kBmsBootSec = 1.0           # BMS 부팅 직후 측정값 무효(ERROR_CODE 7) 시간 (SMBus 8절)
kBmsIdleOffSec = 300.0      # 출력 ON 에서 무부하가 이만큼 이어지면 BMS 가 출력 OFF (SMBus 5.5)
kBmsIdleMa = 100            # 무부하 판정 전류 절대값 미만 (mA)
kBmsTimeUnknown = 0xFFFF    # SBS 예상 시간 65535 = 해당 없음
kBmsErrorInit = 0x7         # BATTERY_STATUS ERROR_CODE: 측정값 없음 (부팅·내부 통신 이상)
kBmsStatusInitialized = 1 << 7
kBmsStatusDischarging = 1 << 6
kBmsStatusFull = 1 << 5
kBmsStatusEmpty = 1 << 4
kBmsFaultComm = 1 << 6
kBmsFaultPf = 1 << 31
# FAULT_FLAGS 비트 → (BATTERY_STATUS 알람 비트, 충전 차단, 방전 차단). SMBus 6.1 표
kBmsFaultEffects = {
    1 << 0: ((1 << 15) | (1 << 14), True, False),   # OV
    1 << 1: (1 << 11, False, False),                # UV
    1 << 2: ((1 << 12) | (1 << 14), True, False),   # OT
    1 << 3: ((1 << 12) | (1 << 14), True, False),   # UT
    1 << 4: (1 << 11, False, True),                 # OC_DSG
    1 << 5: (1 << 14, True, False),                 # OC_CHG
    1 << 8: (1 << 11, False, True),                 # UV_CRITICAL
    1 << 9: ((1 << 14) | (1 << 11), True, True),    # SHORT_CIRCUIT
    kBmsFaultPf: ((1 << 14) | (1 << 11), True, True),
}
kLogLen = 100
kValueMax = {
    icd.SET_CLIMATE_MODE: 1, icd.SET_LIGHT: 3, icd.SET_ALARM_OUT: 3,
    icd.SET_LED_PATTERN: 9, icd.SET_MAINT_MODE: 1,
}
kReadback = {
    icd.SET_CLIMATE_MODE: icd.CLIMATE_MODE,
    icd.SET_LIGHT: icd.LIGHT_STATE,
    icd.SET_ALARM_OUT: icd.ALARM_OUT_STATE,
    icd.SET_LED_PATTERN: icd.LED_PATTERN,
}
kButtons = ("btn_door", "btn_slide", "btn_maint")
kDroneLocations = ("docked", "airborne")   # 드론 mock 위치. docked 면 착륙판 하중(drone_detected)도 켜짐
# 화면에서 직접 바꿀 수 있는 MCU 내부 상태 (이름 → 형). 입력 레지스터는 이 값들로 계산된다
kSettable = {"fault_code": int, "safe_hold": bool, "cover_pos": float, "slide_pos": float, "chg_on": bool,
             "chg_fault": int, "bms_pwr": int, "maint_active": int, "maint_source": int,
             "bms_rsoc": float, "bms_cell_mv": int, "bms_temp_c": float,
             "bms_cycle_count": int, "bms_charging_current_ma": int,
             "bms_weak_cell": int, "bms_weak_cell_mv": int, "bms_charge_pct_per_s": float, "bms_load_ma": int,
             "bms_fault_flags": int, "bms_safety_alert": int, "bms_safety_status": int,
             "bms_pf_alert": int, "bms_pf_status": int, "bms_fet_unknown": bool}
kInjectDefaults = {
    "estop": False, "ac_ok": True, "drone_detected": True, "bms_link": True,
    "overcurrent": False, "limit_conflict": False, "mute": False,
    "btn_door": False, "btn_slide": False, "btn_maint": False,
    "contact_temp": 25.0, "temp_in": 25.0, "hum_in": 45.0,
    "cover_sec": kCoverMoveSec, "slide_sec": kSlideMoveSec, "motion_timeout_sec": kMotionTimeoutSec,
    "exc_code": 0, "exc_n": 0,          # 다음 n 회 응답을 예외로 (2 주소, 3 값, 4 장치오류)
    "bad_crc_n": 0,                     # 다음 n 회 응답의 CRC 를 깨서 보냅니다
    "resp_delay_ms": 0,                 # 응답을 이만큼 늦춥니다 (ICD 응답 대기 100ms)
}


kInputByName = {name: addr for addr, name in icd.INPUT_NAMES.items()}


def force_addr(key):
    """레지스터 이름이나 0xNN / 십진 주소를 입력 레지스터 주소로"""
    if key in kInputByName:
        return kInputByName[key]
    try:
        addr = int(key, 0)
    except (TypeError, ValueError):
        return None
    if 0 <= addr < icd.INPUT_COUNT:
        return addr
    return None


def u16(value):
    return value & 0xFFFF


def put32(regs, addr_hi, value):
    regs[addr_hi] = u16(value >> 16)
    regs[addr_hi + 1] = u16(value)


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
        self.force = {}                              # 입력 레지스터 강제값 {주소: 값}. 시뮬 계산보다 우선합니다
        self.now = 0.0
        self.holding = {addr: 0 for addr in icd.HOLDING_NAMES}
        self.inputs = [0] * icd.INPUT_COUNT
        self.last_rx = 0.0
        self.last_cmd_seq = 0
        self.safe_hold = False
        self.hb_timeout = False
        self.fault_code = 0
        self.hard_block = 0
        self.active = None
        self.cover_pos = 0.0
        self.slide_pos = 0.0
        self.chg_on = False
        self.chg_fault = 0
        self.chg_limit_arg = 0
        self.bms_pwr = 1
        self.bms_lost_at = None
        self.bms_rsoc = 80.0
        self.bms_cell_mv = 4100
        self.bms_temp_c = 25.0
        self.bms_cycle_count = 12
        self.bms_charging_current_ma = 5000
        self.bms_weak_cell = 0           # 이 번호(1~8) 셀만 bms_weak_cell_mv. 0 이면 전부 bms_cell_mv
        self.bms_weak_cell_mv = 3300
        self.bms_charge_pct_per_s = 0.5  # 충전 중 잔량이 오르는 속도 (%/s). 0 이면 충전이 멈춘 팩
        self.bms_load_ma = 200           # 충전 아닐 때 드론 소비 전류 (mA)
        self.bms_idle_since = None
        self.bms_fault_flags = 0
        self.bms_safety_alert = 0
        self.bms_safety_status = 0
        self.bms_pf_alert = 0
        self.bms_pf_status = 0
        self.bms_fet_unknown = False
        self.maint_active = 0
        self.maint_source = 0
        self.btn_release_at = {}
        self.drone = {"link": True, "location": "docked", "stowed_report": True}   # 드론 링크 mock (SM 이 /api/drone 으로 읽음)
        self.timers = []
        self.note("MCU boot")

    def note(self, msg):
        line = "%8.1f %s" % (self.now, msg)
        self.log.append(line)
        print(line, flush=True)

    def on_rx(self):
        self.last_rx = self.now
        if self.hb_timeout:
            self.hb_timeout = False
            self.note("heartbeat restored")

    def handle(self, frame):
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
        self.apply_holding(values)
        return mb.resp_write_ok(frame)

    def apply_holding(self, values):
        """보유 레지스터 갱신과 그 효과 (되읽기·정비 모드·명령 접수). 마스터 쓰기와 직접 설정이 같이 쓴다"""
        self.holding.update(values)
        for a in values:
            if a in kReadback:
                self.inputs[kReadback[a]] = self.holding[a]
        if icd.SET_MAINT_MODE in values:
            self.set_maint(values[icd.SET_MAINT_MODE], 1)
        if icd.CMD_SEQ in values:
            self.on_command()

    def is_value_ok(self, addr, value):
        if addr in kValueMax:
            return value <= kValueMax[addr]
        return True

    def set_maint(self, on, source):
        self.maint_active = on
        self.maint_source = 0
        if on == 1:
            self.maint_source = source
        self.note("maint mode %d (%s)" % (on, icd.MAINT_SOURCE_NAMES[self.maint_source]))

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
        self.leave_safe_hold()
        self.execute(seq, code, a0, a1)

    def reject_reason(self, code, a0, a1):
        if code not in icd.CMD_NAMES:
            return icd.UNKNOWN_CMD
        is_motion = code in icd.MOTION_CMDS
        is_busy = self.active is not None
        if is_motion:
            if self.fault_code != 0:
                return icd.FAULT_LATCHED
            if is_busy:
                return icd.BUSY
        hi_no = self.hard_block_reason(code)
        if hi_no != icd.OK:
            return hi_no
        if code == icd.CHARGE_ON:
            if self.inject["contact_temp"] > kContactTempMaxC:
                return icd.CONTACT_OVERTEMP
            if not self.inject["ac_ok"]:
                return icd.NO_AC
        if code in icd.BMS_CMDS:
            if not self.inject["bms_link"]:
                return icd.BMS_NO_LINK
        if code == icd.CLEAR_FAULT:
            if self.inject["estop"]:
                return icd.HI6
            if self.is_fault_cause_active():
                return self.fault_code
        if code == icd.STATION_POWER_CYCLE:
            if a0 != icd.POWER_CYCLE_MAGIC:
                return icd.BAD_ARG
            is_unsafe = is_busy or self.chg_on or self.cover_pos > 0.0
            if is_unsafe:
                return icd.BUSY
        return icd.OK

    def hard_block_reason(self, code):
        """이 명령을 막는 하드 인터락 번호. 없으면 OK"""
        for hi_no in icd.CMD_HI_REJECT.get(code, ()):
            is_blocked = (self.hard_block & (1 << (hi_no - 1))) != 0
            if is_blocked:
                return hi_no
        return icd.OK

    def is_fault_cause_active(self):
        if self.fault_code == icd.HI4:
            return self.inject["overcurrent"]
        if self.fault_code == icd.HI6:
            return self.inject["estop"]
        if self.fault_code == icd.LIMIT_CONFLICT:
            return self.inject["limit_conflict"]
        return False

    def execute(self, seq, code, a0, a1):
        if code in icd.MOTION_CMDS:
            self.start_motion(seq, code)
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
            self.bms_idle_since = None   # ON 을 다시 쓰면 무부하 5 분을 처음부터 센다
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
        if code == icd.CLEAR_FAULT:
            self.fault_code = 0
            self.done(seq, 0, 0)
            return
        if code == icd.STATION_POWER_CYCLE:
            delay = a1
            if delay == 0:
                delay = icd.POWER_CYCLE_DEFAULT_DELAY_S
            self.timers.append((self.now + delay, lambda: self.power_cycle(seq)))
            return

    def start_motion(self, seq, code):
        self.active = {"seq": seq, "code": code, "t0": self.now,
                       "deadline": self.now + self.inject["motion_timeout_sec"]}
        if seq != 0:
            self.inputs[icd.ACTIVE_SEQ] = seq
            self.inputs[icd.PROGRESS_PCT] = 0

    def power_cycle(self, seq):
        self.note("station power cycle (Orin off → on)")
        self.done(seq, 0, 0)

    def done(self, seq, result, data):
        self.inputs[icd.DONE_SEQ] = seq
        self.inputs[icd.DONE_RESULT] = result
        self.inputs[icd.DONE_DATA] = u16(data)
        self.note("seq %d DONE %s data=%d" % (seq, icd.DONE_RESULT_NAMES.get(result, result), data))

    def finish_motion(self, result):
        a = self.active
        elapsed = int((self.now - a["t0"]) * 10)
        is_local = a["seq"] == 0
        if is_local:
            self.note("local %s %s" % (icd.CMD_NAMES[a["code"]], icd.DONE_RESULT_NAMES.get(result, result)))
        else:
            self.done(a["seq"], result, elapsed)
        self.active = None
        self.inputs[icd.ACTIVE_SEQ] = 0

    def abort_motion(self, result):
        if self.active is None:
            return
        self.finish_motion(result)

    def enter_safe_hold(self, why):
        if self.safe_hold:
            return
        self.safe_hold = True
        self.abort_motion(2)
        self.note("SAFE-HOLD (%s)" % why)

    def leave_safe_hold(self):
        if not self.safe_hold:
            return
        self.safe_hold = False
        self.note("SAFE-HOLD cleared")

    def latch_fault(self, code):
        if self.fault_code != 0:
            return
        self.fault_code = code
        self.abort_motion(4)
        self.note("FAULT latched %d" % code)

    def on_button(self, key):
        if key == "btn_maint":
            self.set_maint(1 - self.maint_active, 2)
            return
        code = icd.COVER_OPEN
        if key == "btn_door" and self.cover_pos >= 1.0:
            code = icd.COVER_CLOSE
        if key == "btn_slide":
            code = icd.SLIDE_EXTEND
            if self.slide_pos >= 1.0:
                code = icd.SLIDE_RETRACT
        is_remote_motion = self.active is not None and self.active["seq"] != 0
        if is_remote_motion:
            is_same = self.active["code"] == code
            if is_same:   # SM 명령과 같은 동작이면 SM 명령을 그대로 둔다
                self.note("button %s same as seq %d, ignored" % (key, self.active["seq"]))
                return
            reason = self.hard_block_reason(code)
            if self.fault_code != 0:
                reason = icd.FAULT_LATCHED
            if reason != icd.OK:   # 할 수 없는 버튼 동작이면 SM 명령을 끊지 않는다
                self.note("button %s ignored: %s" % (key, icd.REASON_NAMES.get(reason, hex(reason))))
                return
            # 현장 우선: SM 명령 모션을 ABORTED 로 끝내고 버튼 동작을 받는다
            self.note("button %s preempts seq %d" % (key, self.active["seq"]))
            self.abort_motion(2)
        reason = self.reject_reason(code, 0, 0)
        if reason != icd.OK:
            self.note("button %s ignored: %s" % (key, icd.REASON_NAMES.get(reason, hex(reason))))
            return
        self.note("button %s → %s (local)" % (key, icd.CMD_NAMES[code]))
        self.leave_safe_hold()
        self.start_motion(0, code)

    def tick_buttons(self):
        for key in kButtons:
            is_new_press = self.inject[key] and key not in self.btn_release_at
            if is_new_press:
                self.btn_release_at[key] = self.now + kBtnHoldSec
                self.on_button(key)
        for key in list(self.btn_release_at):
            if self.now >= self.btn_release_at[key]:
                self.inject[key] = False
                del self.btn_release_at[key]

    def tick(self):
        self.now += kTickSec
        self.run_timers()
        self.tick_heartbeat()
        self.tick_motion()
        self.tick_interlocks()   # 모션 뒤에 판정해야 DONE 을 낸 틱의 HARD_BLOCK 이 새 위치 기준
        self.tick_buttons()
        self.tick_charger()
        self.fill_inputs()
        self.apply_force()

    def apply_force(self):
        for addr, value in self.force.items():
            self.inputs[addr] = value

    def run_timers(self):
        due = [t for t in self.timers if t[0] <= self.now]
        self.timers = [t for t in self.timers if t[0] > self.now]
        for _, fn in due:
            fn()

    def tick_heartbeat(self):
        is_timed_out = (self.now - self.last_rx) > kHbTimeoutSec
        if is_timed_out and not self.hb_timeout:
            self.hb_timeout = True
            self.note("heartbeat timeout")
            self.enter_safe_hold("heartbeat timeout")

    def tick_interlocks(self):
        is_slide_home = self.slide_pos <= 0.0
        is_cover_open = self.cover_pos >= 1.0
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
        target = 0.0
        if code in (icd.COVER_OPEN, icd.SLIDE_EXTEND):
            target = 1.0
        if code in (icd.COVER_OPEN, icd.COVER_CLOSE):
            self.cover_pos = approach(self.cover_pos, target, kTickSec / max(self.inject["cover_sec"], kTickSec))
            pos = self.cover_pos
        else:
            self.slide_pos = approach(self.slide_pos, target, kTickSec / max(self.inject["slide_sec"], kTickSec))
            pos = self.slide_pos
        is_local = a["seq"] == 0
        if not is_local:
            self.inputs[icd.PROGRESS_PCT] = int(abs(pos - (1.0 - target)) * 100)
        if pos == target:
            self.finish_motion(0)
            return
        if self.now > a["deadline"]:
            self.finish_motion(1)
            self.latch_fault(icd.MOTION_TIMEOUT)

    def tick_charger(self):
        if not self.chg_on:
            return
        if self.inject["contact_temp"] > kContactTempMaxC:
            self.chg_on = False
            self.chg_fault = 1
            self.note("charger off: contact overtemp")
            return
        if not self.inject["ac_ok"]:
            self.chg_on = False
            self.chg_fault = 3
            self.note("charger off: no AC")

    def tick_bms_idle(self, current_ma):
        """출력 ON 에서 |전류| < kBmsIdleMa 가 kBmsIdleOffSec 이어지면 BMS 가 출력을 스스로 끔"""
        is_idle = self.bms_pwr == 1 and abs(current_ma) < kBmsIdleMa
        if not is_idle:
            self.bms_idle_since = None
            return
        if self.bms_idle_since is None:
            self.bms_idle_since = self.now
        if self.now - self.bms_idle_since >= kBmsIdleOffSec:
            self.bms_pwr = 0
            self.bms_idle_since = None
            self.note("BMS output auto OFF (idle %d s)" % kBmsIdleOffSec)

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
        inp[icd.FW_VER_MAJ_MIN] = (kFwVersion[0] << 8) | kFwVersion[1]
        inp[icd.FW_VER_PATCH] = kFwVersion[2]
        local_btn = 0
        if inj["btn_door"]:
            local_btn |= 1 << 0
        if inj["btn_slide"]:
            local_btn |= 1 << 1
        inp[icd.LOCAL_BTN] = local_btn
        self.fill_cover_slide(is_motion)
        self.fill_charger()
        inp[icd.TEMP_IN] = u16(int(inj["temp_in"] * 10))
        inp[icd.HUM_IN] = int(inj["hum_in"] * 10)
        inp[icd.ENV_STALE] = 0
        pwr = 1 << 1
        if inj["ac_ok"]:
            pwr = 1 << 0
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
        inp[icd.MAINT_ACTIVE] = self.maint_active
        inp[icd.MAINT_SOURCE] = self.maint_source
        self.fill_bms()

    def fill_cover_slide(self, is_motion):
        inp = self.inputs
        is_closed = self.cover_pos <= 0.0
        is_open = self.cover_pos >= 1.0
        is_cover_motion = is_motion and self.active["code"] in (icd.COVER_OPEN, icd.COVER_CLOSE)
        state = 4
        if is_cover_motion and self.active["code"] == icd.COVER_OPEN:
            state = 1
        elif is_cover_motion:
            state = 3
        elif is_closed:
            state = 0
        elif is_open:
            state = 2
        inp[icd.COVER_STATE] = state
        limits = 0
        if is_closed:
            limits |= 1 << 0
        if is_open:
            limits |= 1 << 1
        if self.inject["limit_conflict"]:
            limits = (1 << 0) | (1 << 1)
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
        if self.inject["drone_detected"]:
            limits |= 1 << 2
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
        if self.chg_on and self.bms_pwr == 0:   # 충전기 전압을 보면 BMS 가 출력을 스스로 켬
            self.bms_pwr = 1
            self.note("BMS output auto ON (charger)")
        fault_flags = self.bms_fault_flags
        if self.bms_pf_status != 0:
            fault_flags |= kBmsFaultPf
        alarm_bits = 0
        is_chg_blocked = False
        is_dsg_blocked = False
        for bit, (alarms, blocks_chg, blocks_dsg) in kBmsFaultEffects.items():
            if fault_flags & bit:
                alarm_bits |= alarms
                is_chg_blocked = is_chg_blocked or blocks_chg
                is_dsg_blocked = is_dsg_blocked or blocks_dsg
        chg_fet = int(not is_chg_blocked)
        dsg_fet = int(self.bms_pwr == 1 and not is_dsg_blocked)
        is_charging = self.chg_on and chg_fet == 1
        current_ma = -self.bms_load_ma * dsg_fet
        if is_charging:
            current_ma = inp[icd.CHG_CURRENT] * 10
            self.bms_rsoc = min(100.0, self.bms_rsoc + self.bms_charge_pct_per_s * kTickSec)
        self.tick_bms_idle(current_ma)
        status = alarm_bits | kBmsStatusInitialized
        if current_ma <= 0:
            status |= kBmsStatusDischarging
        if self.bms_rsoc >= 100:
            status |= kBmsStatusFull
        if self.bms_rsoc <= 0:
            status |= kBmsStatusEmpty
        snapshot_age = 50
        if self.bms_pwr == 0:
            snapshot_age = 2500   # OFF 절전은 5 s 주기 측정
        is_measuring = self.now >= kBmsBootSec and not fault_flags & kBmsFaultComm
        if not is_measuring:
            status = kBmsErrorInit
            snapshot_age = 0xFFFF
        remain_mah = int(kBmsDesignCapacitymAh * self.bms_rsoc / 100)
        to_full_min = kBmsTimeUnknown
        if is_charging and self.bms_charge_pct_per_s > 0:
            to_full_min = int(-(-(100 - self.bms_rsoc) // (self.bms_charge_pct_per_s * 60)))
        to_empty_min = kBmsTimeUnknown
        if current_ma < 0:
            to_empty_min = min(remain_mah * 60 // -current_ma, kBmsTimeUnknown - 1)
        cells = [self.bms_cell_mv] * kBmsCells
        if 1 <= self.bms_weak_cell <= kBmsCells:
            cells[self.bms_weak_cell - 1] = self.bms_weak_cell_mv
        if self.bms_fet_unknown:
            chg_fet = 0xFF
            dsg_fet = 0xFF
        inp[icd.BMS_LINK] = 1
        inp[icd.BMS_AGE] = 0
        inp[icd.BMS_BATTERY_STATUS] = status
        inp[icd.BMS_VOLTAGE] = sum(cells)
        put32(inp, icd.BMS_CURRENT_HI, current_ma)
        inp[icd.BMS_RSOC] = int(self.bms_rsoc)
        inp[icd.BMS_REMAIN] = remain_mah
        inp[icd.BMS_TEMP] = int(round((self.bms_temp_c + 273.15) * 10))
        for i in range(kBmsCells):
            inp[icd.BMS_CELL1 + i] = cells[i]
        inp[icd.BMS_CYCLE_COUNT] = self.bms_cycle_count
        put32(inp, icd.BMS_FAULT_FLAGS_HI, fault_flags)
        inp[icd.BMS_PWR_STATE] = self.bms_pwr
        inp[icd.BMS_CHG_FET] = chg_fet
        inp[icd.BMS_DSG_FET] = dsg_fet
        inp[icd.BMS_CHARGING_CURRENT] = self.bms_charging_current_ma
        inp[icd.BMS_CHARGING_VOLTAGE] = 4200 * kBmsCells
        inp[icd.BMS_SNAPSHOT_AGE] = snapshot_age
        inp[icd.BMS_TEMP_SHUNT] = 250
        inp[icd.BMS_TEMP_CELL] = u16(int(round(self.bms_temp_c * 10)))
        inp[icd.BMS_TEMP_FET] = 260
        inp[icd.BMS_TEMP_INT] = 270
        put32(inp, icd.BMS_PF_STATUS_HI, self.bms_pf_status)
        put32(inp, icd.BMS_SAFETY_STATUS_HI, self.bms_safety_status)
        inp[icd.BMS_AVG_TIME_TO_FULL] = to_full_min
        inp[icd.BMS_CELL_MAX] = max(cells)
        inp[icd.BMS_CELL_MIN] = min(cells)
        put32(inp, icd.BMS_SAFETY_ALERT_HI, self.bms_safety_alert)
        put32(inp, icd.BMS_PF_ALERT_HI, self.bms_pf_alert)
        # ponytail: 평균 전류·평균 방전 시간은 순시값 그대로, 1 분 이동 평균이 필요하면 그때 deque 로
        put32(inp, icd.BMS_AVG_CURRENT_HI, current_ma)
        inp[icd.BMS_RUN_TIME_TO_EMPTY] = to_empty_min
        inp[icd.BMS_AVG_TIME_TO_EMPTY] = to_empty_min
        inp[icd.BMS_SERIAL_NUMBER] = 1234
        inp[icd.BMS_MANUFACTURE_DATE] = ((2026 - 1980) << 9) | (9 << 5) | 1
        inp[icd.BMS_DESIGN_CAPACITY] = kBmsDesignCapacitymAh
        inp[icd.BMS_DESIGN_VOLTAGE] = 3700 * kBmsCells
        inp[icd.BMS_FULL_CHARGE_CAPACITY] = 9800
        inp[icd.BMS_DEVICE_TYPE] = 1
        inp[icd.BMS_FW_VERSION] = 0x0102
        inp[icd.BMS_HW_VERSION] = 0x0001

    def snapshot(self):
        with self.lock:
            active = None
            if self.active is not None:
                active = {"seq": self.active["seq"], "name": icd.CMD_NAMES[self.active["code"]],
                          "local": self.active["seq"] == 0}
            return {
                "inject": dict(self.inject),
                "force": {icd.INPUT_NAMES.get(a, hex(a)): v for a, v in self.force.items()},
                "internal": {
                    "time": round(self.now, 1),
                    "cover_pos": round(self.cover_pos, 2),
                    "slide_pos": round(self.slide_pos, 2),
                    "active": active,
                    "safe_hold": self.safe_hold,
                    "fault": icd.REASON_NAMES.get(self.fault_code, hex(self.fault_code)),
                    "hb_timeout": self.hb_timeout,
                    "hb_age": round(self.now - self.last_rx, 1),
                    "chg_on": self.chg_on,
                    "bms_pwr": self.bms_pwr,
                    "last_cmd_seq": self.last_cmd_seq,
                    "progress": self.inputs[icd.PROGRESS_PCT],
                    "cover_state": icd.COVER_STATE_NAMES[self.inputs[icd.COVER_STATE]],
                    "slide_state": icd.SLIDE_STATE_NAMES[self.inputs[icd.SLIDE_STATE]],
                    "chg_state": icd.CHG_STATE_NAMES[self.inputs[icd.CHG_STATE]],
                    "chg_fault": icd.CHG_FAULT_NAMES[self.chg_fault],
                    "chg_volt": self.inputs[icd.CHG_VOLTAGE] / 100,
                    "chg_amp": self.inputs[icd.CHG_CURRENT] / 100,
                    "led_pattern": self.holding[icd.SET_LED_PATTERN],
                    "light": self.holding[icd.SET_LIGHT],
                    "alarm": self.holding[icd.SET_ALARM_OUT],
                    "climate_out": self.inputs[icd.CLIMATE_OUT],
                    "maint_active": self.maint_active,
                    "maint_source": icd.MAINT_SOURCE_NAMES[self.maint_source],
                },
                "drone": dict(self.drone),
                "holding": {icd.HOLDING_NAMES[a]: v for a, v in self.holding.items()},
                "settable": {k: getattr(self, k) for k in kSettable},
                "regs": {name: self.signed_input(a) for a, name in icd.INPUT_NAMES.items()},
                "log": list(self.log),
            }

    def signed_input(self, addr):
        value = self.inputs[addr]
        if addr in icd.SIGNED_INPUTS and value >= 0x8000:
            value -= 0x10000
        return value

    def response_policy(self, fc, resp):
        """예외 강제·CRC 깨기·지연을 적용한 응답과 지연 시간을 돌려줍니다"""
        inj = self.inject
        is_exception = inj["exc_n"] > 0 and inj["exc_code"] != 0
        if is_exception:
            inj["exc_n"] -= 1
            resp = mb.resp_exception(fc, inj["exc_code"])
            self.note("예외 %d 강제 (남은 %d 회)" % (inj["exc_code"], inj["exc_n"]))
        if inj["bad_crc_n"] > 0:
            inj["bad_crc_n"] -= 1
            resp = bytes(resp[:-1]) + bytes([resp[-1] ^ 0xFF])
            self.note("CRC 깨서 응답 (남은 %d 회)" % inj["bad_crc_n"])
        return resp, inj["resp_delay_ms"] / 1000.0

    def set_force(self, body):
        """본문 예: {"BUS24_V": 2350, "CHG_STATE": null}. 키는 이름이나 0xNN 주소이고, null 은 해제, 빈 본문은 전체 해제입니다"""
        with self.lock:
            if not body:
                self.force.clear()
                self.note("force 전체 해제")
            for key, value in body.items():
                addr = force_addr(key)
                if addr is None:
                    continue
                if value is None:
                    self.force.pop(addr, None)
                    self.note("force %s 해제" % icd.INPUT_NAMES.get(addr, hex(addr)))
                else:
                    self.force[addr] = u16(int(value))
                    self.note("force %s=%d" % (icd.INPUT_NAMES.get(addr, hex(addr)), self.force[addr]))
        return self.snapshot()

    def set_inject(self, body):
        with self.lock:
            for key, value in body.items():
                if key in self.inject:
                    self.inject[key] = type(kInjectDefaults[key])(value)
                    self.note("inject %s=%s" % (key, self.inject[key]))
        return self.snapshot()

    def drone_state(self):
        with self.lock:
            return dict(self.drone)

    def set_drone(self, body):
        """본문 예: {"location": "airborne"}, {"link": false}, {"stowed_report": false}. 위치를 바꾸면 착륙판 하중·수납 보고도 따라감"""
        with self.lock:
            if "link" in body:
                self.drone["link"] = bool(body["link"])
            if body.get("location") in kDroneLocations:
                is_docked = body["location"] == "docked"
                self.drone["location"] = body["location"]
                self.drone["stowed_report"] = is_docked
                self.inject["drone_detected"] = is_docked
            if "stowed_report" in body:
                self.drone["stowed_report"] = bool(body["stowed_report"])
            self.note("drone %s" % self.drone)
        return self.snapshot()

    def set_state(self, body):
        """본문 예: {"fault_code": 0, "SET_LIGHT": 3}. 내부 상태나 보유 레지스터를 그 값으로 바꿉니다 (force 와 달리 시뮬 동작이 따라감)"""
        holding_addr = {name: a for a, name in icd.HOLDING_NAMES.items()}
        with self.lock:
            for key, value in body.items():
                if key in kSettable:
                    setattr(self, key, kSettable[key](value))
                    self.note("set %s=%s" % (key, getattr(self, key)))
                    continue
                if key in holding_addr:
                    self.note("set %s=%d" % (key, int(value) & 0xFFFF))
                    self.apply_holding({holding_addr[key]: int(value) & 0xFFFF})
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
            resp, delay = mcu.response_policy(frame[1], resp)
            is_muted = mcu.inject["mute"]
        if is_muted:
            continue
        if delay > 0:
            time.sleep(delay)
        os.write(fd, resp)


# 3D 화면의 드론 형상
def drone_model(handler, query):
    with open(kDroneModelFile, "rb") as f:
        handler.send(200, f.read(), "model/gltf-binary")


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
        ("POST", "/api/force"): mcu.set_force,
        ("POST", "/api/set"): mcu.set_state,
        ("GET", "/api/drone"): lambda body: mcu.drone_state(),
        ("POST", "/api/drone"): mcu.set_drone,
        ("GET", "/api/icd"): lambda body: icd.describe(),
    }, html_path=kGuiFile, streams={"/api/cam.mjpg": camstream.mjpeg, "/api/drone.glb": drone_model}, asset_dir=kAssetDir)
    print("mcu_sim: %s, http :%d" % (port, kHttpPort), flush=True)
    next_at = time.monotonic()
    while True:
        next_at += kTickSec
        time.sleep(max(0.0, next_at - time.monotonic()))
        with mcu.lock:
            mcu.tick()


if __name__ == "__main__":
    main()
