"""临时保存内核和内存状态，最多运行30分钟，不修改驱动或电源设置。"""
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/mnt/UDISK/xinyu-arm-check/diagnostics')


def collect():
    ROOT.mkdir(exist_ok=True)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    output = open(str(ROOT / ('kernel-' + boot + '.log')), 'a')
    fd = os.open('/dev/kmsg', os.O_RDONLY | os.O_NONBLOCK)
    started = time.monotonic()
    next_status = 0
    try:
        while time.monotonic() - started < 1800:
            ready, unused, unused2 = select.select([fd], [], [], 1)
            changed = False
            if ready:
                while True:
                    try:
                        data = os.read(fd, 65536)
                    except BlockingIOError:
                        break
                    if not data:
                        break
                    output.write(data.decode('utf-8', errors='replace'))
                    changed = True
            if time.monotonic() >= next_status:
                state = {'uptime': Path('/proc/uptime').read_text().strip(),
                         'memory': Path('/proc/meminfo').read_text()}
                output.write('状态：' + json.dumps(state, ensure_ascii=False) + '\n')
                next_status = time.monotonic() + 5
                changed = True
            if changed:
                output.flush()
                os.fsync(output.fileno())
    finally:
        os.close(fd)
        output.close()


if __name__ == '__main__':
    if '--start' in sys.argv:
        ROOT.mkdir(exist_ok=True)
        log = open(str(ROOT / 'launcher.log'), 'a')
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve())],
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        print('临时诊断进程：' + str(process.pid), flush=True)
    else:
        collect()
