"""脱离ADB会话运行一次已有录音的真实USB网络文件联调，不播放。"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
environment = dict(os.environ)
environment['XINYU_BRIDGE_TOKEN'] = (ROOT / 'bridge-token.txt').read_text().strip()
log = open(str(ROOT / 'quiet-round2.log'), 'w')
command = [sys.executable, '-u', str(ROOT / 'board_client.py'),
           '--server', sys.argv[1], '--wav', str(ROOT / 'usb-mic-second.wav'),
           '--library', str(ROOT / 'libpcm_gate.so'), '--playback-target', 'board',
           '--records-dir', str(ROOT / 'records-rndis-quiet')]
process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
print('独立文件联调进程：' + str(process.pid), flush=True)
