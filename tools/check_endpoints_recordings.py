"""复核既有实录的连续分句及外放自触发，不生成假真人记录。"""
import array
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.realtime-deps'))
import webrtcvad
from audio_core import Gate, read_wav
from speech_endpoint import SpeechEndpoint

checks = [('原真人录音', ROOT / 'records/T113真实ARM对照/usb-mic-second.wav'),
          ('房间外放AEC输出', ROOT / 'records/实时交互/4320321e4883447c8ae5e3d8d23e7d2c/clean.pcm')]
results = []
gate = Gate(threshold=500)
for name, path in checks:
    data = path.read_bytes()
    pcm = read_wav(data)[1] if path.suffix == '.wav' else data
    for mode in ('旧固定门限', 1, 2, 3):
        endpoint = SpeechEndpoint()
        detector = webrtcvad.Vad(mode) if isinstance(mode, int) else None
        events = []
        for offset in range(0, len(pcm) - 639, 640):
            frame = pcm[offset:offset + 640]
            total, loud = gate.frame(array.array('h', frame))
            active = detector.is_speech(frame, 16000) and total >= 320 * 50 if detector else loud
            kind, phrase = endpoint.feed(frame, active)
            if kind:
                events.append({'事件': kind, '秒': offset / 32000})
        results.append({'场景': name, '算法': mode, '事件': events, '补充静音': False})
output = ROOT / 'records/实时交互/既有录音分句复核.json'
output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False))
