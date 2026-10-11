"""真实TTS与ASR冒烟检查：合成输入不是真人麦克风输入，不涉及心语。"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from audio_core import Gate, read_wav
from vosk import Model, KaldiRecognizer

out = ROOT / 'records/合成语音识别冒烟'
out.mkdir(parents=True, exist_ok=True)
text = '你好，我今天想和你聊聊天。'
(out / 'input_text.json').write_text(json.dumps({'text': text}, ensure_ascii=False), encoding='utf-8')
subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'tts.ps1'),
    '-RequestFile', str(out / 'input_text.json'), '-OutputFile', str(out / 'input.wav')], check=True, timeout=45)
audio = (out / 'input.wav').read_bytes()
samples, pcm = read_wav(audio)
started = time.perf_counter()
model = Model(os.path.relpath(ROOT / 'models/vosk-model-small-cn-0.22'))
load_time = time.perf_counter() - started
recognizer = KaldiRecognizer(model, 16000)
started = time.perf_counter()
recognized = []
for offset in range(0, len(pcm), 8000):
    if recognizer.AcceptWaveform(pcm[offset:offset + 8000]):
        recognized.append(json.loads(recognizer.Result()).get('text', ''))
recognized.append(json.loads(recognizer.FinalResult()).get('text', ''))
result = {'scope': 'Windows中文TTS→离线Vosk；输入为合成语音，非真人、非板端、未调用心语',
          'input_text': text, 'recognized_text': ''.join(recognized).replace(' ', ''),
          'input_sha256': hashlib.sha256(audio).hexdigest(), 'model_load_seconds': load_time,
          'recognition_seconds': time.perf_counter() - started, 'gate': Gate().analyze(samples)}
(out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in result.items() if key != 'gate'}, ensure_ascii=False, indent=2))
if not result['recognized_text'] or not result['gate']['accepted']:
    sys.exit(1)
