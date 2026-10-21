"""复核既有真人录音的真实候选与故事路由，不启动模型、不播放。"""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.deps'))
from audio_core import read_wav
from speech_text import select_voice_text
from vosk import Model, KaldiRecognizer, SetLogLevel

SetLogLevel(-1)
config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
source = ROOT / 'records/实时交互/4cfe8090d3274a15a7e4ad00245ce4b4/turn-1/clean.wav'
samples, pcm = read_wav(source.read_bytes())
recognizer = KaldiRecognizer(Model(config['vosk_model']), 16000)
recognizer.SetMaxAlternatives(5)
texts = []
raw = []
candidates = []
for offset in range(0, len(pcm), 8000):
    if recognizer.AcceptWaveform(pcm[offset:offset + 8000]):
        candidates.append(json.loads(recognizer.Result()))
candidates.append(json.loads(recognizer.FinalResult()))
for candidate in candidates:
    selected = select_voice_text(candidate)
    texts.append(selected['text'])
    raw.append(selected['raw'])
spec = importlib.util.spec_from_file_location('story_intent',
    ROOT.parents[1] / '机器学习/情感陪伴参赛作业/体验/story_intent.py')
intent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intent)
text = ''.join(texts)
result = {'原始识别': ''.join(raw), '校验后识别': text,
          '故事路由': intent.assistant_story_requested([{'role': 'user', 'content': text}]),
          '边界': '既有真人录音经真实Vosk与现有故事路由；不是模型生成或当前真人复测'}
(ROOT / 'records/实时交互/故事候选复核.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
if text != '请讲一个睡前故事' or not result['故事路由']:
    raise SystemExit('真实候选校验未通过')
