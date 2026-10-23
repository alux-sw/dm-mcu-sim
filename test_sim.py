"""시리얼 없이 Mcu 클래스에 프레임을 직접 넣어 명령·인터락·현장 버튼·하트비트를 점검합니다 (python3 test_sim.py)"""
import icd
import mcu_sim
import modbus_rtu as mb

kTicksCover = int(mcu_sim.kCoverMoveSec / mcu_sim.kTickSec) + 2
kTicksSlide = int(mcu_sim.kSlideMoveSec / mcu_sim.kTickSec) + 2
kTicksHb = int(mcu_sim.kHbTimeoutSec / mcu_sim.kTickSec) + 2


def cmd(mcu, seq, code, a0=0, a1=0):
    resp = mcu.handle(mb.req_write_multi(icd.CMD_SEQ, [seq, code, a0, a1]))
    assert resp[1] == mb.FC_WRITE_MULTI, resp.hex()
    mcu.tick()


def ticks(mcu, n):
    for _ in range(n):
        mcu.on_rx()
        mcu.tick()


def ack(mcu):
    return mcu.inputs[icd.ACK_SEQ], mcu.inputs[icd.ACK_RESULT], mcu.inputs[icd.ACK_REASON]


def done(mcu):
    return mcu.inputs[icd.DONE_SEQ], mcu.inputs[icd.DONE_RESULT]


# CRC 표준 벡터
assert mb.with_crc(bytes.fromhex("01030000000A")).hex() == "01030000000ac5cd"
assert mb.is_crc_ok(bytes.fromhex("01030000000ac5cd"))

mcu = mcu_sim.Mcu()
mcu.on_rx()

# 입력 블록 읽기 응답 길이, 범위 밖 주소
resp = mcu.handle(mb.req_read(mb.FC_READ_INPUT, *icd.STATUS_BLOCK))
assert len(resp) == 5 + 112 * 2 and mb.is_crc_ok(resp)
resp = mcu.handle(mb.req_read(mb.FC_READ_INPUT, 0x00C0, 1))
assert resp[1] == 0x84 and resp[2] == mb.EX_ILLEGAL_ADDR
resp = mcu.handle(mb.req_read(mb.FC_READ_HOLDING, 0x0030, 1))
assert resp[1] == 0x83 and resp[2] == mb.EX_ILLEGAL_ADDR

# 잘못된 설정값 → 0x03, 되읽기
resp = mcu.handle(mb.req_write_single(icd.SET_LED_PATTERN, 10))
assert resp[1] == 0x86 and resp[2] == mb.EX_ILLEGAL_VALUE
resp = mcu.handle(mb.req_write_single(icd.SET_LIGHT, 3))
assert resp[1] == mb.FC_WRITE_SINGLE and mcu.inputs[icd.LIGHT_STATE] == 3

# 정비 모드: SM 쓰기(원격) / 버튼(토글)
mcu.handle(mb.req_write_single(icd.SET_MAINT_MODE, 1))
mcu.tick()
assert (mcu.inputs[icd.MAINT_ACTIVE], mcu.inputs[icd.MAINT_SOURCE]) == (1, 1)
mcu.inject["btn_maint"] = True
ticks(mcu, 1)
assert (mcu.inputs[icd.MAINT_ACTIVE], mcu.inputs[icd.MAINT_SOURCE]) == (0, 0)
ticks(mcu, 6)
assert not mcu.inject["btn_maint"]

# 커버 열기 → 완료 (인자 없음)
cmd(mcu, 1, icd.COVER_OPEN)
assert ack(mcu) == (1, 0, icd.OK)
assert mcu.inputs[icd.COVER_STATE] == 1
ticks(mcu, kTicksCover)
assert done(mcu) == (1, 0)
assert mcu.inputs[icd.COVER_STATE] == 2 and mcu.inputs[icd.COVER_LIMITS] == 0b10 and mcu.inputs[icd.ACTIVE_SEQ] == 0

# 같은 seq 재전송은 무시
cmd(mcu, 1, icd.COVER_CLOSE)
assert ack(mcu) == (1, 0, icd.OK) and mcu.active is None

# 슬라이드 전개 → 완료, 그 상태에서 커버 닫기는 HI-1, 충전은 HI-5
cmd(mcu, 2, icd.SLIDE_EXTEND)
assert ack(mcu) == (2, 0, icd.OK)
ticks(mcu, kTicksSlide)
assert done(mcu) == (2, 0) and mcu.inputs[icd.SLIDE_STATE] == 2
cmd(mcu, 3, icd.COVER_CLOSE)
assert ack(mcu) == (3, 1, icd.HI1)
cmd(mcu, 4, icd.CHARGE_ON)
assert ack(mcu) == (4, 1, icd.HI5)

# 슬라이드 수납 → 드론 없이 충전 ON 은 통전 없음(HW_ERROR)
cmd(mcu, 5, icd.SLIDE_RETRACT)
ticks(mcu, kTicksSlide)
assert done(mcu) == (5, 0)
mcu.inject["drone_detected"] = False
cmd(mcu, 6, icd.CHARGE_ON)
assert ack(mcu) == (6, 0, icd.OK) and done(mcu) == (6, 3) and mcu.inputs[icd.CHG_STATE] == 2

# 드론 감지(하중 센서) 후 충전 ON → 충전 중 슬라이드 전개는 HI-3
mcu.inject["drone_detected"] = True
ticks(mcu, 1)
assert mcu.inputs[icd.SLIDE_LIMITS] & 0b100
cmd(mcu, 7, icd.CHARGE_ON, 300)
assert done(mcu) == (7, 0) and mcu.inputs[icd.CHG_STATE] == 1 and mcu.inputs[icd.CHG_CURRENT_LIMIT] == 300
cmd(mcu, 8, icd.SLIDE_EXTEND)
assert ack(mcu) == (8, 1, icd.HI3)
cmd(mcu, 9, icd.CHARGE_OFF)
assert done(mcu) == (9, 0) and mcu.inputs[icd.CHG_STATE] == 0

# 모션 중 E-Stop → FAULT(HI-6)+SAFE-HOLD, DONE INTERLOCK
cmd(mcu, 10, icd.COVER_CLOSE)
ticks(mcu, 5)
mcu.inject["estop"] = True
ticks(mcu, 1)
assert done(mcu) == (10, 4)
assert mcu.fault_code == icd.HI6 and mcu.safe_hold
assert mcu.inputs[icd.MCU_STATUS] & 0b111 == 0b111
cmd(mcu, 11, icd.CLEAR_FAULT)
assert ack(mcu) == (11, 1, icd.HI6)
mcu.inject["estop"] = False
ticks(mcu, 1)
cmd(mcu, 12, icd.COVER_OPEN)
assert ack(mcu) == (12, 1, icd.FAULT_LATCHED) and mcu.safe_hold
cmd(mcu, 13, icd.CLEAR_FAULT)
assert done(mcu) == (13, 0) and mcu.fault_code == 0 and not mcu.safe_hold

# MOTION_STOP → SAFE-HOLD 표시, 다음 정상 명령 접수로 자동 해제
cmd(mcu, 14, icd.COVER_CLOSE)
ticks(mcu, 3)
cmd(mcu, 15, icd.MOTION_STOP)
assert done(mcu) == (15, 0) and mcu.safe_hold and mcu.active is None
cmd(mcu, 16, icd.COVER_CLOSE)
assert ack(mcu) == (16, 0, icd.OK) and not mcu.safe_hold
ticks(mcu, kTicksCover)
assert done(mcu) == (16, 0) and mcu.inputs[icd.COVER_STATE] == 0

# 모션 제한 시간 초과 → DONE TIMEOUT + FAULT MOTION_TIMEOUT
mcu.inject["motion_timeout_sec"] = 1.0
cmd(mcu, 17, icd.COVER_OPEN)
ticks(mcu, 12)
assert done(mcu) == (17, 1) and mcu.fault_code == icd.MOTION_TIMEOUT
mcu.inject["motion_timeout_sec"] = mcu_sim.kMotionTimeoutSec
cmd(mcu, 18, icd.CLEAR_FAULT)
assert done(mcu) == (18, 0)

# 현장 버튼: ACK/DONE 없이 모션, LOCAL_BTN 비트, SM 모션 명령은 BUSY
mcu.inject["btn_door"] = True
ticks(mcu, 1)
assert mcu.inputs[icd.LOCAL_BTN] == 0b01 and mcu.active is not None and mcu.active["seq"] == 0
assert mcu.inputs[icd.ACTIVE_SEQ] == 0 and mcu.inputs[icd.MCU_STATUS] & (1 << 7)
cmd(mcu, 19, icd.SLIDE_EXTEND)
assert ack(mcu) == (19, 1, icd.BUSY)
ticks(mcu, kTicksCover)
assert mcu.active is None and mcu.inputs[icd.COVER_STATE] == 2 and done(mcu) == (18, 0)
assert mcu.inputs[icd.LOCAL_BTN] == 0
mcu.inject["btn_slide"] = True
ticks(mcu, kTicksSlide + 1)
assert mcu.inputs[icd.SLIDE_STATE] == 2
mcu.inject["btn_slide"] = True
ticks(mcu, kTicksSlide + 1)
assert mcu.inputs[icd.SLIDE_STATE] == 0

# 현장 우선: SM 모션 중 버튼 → SM 명령은 DONE ABORTED, 버튼 동작으로 넘어감
cmd(mcu, 190, icd.COVER_CLOSE)
ticks(mcu, 3)
mcu.inject["btn_door"] = True
ticks(mcu, 1)
assert done(mcu) == (190, 2) and mcu.active is not None and mcu.active["seq"] == 0
ticks(mcu, kTicksCover)
assert mcu.inputs[icd.COVER_STATE] == 2

# BMS 전원, 링크 끊김
cmd(mcu, 20, icd.BMS_POWER_OFF)
assert done(mcu) == (20, 0) and mcu.inputs[icd.BMS_PWR_STATE] == 0
mcu.inject["bms_link"] = False
ticks(mcu, 1)
cmd(mcu, 21, icd.BMS_POWER_ON)
assert ack(mcu) == (21, 1, icd.BMS_NO_LINK) and mcu.inputs[icd.BMS_LINK] == 0
mcu.inject["bms_link"] = True

# 매직 불일치·미정의 명령
cmd(mcu, 22, icd.STATION_POWER_CYCLE, 0x1234)
assert ack(mcu) == (22, 1, icd.BAD_ARG)
cmd(mcu, 23, 0x000E)
assert ack(mcu) == (23, 1, icd.UNKNOWN_CMD)

# 하트비트 3 초 미수신 → SAFE-HOLD
for _ in range(kTicksHb):
    mcu.tick()
assert mcu.hb_timeout and mcu.safe_hold
mcu.on_rx()
assert not mcu.hb_timeout

# 직접 설정: 내부 상태·보유 레지스터가 입력 레지스터로 이어진다. E-Stop 이 눌려 있으면 폴트는 다시 래치
mcu.inject["estop"] = True
ticks(mcu, 1)
mcu.set_state({"fault_code": 0, "safe_hold": 0})
ticks(mcu, 1)
assert mcu.fault_code == icd.HI6
mcu.inject["estop"] = False
mcu.set_state({"fault_code": 0, "safe_hold": 0, "SET_LIGHT": 3})
ticks(mcu, 1)
assert mcu.fault_code == 0 and not mcu.safe_hold and mcu.inputs[icd.FAULT_CODE] == 0
assert mcu.inputs[icd.LIGHT_STATE] == 3
mcu.set_state({"SET_LED_PATTERN": 2})
assert mcu.inputs[icd.LED_PATTERN] == 2

# DONE 을 받자마자 다음 명령: 커버 열림 DONE 틱의 HARD_BLOCK 은 이미 열림 기준 (HI-2 없음)
cmd(mcu, 30, icd.COVER_CLOSE)
ticks(mcu, kTicksCover)
cmd(mcu, 31, icd.COVER_OPEN)
for _ in range(kTicksCover):
    ticks(mcu, 1)
    if done(mcu) == (31, 0):
        break
assert done(mcu) == (31, 0)
mcu.handle(mb.req_write_multi(icd.CMD_SEQ, [32, icd.SLIDE_EXTEND, 0, 0]))
assert ack(mcu) == (32, 0, icd.OK)
ticks(mcu, kTicksSlide)
assert done(mcu) == (32, 0)

# 할 수 없는 현장 버튼(슬라이드 나와 있어 커버 닫기 HI-1)은 SM 명령을 끊지 않음
cmd(mcu, 33, icd.SLIDE_RETRACT)
ticks(mcu, 3)
mcu.inject["btn_door"] = True
ticks(mcu, 1)
assert mcu.active is not None and mcu.active["seq"] == 33
ticks(mcu, kTicksSlide)
assert done(mcu) == (33, 0)

# SM 명령과 같은 동작의 현장 버튼(커버 여는 중 문 버튼)은 무시, SM 명령은 OK
cmd(mcu, 34, icd.COVER_CLOSE)
ticks(mcu, kTicksCover)
cmd(mcu, 35, icd.COVER_OPEN)
ticks(mcu, 3)
mcu.inject["btn_door"] = True
ticks(mcu, 1)
assert mcu.active is not None and mcu.active["seq"] == 35
ticks(mcu, kTicksCover)
assert done(mcu) == (35, 0) and mcu.inputs[icd.COVER_STATE] == 2

# 드론 mock: 이륙하면 착륙판 하중·수납 보고가 꺼지고, 착륙하면 켜짐
mcu.set_drone({"location": "airborne"})
ticks(mcu, 1)
assert mcu.drone == {"link": True, "location": "airborne", "stowed_report": False}
assert not mcu.inputs[icd.SLIDE_LIMITS] & 0b100 and not mcu.inputs[icd.MCU_STATUS] & (1 << 6)
mcu.set_drone({"location": "docked"})
ticks(mcu, 1)
assert mcu.drone["stowed_report"] and mcu.inputs[icd.SLIDE_LIMITS] & 0b100
mcu.set_drone({"link": False, "stowed_report": False})
assert mcu.drone == {"link": False, "location": "docked", "stowed_report": False}


def bms32(m, addr_hi):
    return (m.inputs[addr_hi] << 16) | m.inputs[addr_hi + 1]


# BMS 부팅 직후 1 초는 ERROR_CODE 7, 그 뒤 INITIALIZED·DISCHARGING
bms = mcu_sim.Mcu()
ticks(bms, 1)
assert bms.inputs[icd.BMS_BATTERY_STATUS] == 0x7 and bms.inputs[icd.BMS_SNAPSHOT_AGE] == 0xFFFF
ticks(bms, int(mcu_sim.kBmsBootSec / mcu_sim.kTickSec) + 1)
assert bms.inputs[icd.BMS_BATTERY_STATUS] == 0x00C0

# 약한 셀 하나: 팩 전압·최소·최대가 따라감
bms.set_state({"bms_weak_cell": 3, "bms_weak_cell_mv": 3300})
ticks(bms, 1)
cell_mv = int(round(bms.bms_cells_mv[0]))
assert bms.inputs[icd.BMS_CELL1 + 2] == 3300 and bms.inputs[icd.BMS_CELL1] == cell_mv
assert (bms.inputs[icd.BMS_CELL_MIN], bms.inputs[icd.BMS_CELL_MAX]) == (3300, cell_mv)
assert bms.inputs[icd.BMS_VOLTAGE] == cell_mv * 7 + 3300
bms.set_state({"bms_weak_cell": 0})

# 전체 잔량 = 셀 잔량 평균. 전체를 바꾸면 셀이 같은 만큼 움직이고, 셀 하나를 바꾸면 전체가 다시 계산됨
bms.set_state({"bms_rsoc": 0})
assert bms.bms_cell_mv == mcu_sim.kBmsCellEmptyMv
bms.set_state({"bms_rsoc": 100})
assert bms.bms_cell_mv == mcu_sim.kBmsCellFullMv
bms.set_state({"bms_rsoc": 80})
bms.set_state({"bms_cell_pct": {"cell": 2, "pct": 40}})
ticks(bms, 1)
assert bms.bms_rsoc == 75.0 and bms.inputs[icd.BMS_RSOC] == 75
assert bms.inputs[icd.BMS_CELL1 + 1] == mcu_sim.cell_mv_of(40) and bms.inputs[icd.BMS_CELL1] == mcu_sim.cell_mv_of(80)
bms.set_state({"bms_rsoc": 50})   # 셀 사이 차이 유지
ticks(bms, 1)
assert bms.inputs[icd.BMS_CELL1] - bms.inputs[icd.BMS_CELL1 + 1] == mcu_sim.cell_mv_of(80) - mcu_sim.cell_mv_of(40)
assert bms.inputs[icd.BMS_RSOC] == 50 and bms.inputs[icd.BMS_REMAIN] == 4000
bms.set_state({"bms_cell_pct": {"cell": 2, "pct": 0}, "bms_rsoc": 10})   # 0 % 에 걸린 셀은 두고 나머지로 평균을 맞춤
assert abs(bms.bms_rsoc - 10) < 0.01 and bms.bms_cells_mv[1] == mcu_sim.kBmsCellEmptyMv
bms.set_state({"bms_cell_reset": True})
assert len(set(bms.bms_cells_mv)) == 1 and abs(bms.bms_rsoc - 10) < 0.01   # 고르게 해도 평균은 그대로
bms.set_state({"bms_cell_mv": 3900})
assert bms.bms_cells_mv == [3900.0] * 8 and abs(bms.bms_rsoc - 66.667) < 0.01
bms.set_state({"bms_rsoc": 10, "chg_on": 1})   # 충전하면 셀이 같이 오르고 평균 잔량도 오름
ticks(bms, 10)
assert bms.bms_rsoc > 10 and len(set(bms.bms_cells_mv)) == 1
bms.set_state({"bms_rsoc": 100})
ticks(bms, 2)
assert bms.inputs[icd.CHG_OUTPUT_ON] == 1 and bms.inputs[icd.CHG_CURRENT] == 0 and bms32(bms, icd.BMS_CURRENT_HI) == 0
assert bms.inputs[icd.BMS_FULL_CHARGE_CAPACITY] == 8000 and bms.inputs[icd.BMS_REMAIN] == 8000
bms.set_state({"chg_on": 0, "bms_rsoc": 80})

# PF_STATUS ≠ 0 → FAULT_FLAGS bit31, 알람 bit14·11, FET 둘 다 열림
bms.set_state({"bms_pf_status": 0x10, "bms_pf_alert": 0x20, "bms_safety_alert": 0x1, "bms_safety_status": 0x800})
ticks(bms, 1)
assert bms32(bms, icd.BMS_FAULT_FLAGS_HI) == 1 << 31 and bms32(bms, icd.BMS_PF_STATUS_HI) == 0x10
assert bms32(bms, icd.BMS_PF_ALERT_HI) == 0x20 and bms32(bms, icd.BMS_SAFETY_ALERT_HI) == 0x1
assert bms32(bms, icd.BMS_SAFETY_STATUS_HI) == 0x800
assert bms.inputs[icd.BMS_BATTERY_STATUS] & 0x4800 == 0x4800
assert (bms.inputs[icd.BMS_CHG_FET], bms.inputs[icd.BMS_DSG_FET]) == (0, 0)
bms.set_state({"bms_pf_status": 0, "bms_pf_alert": 0, "bms_safety_alert": 0, "bms_safety_status": 0})

# UV_CRITICAL: 방전만 차단, 충전 FET 는 닫힘. COMM: ERROR_CODE 7
bms.set_state({"bms_fault_flags": 1 << 8})
ticks(bms, 1)
assert (bms.inputs[icd.BMS_CHG_FET], bms.inputs[icd.BMS_DSG_FET]) == (1, 0)
assert bms.inputs[icd.BMS_BATTERY_STATUS] & (1 << 11)
bms.set_state({"bms_fault_flags": 1 << 6})
ticks(bms, 1)
assert bms.inputs[icd.BMS_BATTERY_STATUS] == 0x7
bms.set_state({"bms_fault_flags": 0, "bms_fet_unknown": 1})
ticks(bms, 1)
assert (bms.inputs[icd.BMS_CHG_FET], bms.inputs[icd.BMS_DSG_FET]) == (0xFF, 0xFF)
bms.set_state({"bms_fet_unknown": 0})

# 예상 시간: 방전 중 TO_EMPTY 만, 충전 중 TO_FULL 만 (속도 0 이면 모름)
bms.set_state({"bms_rsoc": 50, "bms_load_ma": 200})
ticks(bms, 1)
assert bms.inputs[icd.BMS_AVG_TIME_TO_FULL] == 0xFFFF and bms.inputs[icd.BMS_RUN_TIME_TO_EMPTY] == 1200
assert bms32(bms, icd.BMS_AVG_CURRENT_HI) == 0xFFFFFF38
bms.set_state({"bms_rsoc": 50, "chg_on": 1, "bms_charge_pct_per_s": 0.5})
ticks(bms, 1)
assert bms.inputs[icd.BMS_AVG_TIME_TO_FULL] == 2 and bms.inputs[icd.BMS_RUN_TIME_TO_EMPTY] == 0xFFFF
bms.set_state({"bms_charge_pct_per_s": 0})
ticks(bms, 1)
assert bms.inputs[icd.BMS_AVG_TIME_TO_FULL] == 0xFFFF
bms.set_state({"chg_on": 0, "bms_charge_pct_per_s": 0.5})

# 무부하 5 분이면 출력 자동 OFF, 충전기 전압이 보이면 자동 ON
bms.set_state({"bms_load_ma": 50})
ticks(bms, int(mcu_sim.kBmsIdleOffSec / mcu_sim.kTickSec) - 10)
assert bms.bms_pwr == 1
cmd(bms, 1, icd.BMS_POWER_ON)
ticks(bms, 20)
assert bms.bms_pwr == 1
ticks(bms, int(mcu_sim.kBmsIdleOffSec / mcu_sim.kTickSec))
assert bms.bms_pwr == 0 and bms.inputs[icd.BMS_PWR_STATE] == 0 and bms.inputs[icd.BMS_SNAPSHOT_AGE] == 2500
bms.set_state({"chg_on": 1})
ticks(bms, 1)
assert bms.bms_pwr == 1

print("test_sim: OK")
