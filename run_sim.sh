#!/bin/bash
# SM 마스터와 MCU 시뮬레이터를 띄웁니다 (화면: 마스터 http://localhost:8880, 시뮬레이터 :8881)
#
#   ./run_sim.sh                        가상 UART 쌍 위에 둘 다 (기본값)
#   ./run_sim.sh --port /dev/ttyUSB0    실물 포트에 SM 마스터만
#   ./run_sim.sh --port /dev/ttyUSB0 --slave   실물 포트에 MCU 시뮬만
#   ./run_sim.sh --list                 붙어 있는 시리얼 포트 목록
#
# 포트는 8N1 115200 고정.
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

if [ -n "$port" ] && [ ! -w "$port" ]; then
    echo "[!] $port 를 열 수 없다 — 가상 UART 로 돌아간다" >&2
    port=""
    is_slave_only=false
fi

trap 'kill $(jobs -p) 2>/dev/null' EXIT

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

wait -n
