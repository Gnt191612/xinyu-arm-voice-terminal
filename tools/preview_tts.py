"""生成本机音色对比，不自动外放；整个生成过程受断板守护。"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realtime_session import find_adb
from supervise_bridge import board_connected, supervise
from tts_audio import normalize_tts_wave


def render():
    output = ROOT / 'records/音色试听'
    output.mkdir(parents=True, exist_ok=True)
    text = '我在这里，慢慢说就好。今天有点累，也不用急着整理好心情。我们先聊一会儿，再一起想想明天怎么安排，好吗？'
    variants = [('A_原版慧慧', 'Microsoft Huihui Desktop', 0, False),
                ('B_舒缓慧慧', 'Microsoft Huihui Desktop', -1, True),
                ('C_舒缓瑶瑶', 'Microsoft Yaoyao', -1, True)]
    results = []
    for name, voice, rate, prosody in variants:
        request = output / (name + '.json')
        request.write_text(json.dumps(dict(text=text, voice=voice, rate=rate, prosody=prosody),
                                      ensure_ascii=False), encoding='utf-8')
        target = output / (name + '.wav')
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(ROOT / 'tts.ps1'), '-RequestFile', str(request), '-OutputFile', str(target)],
                       check=True, timeout=30, capture_output=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        normalize_tts_wave(target)
        with wave.open(str(target), 'rb') as audio:
            if audio.getparams()[:3] != (1, 2, 16000):
                raise RuntimeError('样音格式与可打断播放器不一致')
            pcm = audio.readframes(audio.getnframes())
            samples = struct.unpack('<{}h'.format(len(pcm) // 2), pcm)
            if not samples or max(abs(value) for value in samples) == 0:
                raise RuntimeError('样音为空或静音')
            results.append(dict(名称=name, 音色=voice, 秒数=audio.getnframes()/16000,
                字节数=target.stat().st_size, 峰值=max(abs(value) for value in samples),
                SHA256=hashlib.sha256(target.read_bytes()).hexdigest()))
    (output / '样音核验.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if '--render' in sys.argv:
        render()
    else:
        adb = find_adb()
        if not board_connected(adb, '20080411'):
            raise SystemExit('开发板未连接，不启动音色测试进程')
        child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--render'],
            stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')
        raise SystemExit(supervise(child, lambda: board_connected(adb, '20080411')))
