"""临时软件断开USB八秒后恢复；不掉电、不改开机配置、不刷写分区。"""
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/mnt/UDISK/xinyu-arm-check')
UDC = Path('/sys/kernel/config/usb_gadget/g1/UDC')

if '--start' in sys.argv:
    log = open(str(ROOT / 'usb-disconnect-trial.log'), 'w')
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve())],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True)
    print('软件掉线检查进程：' + str(child.pid), flush=True)
else:
    binding = UDC.read_text().strip()
    if not binding:
        raise RuntimeError('USB当前没有绑定，停止试验')
    time.sleep(2)
    try:
        print('软件USB断开', time.monotonic(), flush=True)
        UDC.write_text('\n')
        time.sleep(8)
    finally:
        UDC.write_text(binding + '\n')
        print('软件USB已恢复', time.monotonic(), flush=True)
