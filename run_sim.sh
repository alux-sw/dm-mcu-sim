#!/bin/bash
# SM 마스터와 MCU 시뮬레이터를 띄운다 (GUI: http://localhost:8880)
#
#   ./run_sim.sh                        가상 UART 쌍 위에 둘 다 (기본)
#   ./run_sim.sh --port /dev/ttyUSB0    실물 포트에 SM 마스터만 — 상대는 벤더 MCU
#   ./run_sim.sh --port /dev/ttyUSB0 --slave   실물 포트에 MCU 시뮬만 — 상대는 벤더 DM
#   ./run_sim.sh --list                 붙어 있는 시리얼 포트 목록
#
# 포트는 USB 어댑터(/dev/ttyUSB*)나 USB CDC(/dev/ttyACM*)도 된다. 8N1 115200 고정.
cd "$(dirname "$0")"

kPortGlobs="/dev/ttyUSB* /dev/ttyACM*"

port=""
is_slave_only=false

while [ $# -gt 0 ]; do
    case "$1" in
        --port) port="$2"; shift 2 ;;
        --slave) is_slave_only=true; shift ;;
        --list)
            echo "시리얼 포트:"
            ls -l $kPortGlobs 2>/dev/null || echo "  (없음)"
            ls -l /dev/serial/by-id/ 2>/dev/null | tail -n +2
            exit 0 ;;
        -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
        *) echo "모르는 인자: $1" >&2; exit 1 ;;
    esac
done

# 포트가 없거나 못 열면 가상으로 — 화면이 죽어 손도 못 대는 상황을 막는다
if [ -n "$port" ] && [ ! -w "$port" ]; then
    echo "[!] $port 를 열 수 없다 — 가상 UART 로 돌아간다" >&2
    port=""
    is_slave_only=false
fi

trap 'kill $(jobs -p) 2>/dev/null' EXIT   # 우리가 띄운 자식만 — kill 0 은 부모 셸까지 죽인다

if [ -z "$port" ]; then
    if [ "$is_slave_only" = true ]; then
        echo "--slave 는 --port 와 함께 쓴다 (실물 포트에 MCU 시뮬만 붙이는 모드)" >&2
        exit 1
    fi
    python3 vserial.py > vserial.txt &
    sleep 0.5
    python3 mcu_sim.py "$(sed -n 2p vserial.txt)" &
    python3 sm_master.py "$(sed -n 1p vserial.txt)" &
elif [ "$is_slave_only" = true ]; then
    python3 mcu_sim.py "$port" &
else
    python3 sm_master.py "$port" &
fi

wait -n          # 하나만 죽어도 빠져나온다 (systemd 가 통째로 재시작)
