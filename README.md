# dm-mcu-sim

Station Manager ↔ 스테이션 MCU, Modbus RTU 프로토타입.

| 파일 | 역할 |
|---|---|
| `sm_master.py` | SM 쪽 Modbus 마스터. 상태 10 Hz·BMS 1/0.2 Hz·식별 1회·하트비트 1 Hz 폴링, 명령·설정 쓰기, 시작 시 보유 레지스터 0x03 동기화, HTTP :8880 |
| `mcu_sim.py` | MCU 쪽 Modbus 슬레이브 시뮬레이터. 레지스터 맵·명령 접수/거부·HI-1~6·SAFE-HOLD/FAULT·하트비트·현장 버튼·정비 모드·BMS 미러, HTTP :8881 |
| `gui.html` | 마스터 화면. 레지스터 표, 명령·설정, 요청 종류별 마지막 RX 바이트 표, 값에 마우스를 올리면 ICD 설명 툴팁이 표시됩니다. |
| `sim.html` | 시뮬레이터 화면. 스테이션 애니메이션 |
| `icd.py` | 레지스터 주소·명령·거부 코드·설명 |
| `modbus_rtu.py` | CRC16·프레임 조립/해석·시리얼(termios) |
| `webapi.py` | JSON HTTP 서버 |
| `vserial.py` | 가상 UART 쌍 (pty 2개 브리지) |
| `run_sim.sh` | 가상 UART 위에 둘 다 띄움 |
| `test_sim.py` | 시리얼 없이 명령·인터락·버튼·하트비트 점검 |

Python 3 표준 라이브러리만 사용 (Linux).

# 실행
SM(Station Master) <-> MCU 시뮬레이터 v1.0.0

## 한 PC에서 SM과 MCU 모두 시뮬레이션
### 실행:
bash run_sim.sh
- 마스터(SM) 화면: http://localhost:8880
- 슬레이브 및 시뮬레이터(MCU) 화면: http://localhost:8881

## 두 PC에서 각각 SM과 MCU를 시뮬레이션
### 마스터 실행:
bash run_sim.sh --port {시리얼포트}
ex) bash run_sim.sh --port /dev/ttyTHS1

접속: http://{마스터주소}:8880

### 슬레이브 실행:
bash run_sim.sh --port {시리얼포트} --slave
ex) bash run_sim.sh --port /dev/ttyUSB0 --slave

접속: http://{슬레이브주소}:8881