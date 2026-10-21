"""故事文件复核也受独立断板守护约束，不占用键鼠或播放音频。"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realtime_session import find_adb
from supervise_bridge import board_connected, supervise

adb = find_adb()
if not board_connected(adb, '20080411'):
    raise SystemExit('开发板未连接，不启动模型复核')
process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'tools/check_realtime_worker.py'),
                           '--task' if '--task' in sys.argv else '--story'],
    cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')
raise SystemExit(supervise(process, lambda: board_connected(adb, '20080411')))
