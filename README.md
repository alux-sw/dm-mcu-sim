# dm-mcu-sim

ICD-XS-DM-MCU v0.1 (Dock Manager ↔ 스테이션 MCU, Modbus RTU) 프로토타입.

| 파일 | 역할 |
|---|---|
| `dm_master.py` | DM(SM) 쪽 Modbus 마스터. 상태 10 Hz·BMS 1/0.2 Hz·식별 1회·하트비트 1 Hz 폴링, 명령·설정 쓰기, HTTP :8880 |
| `mcu_sim.py` | MCU 쪽 Modbus 슬레이브 시뮬레이터. 레지스터 맵·명령 접수/거부·HI-1~6·SAFE-HOLD/FAULT·하트비트·BMS 미러, HTTP :8881 |
| `gui.html` | 디버그 GUI. 스테이션 애니메이션(커버·슬라이드·드론·충전·LED·조명·알람·공조·E-Stop·침수), 레지스터 표, 명령·설정·주입. 값에 마우스를 올리면 ICD 설명 툴팁. dm_master 가 `/` 로 내보냄 |
| `icd.py` | 레지스터 주소·명령·거부 코드 정의 |
| `modbus_rtu.py` | CRC16·프레임 조립/해석·시리얼(termios) |
| `webapi.py` | JSON HTTP 서버 |
| `vserial.py` | 가상 UART 쌍 (pty 2개 브리지) |
| `run_sim.sh` | 가상 UART 위에 둘 다 띄움 |
| `test_sim.py` | 시리얼 없이 명령·인터락·하트비트 점검 |

Python 3 표준 라이브러리만 사용 (Linux).

## 실행

가상 UART 로 한 대에서:

```
./run_sim.sh
```

브라우저에서 `http://<호스트>:8880`.

실제 UART:

```
python3 dm_master.py /dev/ttyTHS1      # Orin
python3 mcu_sim.py /dev/ttyUSB0        # MCU 대신 PC
```

점검:

```
python3 test_sim.py
```

## HTTP API

dm_master (:8880)

- `GET /api/state` — 입력 레지스터 전부(이름별)·해석값·링크 통계·명령 로그·프레임 로그·마지막 보유 레지스터 값(시작 시 0x03 으로 한 번 읽음)
- `GET /api/icd` — 레지스터·명령·거부 코드 설명 (툴팁용)
- `POST /api/cmd` `{"code":1,"arg0":0,"arg1":0}` — CMD_SEQ 자동 증가, 0x10 한 프레임으로 씀
- `POST /api/write` `{"addr":33,"value":3}` — 보유 레지스터 0x06 쓰기

mcu_sim (:8881)

- `GET /api/state` — 주입값·내부 상태(위치·충전·LED 등 애니메이션용)·로그
- `POST /api/inject` `{"estop":true,"contact_temp":65}` — estop / ac_ok / flood / drone_detected / bms_link / overcurrent(HI-4) / limit_conflict / mute(응답 끊기) / contact_temp / temp_in / hum_in / cover_sec·slide_sec(모션 소요 시간, GUI 상단에서 조절)

## 시뮬레이터 가정

- 커버 3 초, 슬라이드 4 초에 리미트 도달. 도어센서 비트 = 닫힘 리미트와 동일
- 충전 ON 은 드론 감지가 없으면 통전 없음(CHG_FAULT 3, DONE HW_ERROR)
- 충전기 기본 상한 10 A, 출력 50.4 V / 5 A
- CFG_CONTACT_TEMP_MAX 기본 60.0 ℃ (ICD 에 기본값 없음)
- 부팅 후 DM 프레임이 3 초 없으면 SAFE-HOLD (ICD 5 장)

## ICD 에서 드러난 빈 곳

- MOTION_STOP 이 모션을 중단하면 중단된 명령의 DONE(ABORTED) 과 MOTION_STOP 의 DONE 이 같은 슬롯에 연달아 써져 앞엣것이 덮인다
- STATION_POWER_CYCLE 거부 조건 "충전 ON", "커버 열림" 에 해당하는 ACK_REASON 코드가 없다 (시뮬레이터는 BUSY 로 응답)
- CLEAR_FAULT 거부 "원인 미해소" 의 ACK_REASON 코드가 없다 (시뮬레이터는 FAULT_CODE 값을 그대로 응답)
- CFG_CONTACT_TEMP_MAX 기본값 없음
