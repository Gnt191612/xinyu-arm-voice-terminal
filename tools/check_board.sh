#!/bin/sh
# 缺少Python时仍能给出提示；不安装软件、不更改板端配置。
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' '固件没有python3。请在T113匹配的Tina SDK中启用Python3及ctypes/libffi、ALSA工具。'
    printf '%s\n' '不能直接复制电脑的Python或其他板子的动态库。'
    uname -m
    cat /proc/asound/cards 2>/dev/null
    command -v arecord >/dev/null 2>&1 && arecord -l
    printf '%s\n' '当前电脑外放方案不要求板端aplay或播放声卡。'
    exit 1
fi
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
exec python3 "$script_dir/check_board.py" "$@"
