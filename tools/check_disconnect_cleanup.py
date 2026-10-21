"""真实会话+托管模型的软件USB掉线检查；不代替物理拔板。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realtime_session import find_adb
from supervise_bridge import board_connected, stop_owned_process


def main():
    output = ROOT / 'records/实时交互/外层守护掉线复核'
    output.mkdir(exist_ok=True)
    adb = find_adb()
    log = open(output / 'session.log', 'wb')
    process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'supervise_bridge.py'),
                               '--realtime', '--duration', '120'], cwd=str(ROOT), stdout=log,
                              stderr=subprocess.STDOUT, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    try:
        deadline = time.monotonic() + 100
        while '连续采集已连接' not in (output / 'session.log').read_text(encoding='utf-8', errors='replace'):
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('本次真实会话未准备好，未执行USB断开')
            time.sleep(0.2)
        subprocess.run([adb, 'push', str(ROOT / 'tools/usb_disconnect_trial.py'),
                        '/mnt/UDISK/xinyu-arm-check/tools/usb_disconnect_trial.py'], check=True, timeout=5)
        command = ('export PYTHONHOME=/mnt/UDISK/xinyu-runtime35/usr; '
                   'export LD_LIBRARY_PATH=/mnt/UDISK/xinyu-runtime35/usr/lib; '
                   '/mnt/UDISK/xinyu-runtime35/usr/bin/python3 '
                   '/mnt/UDISK/xinyu-arm-check/tools/usb_disconnect_trial.py --start')
        subprocess.run([adb, 'shell', command], check=True, timeout=5)
        deadline = time.monotonic() + 8
        while board_connected(adb, '20080411'):
            if time.monotonic() > deadline:
                raise RuntimeError('没有观察到USB断开，不能计为通过')
            time.sleep(0.02)
        observed = time.monotonic()
        process.wait(timeout=5)
        elapsed = time.monotonic() - observed
        time.sleep(max(0, 10 - elapsed))
        restored = board_connected(adb, '20080411')
        result = {'会话退出码': process.returncode, '检测到设备离线后退出秒数': elapsed,
                  'ADB自动恢复': restored, '退出时限通过': elapsed < 3,
                  '边界': '软件解除USB绑定后自动恢复；不是物理拔板'}
        (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if not result['退出时限通过'] or not restored:
            raise RuntimeError('掉线或恢复验收未通过')
    finally:
        stop_owned_process(process)
        log.close()


if __name__ == '__main__':
    main()
