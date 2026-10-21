"""使用既有实录核对本地识别，不启动心语、不播放，不冒充当前真人测试。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from audio_core import read_wav
from realtime_session import find_adb
from supervise_bridge import board_connected, supervise


def check():
    from sensevoice_asr import SenseVoice
    started = time.monotonic()
    recognizer = SenseVoice()
    print('本地识别器已加载，开始既有录音对照', flush=True)
    cases = [('原轻声录音', 'records/T113真实ARM对照/usb-mic-second.wav'),
             ('第一次故事请求', 'records/实时交互/4cfe8090d3274a15a7e4ad00245ce4b4/turn-1/clean.wav'),
             ('最新故事请求', 'records/实时交互/d7dc74f468524311857548d0e3c5028a/turn-4/clean.wav'),
             ('首次插话', 'records/实时交互/b916311638354eb7b6a45495f5e1f1a8/turn-2/clean.wav'),
             ('最新插话', 'records/实时交互/d7dc74f468524311857548d0e3c5028a/turn-6/clean.wav')]
    results = []
    for name, path in cases:
        _, pcm = read_wav((ROOT / path).read_bytes())
        before = time.monotonic()
        row = {'场景': name, '原始文件': path, '识别': recognizer(pcm), '秒数': time.monotonic()-before}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    results.append({'场景': '纯静音', '识别': recognizer(b'\0' * 32000)})
    output = {'结果': results, '总秒数': time.monotonic()-started,
              '边界': '真实已保存录音离线识别，不代表当前真人双讲通过'}
    (ROOT / 'records/实时交互/新离线识别对照.json').write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')


def check_barge():
    from sensevoice_asr import SenseVoice
    from speech_endpoint import SpeechEndpoint
    from voice_activity import VoiceActivityDetector
    source = ROOT / 'records/实时交互/b7be76a926614969801e14623ed072ff'
    pcm = (source / '最近消回声.pcm').read_bytes()
    recognizer = SenseVoice()
    results = []
    for label, continuation_mode in (('旧分句', 3), ('修复后分句', 1)):
        endpoint = SpeechEndpoint()
        onset = VoiceActivityDetector()
        continuation = VoiceActivityDetector(mode=continuation_mode)
        for offset in range(0, len(pcm)-639, 640):
            frame = pcm[offset:offset+640]
            start = onset.detect(frame)
            ongoing = continuation.detect(frame)
            kind, phrase = endpoint.feed(frame, ongoing if endpoint.frames is not None else start)
            if kind == '结束' and offset / 32000 > 40:
                row = {'算法': label, '片段秒数': len(phrase)/32000,
                       '结束位置秒': offset/32000, '识别': recognizer(phrase)}
                results.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    passed = any(row['算法'] == '修复后分句' and '早餐' in row['识别'] for row in results)
    (ROOT / 'records/实时交互/插话分句回放复核.json').write_text(json.dumps({
        '通过': passed, '结果': results, '边界': '已有真实AEC输出按原样回放，不是新的真人双讲测试'
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    if not passed:
        raise RuntimeError('既有插话复核未保留早餐问题，不能启动重复真人测试')


if __name__ == '__main__':
    if '--child' in sys.argv:
        check_barge() if '--barge' in sys.argv else check()
    else:
        adb = find_adb()
        if not board_connected(adb, '20080411'):
            raise SystemExit('开发板未连接，不启动识别对照进程')
        child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--child',
                                  *(['--barge'] if '--barge' in sys.argv else [])],
            stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')
        raise SystemExit(supervise(child, lambda: board_connected(adb, '20080411')))
