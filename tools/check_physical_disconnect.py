"""只在用户实际拔线时计时；不操作键鼠、不模拟USB断开。"""
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
    output = ROOT / 'records/实时交互/物理拔线复核'
    output.mkdir(parents=True, exist_ok=True)
    adb = find_adb()
    with open(output / 'session.log', 'wb') as log:
        process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'supervise_bridge.py'),
            '--realtime', '--duration', '180'], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONIOENCODING='utf-8'),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 100
            while '连续采集已连接' not in (output / 'session.log').read_text(encoding='utf-8', errors='replace'):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('真实采集未准备好，不算物理拔线验收')
                time.sleep(0.2)
            print('真实采集已准备好：请拔下OTG数据线，暂不插回。', flush=True)
            deadline = time.monotonic() + 80
            while board_connected(adb, '20080411'):
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('未观察到物理断线，本次不计通过')
                time.sleep(0.05)
            observed = time.monotonic()
            process.wait(timeout=4)
            elapsed = time.monotonic() - observed
            result = {'守护退出码': process.returncode, '观察到ADB离线后退出秒数': elapsed,
                      '三秒内退出': elapsed < 3, '边界': '需用户确认实际拔OTG；键鼠全程未自动操作'}
            (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(result, ensure_ascii=False), flush=True)
        finally:
            stop_owned_process(process)


if __name__ == '__main__':
    main()
