"""ICD-XS-DM-MCU v0.1 레지스터 주소·코드 정의"""

SLAVE_ADDR = 1

# 보유 레지스터 (DM → MCU)
HB_SEQ = 0x0000
EPOCH_HI = 0x0001
EPOCH_LO = 0x0002
CMD_SEQ = 0x0010
CMD_CODE = 0x0011
CMD_ARG0 = 0x0012
CMD_ARG1 = 0x0013
SET_CLIMATE_MODE = 0x0020
SET_LIGHT = 0x0021
SET_ALARM_OUT = 0x0022
SET_LED_PATTERN = 0x0023
SET_CHG_CURRENT_LIMIT = 0x0024
CFG_COVER_TIMEOUT = 0x0030
CFG_SLIDE_TIMEOUT = 0x0031
CFG_CONTACT_TEMP_MAX = 0x0032
CFG_HB_TIMEOUT = 0x0033

HOLDING_NAMES = {
    HB_SEQ: "HB_SEQ",
    EPOCH_HI: "EPOCH_HI",
    EPOCH_LO: "EPOCH_LO",
    CMD_SEQ: "CMD_SEQ",
    CMD_CODE: "CMD_CODE",
    CMD_ARG0: "CMD_ARG0",
    CMD_ARG1: "CMD_ARG1",
    SET_CLIMATE_MODE: "SET_CLIMATE_MODE",
    SET_LIGHT: "SET_LIGHT",
    SET_ALARM_OUT: "SET_ALARM_OUT",
    SET_LED_PATTERN: "SET_LED_PATTERN",
    SET_CHG_CURRENT_LIMIT: "SET_CHG_CURRENT_LIMIT_10mA",
    CFG_COVER_TIMEOUT: "CFG_COVER_TIMEOUT_100ms",
    CFG_SLIDE_TIMEOUT: "CFG_SLIDE_TIMEOUT_100ms",
    CFG_CONTACT_TEMP_MAX: "CFG_CONTACT_TEMP_MAX_x10",
    CFG_HB_TIMEOUT: "CFG_HB_TIMEOUT_100ms",
}

HOLDING_DEFAULTS = {
    CFG_COVER_TIMEOUT: 300,
    CFG_SLIDE_TIMEOUT: 300,
    CFG_CONTACT_TEMP_MAX: 600,
    CFG_HB_TIMEOUT: 30,
}

# 입력 레지스터 (MCU → DM)
ACK_SEQ = 0x0000
ACK_RESULT = 0x0001
ACK_REASON = 0x0002
DONE_SEQ = 0x0003
DONE_RESULT = 0x0004
DONE_DATA = 0x0005
ACTIVE_SEQ = 0x0006
PROGRESS_PCT = 0x0007
MCU_STATUS = 0x0010
HARD_BLOCK = 0x0011
FAULT_CODE = 0x0012
MCU_TICK = 0x0013
FW_VER_MAJ_MIN = 0x0014
FW_VER_PATCH = 0x0015
UPTIME_HI = 0x0016
UPTIME_LO = 0x0017
COVER_STATE = 0x0020
COVER_LIMITS = 0x0021
COVER_CURRENT = 0x0022
SLIDE_STATE = 0x0023
SLIDE_LIMITS = 0x0024
SLIDE_CURRENT = 0x0025
SLIDE_ENCODER = 0x0026
CHG_STATE = 0x0030
CHG_OUTPUT_ON = 0x0031
CHG_VOLTAGE = 0x0032
CHG_CURRENT = 0x0033
CHG_CURRENT_LIMIT = 0x0034
CONTACT_TEMP = 0x0035
CHG_FAULT_CODE = 0x0036
TEMP_IN = 0x0040
HUM_IN = 0x0041
FLOOD = 0x0042
ENV_STALE = 0x0043
PWR_FLAGS = 0x0050
UPS_VOLTAGE = 0x0051
UPS_SOC = 0x0052
BUS24_V = 0x0053
BUS24_A = 0x0054
BUS48_V = 0x0055
BUS48_A = 0x0056
CLIMATE_MODE = 0x0060
CLIMATE_OUT = 0x0061
LIGHT_STATE = 0x0062
ALARM_OUT_STATE = 0x0063
LED_PATTERN = 0x0064
BMS_LINK = 0x0080
BMS_AGE = 0x0081
BMS_BATTERY_STATUS = 0x0082
BMS_VOLTAGE = 0x0083
BMS_CURRENT_HI = 0x0084
BMS_CURRENT_LO = 0x0085
BMS_RSOC = 0x0086
BMS_REMAIN = 0x0087
BMS_TEMP = 0x0088
BMS_CELL1 = 0x0089
BMS_CYCLE_COUNT = 0x008F
BMS_FAULT_FLAGS_HI = 0x0090
BMS_FAULT_FLAGS_LO = 0x0091
BMS_PWR_STATE = 0x0092
BMS_CHG_FET = 0x0093
BMS_DSG_FET = 0x0094
BMS_CHARGING_CURRENT = 0x0095
BMS_CHARGING_VOLTAGE = 0x0096
BMS_SNAPSHOT_AGE = 0x0097
BMS_TEMP_SHUNT = 0x0098
BMS_TEMP_CELL = 0x0099
BMS_TEMP_FET = 0x009A
BMS_TEMP_INT = 0x009B
BMS_PF_STATUS_HI = 0x009C
BMS_PF_STATUS_LO = 0x009D
BMS_SAFETY_STATUS_HI = 0x009E
BMS_SAFETY_STATUS_LO = 0x009F
BMS_AVG_TIME_TO_FULL = 0x00A0
BMS_CELL_MAX = 0x00A1
BMS_CELL_MIN = 0x00A2
BMS_SERIAL_NUMBER = 0x00B0
BMS_MANUFACTURE_DATE = 0x00B1
BMS_DESIGN_CAPACITY = 0x00B2
BMS_DESIGN_VOLTAGE = 0x00B3
BMS_FULL_CHARGE_CAPACITY = 0x00B4
BMS_DEVICE_TYPE = 0x00B5
BMS_FW_VERSION = 0x00B6
BMS_HW_VERSION = 0x00B7
INPUT_COUNT = 0x00C0

INPUT_NAMES = {
    ACK_SEQ: "ACK_SEQ",
    ACK_RESULT: "ACK_RESULT",
    ACK_REASON: "ACK_REASON",
    DONE_SEQ: "DONE_SEQ",
    DONE_RESULT: "DONE_RESULT",
    DONE_DATA: "DONE_DATA",
    ACTIVE_SEQ: "ACTIVE_SEQ",
    PROGRESS_PCT: "PROGRESS_PCT",
    MCU_STATUS: "MCU_STATUS",
    HARD_BLOCK: "HARD_BLOCK",
    FAULT_CODE: "FAULT_CODE",
    MCU_TICK: "MCU_TICK",
    FW_VER_MAJ_MIN: "FW_VER_MAJ_MIN",
    FW_VER_PATCH: "FW_VER_PATCH",
    UPTIME_HI: "UPTIME_HI",
    UPTIME_LO: "UPTIME_LO",
    COVER_STATE: "COVER_STATE",
    COVER_LIMITS: "COVER_LIMITS",
    COVER_CURRENT: "COVER_CURRENT_mA",
    SLIDE_STATE: "SLIDE_STATE",
    SLIDE_LIMITS: "SLIDE_LIMITS",
    SLIDE_CURRENT: "SLIDE_CURRENT_mA",
    SLIDE_ENCODER: "SLIDE_ENCODER",
    CHG_STATE: "CHG_STATE",
    CHG_OUTPUT_ON: "CHG_OUTPUT_ON",
    CHG_VOLTAGE: "CHG_VOLTAGE_10mV",
    CHG_CURRENT: "CHG_CURRENT_10mA",
    CHG_CURRENT_LIMIT: "CHG_CURRENT_LIMIT_10mA",
    CONTACT_TEMP: "CONTACT_TEMP_x10",
    CHG_FAULT_CODE: "CHG_FAULT_CODE",
    TEMP_IN: "TEMP_IN_x10",
    HUM_IN: "HUM_IN_x10",
    FLOOD: "FLOOD",
    ENV_STALE: "ENV_STALE",
    PWR_FLAGS: "PWR_FLAGS",
    UPS_VOLTAGE: "UPS_VOLTAGE_10mV",
    UPS_SOC: "UPS_SOC_PCT",
    BUS24_V: "BUS24_10mV",
    BUS24_A: "BUS24_10mA",
    BUS48_V: "BUS48_10mV",
    BUS48_A: "BUS48_10mA",
    CLIMATE_MODE: "CLIMATE_MODE",
    CLIMATE_OUT: "CLIMATE_OUT",
    LIGHT_STATE: "LIGHT_STATE",
    ALARM_OUT_STATE: "ALARM_OUT_STATE",
    LED_PATTERN: "LED_PATTERN",
    BMS_LINK: "BMS_LINK",
    BMS_AGE: "BMS_AGE_100ms",
    BMS_BATTERY_STATUS: "BMS_BATTERY_STATUS",
    BMS_VOLTAGE: "BMS_VOLTAGE_mV",
    BMS_CURRENT_HI: "BMS_CURRENT_mA_HI",
    BMS_CURRENT_LO: "BMS_CURRENT_mA_LO",
    BMS_RSOC: "BMS_RSOC_PCT",
    BMS_REMAIN: "BMS_REMAIN_mAh",
    BMS_TEMP: "BMS_TEMP_0p1K",
    BMS_CELL1 + 0: "BMS_CELL1_mV",
    BMS_CELL1 + 1: "BMS_CELL2_mV",
    BMS_CELL1 + 2: "BMS_CELL3_mV",
    BMS_CELL1 + 3: "BMS_CELL4_mV",
    BMS_CELL1 + 4: "BMS_CELL5_mV",
    BMS_CELL1 + 5: "BMS_CELL6_mV",
    BMS_CYCLE_COUNT: "BMS_CYCLE_COUNT",
    BMS_FAULT_FLAGS_HI: "BMS_FAULT_FLAGS_HI",
    BMS_FAULT_FLAGS_LO: "BMS_FAULT_FLAGS_LO",
    BMS_PWR_STATE: "BMS_PWR_STATE",
    BMS_CHG_FET: "BMS_CHG_FET",
    BMS_DSG_FET: "BMS_DSG_FET",
    BMS_CHARGING_CURRENT: "BMS_CHARGING_CURRENT_mA",
    BMS_CHARGING_VOLTAGE: "BMS_CHARGING_VOLTAGE_mV",
    BMS_SNAPSHOT_AGE: "BMS_SNAPSHOT_AGE_ms",
    BMS_TEMP_SHUNT: "BMS_TEMP_SHUNT_x10",
    BMS_TEMP_CELL: "BMS_TEMP_CELL_x10",
    BMS_TEMP_FET: "BMS_TEMP_FET_x10",
    BMS_TEMP_INT: "BMS_TEMP_INT_x10",
    BMS_PF_STATUS_HI: "BMS_PF_STATUS_HI",
    BMS_PF_STATUS_LO: "BMS_PF_STATUS_LO",
    BMS_SAFETY_STATUS_HI: "BMS_SAFETY_STATUS_HI",
    BMS_SAFETY_STATUS_LO: "BMS_SAFETY_STATUS_LO",
    BMS_AVG_TIME_TO_FULL: "BMS_AVG_TIME_TO_FULL_min",
    BMS_CELL_MAX: "BMS_CELL_MAX_mV",
    BMS_CELL_MIN: "BMS_CELL_MIN_mV",
    BMS_SERIAL_NUMBER: "BMS_SERIAL_NUMBER",
    BMS_MANUFACTURE_DATE: "BMS_MANUFACTURE_DATE",
    BMS_DESIGN_CAPACITY: "BMS_DESIGN_CAPACITY_mAh",
    BMS_DESIGN_VOLTAGE: "BMS_DESIGN_VOLTAGE_mV",
    BMS_FULL_CHARGE_CAPACITY: "BMS_FULL_CHARGE_CAPACITY_mAh",
    BMS_DEVICE_TYPE: "BMS_DEVICE_TYPE",
    BMS_FW_VERSION: "BMS_FW_VERSION",
    BMS_HW_VERSION: "BMS_HW_VERSION",
}

SIGNED_INPUTS = (SLIDE_ENCODER, CONTACT_TEMP, TEMP_IN, BMS_TEMP_SHUNT, BMS_TEMP_CELL, BMS_TEMP_FET, BMS_TEMP_INT)

# 폴링 블록 (시작, 워드 수)
STATUS_BLOCK = (0x0000, 112)
BMS_BLOCK = (0x0080, 48)
BMS_IDENT_BLOCK = (0x00B0, 16)

# 명령 코드
COVER_OPEN = 0x0001
COVER_CLOSE = 0x0002
SLIDE_EXTEND = 0x0003
SLIDE_RETRACT = 0x0004
CHARGE_ON = 0x0005
CHARGE_OFF = 0x0006
BMS_POWER_ON = 0x0007
BMS_POWER_OFF = 0x0008
MOTION_STOP = 0x0009
CLEAR_HOLD = 0x000A
CLEAR_FAULT = 0x000B
BMS_READ_WORD = 0x000C
BMS_WRITE_WORD = 0x000D
MCU_RESET = 0x000E
STATION_POWER_CYCLE = 0x000F

CMD_NAMES = {
    COVER_OPEN: "COVER_OPEN",
    COVER_CLOSE: "COVER_CLOSE",
    SLIDE_EXTEND: "SLIDE_EXTEND",
    SLIDE_RETRACT: "SLIDE_RETRACT",
    CHARGE_ON: "CHARGE_ON",
    CHARGE_OFF: "CHARGE_OFF",
    BMS_POWER_ON: "BMS_POWER_ON",
    BMS_POWER_OFF: "BMS_POWER_OFF",
    MOTION_STOP: "MOTION_STOP",
    CLEAR_HOLD: "CLEAR_HOLD",
    CLEAR_FAULT: "CLEAR_FAULT",
    BMS_READ_WORD: "BMS_READ_WORD",
    BMS_WRITE_WORD: "BMS_WRITE_WORD",
    MCU_RESET: "MCU_RESET",
    STATION_POWER_CYCLE: "STATION_POWER_CYCLE",
}

MOTION_CMDS = (COVER_OPEN, COVER_CLOSE, SLIDE_EXTEND, SLIDE_RETRACT)
BMS_CMDS = (BMS_POWER_ON, BMS_POWER_OFF, BMS_READ_WORD, BMS_WRITE_WORD)
CMD_HI_REJECT = {
    COVER_OPEN: (4, 6),
    COVER_CLOSE: (1, 4, 6),
    SLIDE_EXTEND: (2, 3, 4, 6),
    SLIDE_RETRACT: (4, 6),
    CHARGE_ON: (5, 6),
}
BMS_WRITE_ALLOWED = (0x00, 0x01, 0x02, 0x03, 0x04, 0x80)
MCU_RESET_MAGIC = 0x5A5A
POWER_CYCLE_MAGIC = 0xA5A5
POWER_CYCLE_DEFAULT_DELAY_S = 10

# 거부·폴트 코드
OK = 0x0000
HI1 = 0x0001
HI2 = 0x0002
HI3 = 0x0003
HI4 = 0x0004
HI5 = 0x0005
HI6 = 0x0006
BUSY = 0x0010
SAFE_HOLD = 0x0011
FAULT_LATCHED = 0x0012
BMS_NO_LINK = 0x0013
BMS_REJECT = 0x0014
CONTACT_OVERTEMP = 0x0015
BAD_ARG = 0x0016
UNKNOWN_CMD = 0x0017
NO_AC = 0x0018
MOTION_TIMEOUT = 0x0020
LIMIT_CONFLICT = 0x0021

REASON_NAMES = {
    OK: "OK",
    HI1: "HI-1",
    HI2: "HI-2",
    HI3: "HI-3",
    HI4: "HI-4",
    HI5: "HI-5",
    HI6: "HI-6",
    BUSY: "BUSY",
    SAFE_HOLD: "SAFE_HOLD",
    FAULT_LATCHED: "FAULT_LATCHED",
    BMS_NO_LINK: "BMS_NO_LINK",
    BMS_REJECT: "BMS_REJECT",
    CONTACT_OVERTEMP: "CONTACT_OVERTEMP",
    BAD_ARG: "BAD_ARG",
    UNKNOWN_CMD: "UNKNOWN_CMD",
    NO_AC: "NO_AC",
    MOTION_TIMEOUT: "MOTION_TIMEOUT",
    LIMIT_CONFLICT: "LIMIT_CONFLICT",
}

# 상태 값 이름
DONE_RESULT_NAMES = {0: "OK", 1: "TIMEOUT", 2: "ABORTED", 3: "HW_ERROR", 4: "INTERLOCK"}
COVER_STATE_NAMES = {0: "closed", 1: "opening", 2: "open", 3: "closing", 4: "unknown"}
SLIDE_STATE_NAMES = {0: "retracted", 1: "extending", 2: "extended", 3: "retracting", 4: "unknown"}
CHG_STATE_NAMES = {0: "off", 1: "on", 2: "fault"}
CHG_FAULT_NAMES = {0: "none", 1: "contact_overtemp", 2: "overcurrent", 3: "no_current", 4: "bms_reject"}
LED_PATTERN_NAMES = {
    0: "OFF", 1: "대기", 2: "모션 중", 3: "개방 대기", 4: "드론 비행 중",
    5: "SAFE-HOLD", 6: "FAULT", 7: "정비 모드", 8: "충전 중", 9: "업데이트 중",
}
MCU_STATUS_BITS = ("estop", "safe_hold", "fault", "hb_timeout", "sd_ok", "bms_link", "drone_detected", "motion_active")
HARD_BLOCK_BITS = ("HI-1", "HI-2", "HI-3", "HI-4", "HI-5", "HI-6")
COVER_LIMIT_BITS = ("front_closed", "front_open", "side_closed", "side_open", "front_door", "side_door")
SLIDE_LIMIT_BITS = ("home", "extended")
CLIMATE_OUT_BITS = ("heater", "cooler", "fan")
LIGHT_BITS = ("inner", "outer")
ALARM_BITS = ("buzzer", "indicator")
PWR_FLAG_BITS = ("ac_ok", "ups_on_battery", "ups_charging")
ENV_STALE_BITS = ("temp_hum", "flood")

# ICD 설명 (툴팁용)
HOLDING_DESC = {
    HB_SEQ: "DM 하트비트 카운터. 1 Hz 로 0x06 쓰기",
    EPOCH_HI: "Unix time(초) 상위. 선택",
    EPOCH_LO: "Unix time(초) 하위",
    CMD_SEQ: "명령 시퀀스 1~65535. 직전 값과 같으면 새 명령으로 보지 않음",
    CMD_CODE: "명령 코드 (4.3)",
    CMD_ARG0: "인자 0",
    CMD_ARG1: "인자 1",
    SET_CLIMATE_MODE: "0 off, 1 auto. 되읽기 0x0060",
    SET_LIGHT: "bit0 내부, bit1 외부. 되읽기 0x0062",
    SET_ALARM_OUT: "bit0 부저, bit1 LED 인디케이터. 되읽기 0x0063",
    SET_LED_PATTERN: "패턴 코드 (4.5). 되읽기 0x0064",
    SET_CHG_CURRENT_LIMIT: "충전 전류 상한 10 mA. 0 = 충전기 기본값 [확인]",
    CFG_COVER_TIMEOUT: "커버 모션 제한 시간 100 ms. 기본 300",
    CFG_SLIDE_TIMEOUT: "슬라이드 모션 제한 시간 100 ms. 기본 300",
    CFG_CONTACT_TEMP_MAX: "접점 온도 상한 ℃×10 (I16). 초과 시 MCU 가 충전 OFF",
    CFG_HB_TIMEOUT: "하트비트 타임아웃 100 ms. 기본 30, 최소 10",
}

INPUT_DESC = {
    ACK_SEQ: "접수/거부 판정한 CMD_SEQ",
    ACK_RESULT: "0 접수, 1 거부",
    ACK_REASON: "거부 사유 (4.4)",
    DONE_SEQ: "완료된 CMD_SEQ",
    DONE_RESULT: "0 성공, 1 시간 초과, 2 중단, 3 하드웨어 오류, 4 실행 중 인터락 발동",
    DONE_DATA: "모션: 소요 시간(100ms). BMS 쓰기: ERROR_CODE. BMS 읽기: 읽은 값",
    ACTIVE_SEQ: "실행 중 CMD_SEQ. 0 = 유휴",
    PROGRESS_PCT: "진행률 0~100",
    MCU_STATUS: "bit0 estop, bit1 safe_hold, bit2 fault, bit3 hb_timeout, bit4 sd_ok, bit5 bms_link, bit6 drone_detected, bit7 motion_active",
    HARD_BLOCK: "현재 성립 중인 하드 인터락. bit0 HI-1 … bit5 HI-6",
    FAULT_CODE: "래치된 폴트 원인 (4.4)",
    MCU_TICK: "100 ms 카운터",
    FW_VER_MAJ_MIN: "(MAJOR<<8) | MINOR",
    FW_VER_PATCH: "펌웨어 패치 버전",
    UPTIME_HI: "가동 시간(초) 상위",
    UPTIME_LO: "가동 시간(초) 하위",
    COVER_STATE: "0 closed, 1 opening, 2 open, 3 closing, 4 unknown",
    COVER_LIMITS: "bit0 정면 닫힘, bit1 정면 열림, bit2 측면 닫힘, bit3 측면 열림, bit4 정면 도어센서, bit5 측면 도어센서 [확인]",
    COVER_CURRENT: "커버 액추에이터 전류 mA",
    SLIDE_STATE: "0 retracted, 1 extending, 2 extended, 3 retracting, 4 unknown",
    SLIDE_LIMITS: "bit0 홈, bit1 전개",
    SLIDE_CURRENT: "슬라이드 모터 전류 mA",
    SLIDE_ENCODER: "슬라이드 엔코더 (I16). 미장착 시 0x8000",
    CHG_STATE: "0 off, 1 on, 2 fault",
    CHG_OUTPUT_ON: "충전 출력 0 / 1",
    CHG_VOLTAGE: "충전기 출력 전압 10 mV",
    CHG_CURRENT: "충전기 출력 전류 10 mA",
    CHG_CURRENT_LIMIT: "적용 중 전류 상한 10 mA",
    CONTACT_TEMP: "접점 온도 ℃×10 (I16)",
    CHG_FAULT_CODE: "0 없음, 1 접점 과온, 2 과전류, 3 통전 없음, 4 BMS 거부",
    TEMP_IN: "내부 온도 ℃×10 (I16)",
    HUM_IN: "내부 습도 %×10",
    FLOOD: "침수 0 / 1",
    ENV_STALE: "센서 갱신 실패. bit0 내부 온습도, bit1 침수",
    PWR_FLAGS: "bit0 ac_ok, bit1 ups_on_battery, bit2 ups_charging",
    UPS_VOLTAGE: "UPS 전압 10 mV",
    UPS_SOC: "UPS 잔량 %",
    BUS24_V: "24V 버스 전압 10 mV",
    BUS24_A: "24V 버스 전류 10 mA",
    BUS48_V: "48V 버스 전압 10 mV",
    BUS48_A: "48V 버스 전류 10 mA",
    CLIMATE_MODE: "공조 모드 되읽기. 0 off, 1 auto",
    CLIMATE_OUT: "공조 출력. bit0 heater, bit1 cooler, bit2 fan",
    LIGHT_STATE: "조명 되읽기. bit0 내부, bit1 외부",
    ALARM_OUT_STATE: "알람 출력 되읽기. bit0 부저, bit1 인디케이터",
    LED_PATTERN: "LED 패턴 되읽기 (4.5)",
    BMS_LINK: "0 무응답, 1 정상",
    BMS_AGE: "마지막 성공 읽기 후 경과 100 ms",
    BMS_BATTERY_STATUS: "Battery Status bitfield",
    BMS_VOLTAGE: "팩 전압 mV",
    BMS_CURRENT_HI: "팩 전류 I32 mA 상위 (양수 충전, 음수 방전)",
    BMS_CURRENT_LO: "팩 전류 I32 mA 하위",
    BMS_RSOC: "잔량 %",
    BMS_REMAIN: "잔여 용량 mAh",
    BMS_TEMP: "온도 0.1 K",
    BMS_CELL1 + 0: "셀 1 전압 mV",
    BMS_CELL1 + 1: "셀 2 전압 mV",
    BMS_CELL1 + 2: "셀 3 전압 mV",
    BMS_CELL1 + 3: "셀 4 전압 mV",
    BMS_CELL1 + 4: "셀 5 전압 mV",
    BMS_CELL1 + 5: "셀 6 전압 mV",
    BMS_CYCLE_COUNT: "사이클 수",
    BMS_FAULT_FLAGS_HI: "Fault Flags U32 bitfield 상위",
    BMS_FAULT_FLAGS_LO: "Fault Flags U32 bitfield 하위",
    BMS_PWR_STATE: "BMS 전원 상태 0 OFF, 1 ON",
    BMS_CHG_FET: "충전 FET 0 열림, 1 닫힘, 0xFF 불명",
    BMS_DSG_FET: "방전 FET 0 열림, 1 닫힘, 0xFF 불명",
    BMS_CHARGING_CURRENT: "요구 충전 전류 mA",
    BMS_CHARGING_VOLTAGE: "요구 충전 전압 mV",
    BMS_SNAPSHOT_AGE: "Snapshot Age ms",
    BMS_TEMP_SHUNT: "션트 온도 ℃×10 (I16)",
    BMS_TEMP_CELL: "셀 온도 ℃×10 (I16)",
    BMS_TEMP_FET: "FET 온도 ℃×10 (I16)",
    BMS_TEMP_INT: "내부 온도 ℃×10 (I16)",
    BMS_PF_STATUS_HI: "PF Status U32 bitfield 상위",
    BMS_PF_STATUS_LO: "PF Status U32 bitfield 하위",
    BMS_SAFETY_STATUS_HI: "Safety Status U32 bitfield 상위",
    BMS_SAFETY_STATUS_LO: "Safety Status U32 bitfield 하위",
    BMS_AVG_TIME_TO_FULL: "만충까지 예상 시간 min",
    BMS_CELL_MAX: "셀 최대 전압 mV",
    BMS_CELL_MIN: "셀 최소 전압 mV",
    BMS_SERIAL_NUMBER: "시리얼 (링크 성립 시 1회 갱신)",
    BMS_MANUFACTURE_DATE: "제조일 (SBS 형식, 링크 성립 시 1회)",
    BMS_DESIGN_CAPACITY: "설계 용량 mAh",
    BMS_DESIGN_VOLTAGE: "설계 전압 mV",
    BMS_FULL_CHARGE_CAPACITY: "만충 용량 mAh",
    BMS_DEVICE_TYPE: "장치 종류",
    BMS_FW_VERSION: "BMS 펌웨어 버전",
    BMS_HW_VERSION: "BMS 하드웨어 버전",
}

CMD_DESC = {
    COVER_OPEN: "ARG0 도어 마스크(0 전체, bit0 정면, bit1 측면). 완료: 열림 리미트 검출. 거부: HI-4, HI-6",
    COVER_CLOSE: "ARG0 도어 마스크. 완료: 닫힘 리미트 검출. 거부: HI-1, HI-4, HI-6",
    SLIDE_EXTEND: "완료: 전개 리미트 검출. 거부: HI-2, HI-3, HI-4, HI-6",
    SLIDE_RETRACT: "완료: 홈 리미트 검출. 거부: HI-4, HI-6",
    CHARGE_ON: "ARG0 전류 상한 10mA (0 = 0x0024 값). 완료: SSR ON + 통전 확인. 거부: HI-5, HI-6, CONTACT_OVERTEMP, NO_AC",
    CHARGE_OFF: "완료: SSR OFF 확인. 거부 없음",
    BMS_POWER_ON: "PWR_CTRL ← 0x01, ERROR_CODE = OK. 거부: BMS_NO_LINK",
    BMS_POWER_OFF: "PWR_CTRL ← 0x00, ERROR_CODE = OK. 거부: BMS_NO_LINK",
    MOTION_STOP: "모든 액추에이터 즉시 정지, SAFE-HOLD 진입. 항상 접수 (BUSY 무시)",
    CLEAR_HOLD: "SAFE-HOLD 해제. 거부: E-Stop 활성",
    CLEAR_FAULT: "래치된 FAULT 해제. 거부: E-Stop 활성, 원인 미해소",
    BMS_READ_WORD: "ARG0 BMS 레지스터 주소. 읽은 값 → DONE_DATA. 거부: BMS_NO_LINK",
    BMS_WRITE_WORD: "ARG0 주소(허용 0x00~0x04, 0x80), ARG1 값. ERROR_CODE → DONE_DATA. 거부: BMS_NO_LINK, BAD_ARG",
    MCU_RESET: "ARG0 0x5A5A. 응답 후 소프트 리셋. 거부: BAD_ARG, BUSY",
    STATION_POWER_CYCLE: "ARG0 0xA5A5, ARG1 지연 초(기본 10). ACK 후 Orin 전원 차단 → 재인가 [확인]. 거부: BAD_ARG, BUSY, 충전 ON, 커버 열림",
}

REASON_DESC = {
    OK: "정상",
    HI1: "커버 폐쇄 금지: 슬라이드 홈 리미트 미검출",
    HI2: "슬라이드 전개 금지: 커버 열림 리미트 미검출",
    HI3: "슬라이드 전개 금지: 충전 통전 중",
    HI4: "모션 금지 (FAULT): 구동부 과전류 / 스톨",
    HI5: "충전 ON 금지: 슬라이드 홈 리미트 미검출",
    HI6: "모션 금지 (FAULT): E-Stop 활성",
    BUSY: "다른 모션 실행 중",
    SAFE_HOLD: "SAFE-HOLD 중",
    FAULT_LATCHED: "FAULT 래치 중",
    BMS_NO_LINK: "BMS 무응답",
    BMS_REJECT: "BMS ERROR_CODE ≠ OK",
    CONTACT_OVERTEMP: "접점 온도 > CFG_CONTACT_TEMP_MAX",
    BAD_ARG: "인자 범위 밖 / 매직 불일치",
    UNKNOWN_CMD: "정의되지 않은 명령 코드",
    NO_AC: "AC 없음",
    MOTION_TIMEOUT: "(FAULT_CODE) 모션 제한 시간 초과",
    LIMIT_CONFLICT: "(FAULT_CODE) 리미트 스위치 모순",
}
