#!/bin/sh
# 板端跑一轮：ALSA 录 5 秒 → ARM 汇编门控（libpcm_gate.so）→ RNDIS 上传电脑桥接
# 用法（电脑端通过 adb 执行）：XINYU_BRIDGE_TOKEN=<令牌> sh /tmp/board_round.sh
# 前提：板端 USB 麦克风在 card 2（plughw:2,0），电脑桥接监听 192.168.113.1:8765

RUNTIME=/mnt/UDISK/xinyu-runtime35
WORK=/mnt/UDISK/xinyu-arm-check
export LD_LIBRARY_PATH=$RUNTIME/usr/lib
export PYTHONHOME=$RUNTIME/usr
cd "$WORK" || exit 9

printf '\n' | "$RUNTIME/usr/bin/python3" board_client.py \
  --server http://192.168.113.1:8765 \
  --capture-device plughw:2,0 \
  --library "$WORK/libpcm_gate.so" \
  --records-dir "$WORK/records"
echo "EXIT=$?"
