"""用板端真实汇编检查已录制WAV，不发网络请求、不播放。"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_core import Gate, read_wav

parser = argparse.ArgumentParser()
parser.add_argument('wav', type=Path)
parser.add_argument('--library', required=True, type=Path)
args = parser.parse_args()
samples, pcm = read_wav(args.wav.read_bytes())
result = Gate(args.library).analyze(samples)
print(json.dumps({'samples': len(samples), 'seconds': len(samples) / 16000,
                  'peak': max(abs(x) for x in samples), 'gate': result}, ensure_ascii=False))
