#!/bin/bash
# 가상 UART 위에 MCU 시뮬레이터와 SM 마스터를 함께 띄운다 (GUI: http://localhost:8880)
cd "$(dirname "$0")"
trap 'kill 0' EXIT
python3 vserial.py > vserial.txt &
sleep 0.5
SM_PORT=$(sed -n 1p vserial.txt)
MCU_PORT=$(sed -n 2p vserial.txt)
python3 mcu_sim.py "$MCU_PORT" &
python3 sm_master.py "$SM_PORT" &
wait
