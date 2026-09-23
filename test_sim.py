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

print("test_sim: OK")
