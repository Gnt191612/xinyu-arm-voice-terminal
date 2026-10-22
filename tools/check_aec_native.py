"""SpeexDSP合成回声检查；只验证算法链路，不代替房间双讲测试。"""
import array
import json
import math
from pathlib import Path
import random
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
rng = random.Random(20261023)
count = 320 * 600
reference = [int(rng.uniform(-4000, 4000)) for _ in range(count)]
near = [int(1500 * math.sin(2 * math.pi * 211 * i / 16000)) if i > count * 0.75 else 0 for i in range(count)]
microphone = [int(0.55 * reference[i - 800]) + near[i] if i >= 800 else near[i] for i in range(count)]
payload = bytearray()
for offset in range(0, count, 320):
    payload.extend(array.array('h', microphone[offset:offset + 320]).tobytes())
    payload.extend(array.array('h', reference[offset:offset + 320]).tobytes())
started = time.monotonic()
result = subprocess.run([str(ROOT / '.realtime-build/aec_pipe.exe')], input=bytes(payload),
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=True)
clean = array.array('h', result.stdout)
assert len(clean) == count
start, end = int(count * 0.6), int(count * 0.7)
before = sum(x * x for x in microphone[start:end])
after = sum(x * x for x in clean[start:end])
erle = 10 * math.log10(before / max(1, after))
begin = int(count * 0.9)
projections = [(delay, sum(clean[i] * near[i - delay] for i in range(begin, count)) /
                sum(near[i - delay] ** 2 for i in range(begin, count)))
               for delay in (0, 160, 320, 480, 640)]
delay, projection = max(projections, key=lambda item: item[1])
record = {'场景': '可复现的800采样延迟线性合成回声，后段加入独立近端信号',
          '回声衰减dB': erle, '双讲近端保留投影': projection,
          '计入预处理延迟采样': delay,
          '12秒音频计算耗时': time.monotonic() - started,
          '通过': erle > 12 and projection > 0.25,
          '边界': '不是房间外放实测，不代表实际双讲已经通过'}
output = ROOT / 'records/实时交互/AEC算法验证.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
assert record['通过']
