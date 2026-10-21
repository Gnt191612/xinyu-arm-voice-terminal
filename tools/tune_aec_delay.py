"""离线扫描已录房间回灌的参考延迟；不播放、不冒充真人双讲验收。"""
import array
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
directory = Path(sys.argv[1])
microphone = (directory / 'microphone.pcm').read_bytes()
reference = (directory / 'reference.pcm').read_bytes()
count = min(len(microphone), len(reference)) // 640
rows = []
for delta_ms in range(-120, 241, 20):
    shift = delta_ms // 20
    packet = bytearray()
    for frame in range(count):
        source = frame - shift
        ref = reference[source * 640:(source + 1) * 640] if 0 <= source < count else b'\0' * 640
        packet.extend(microphone[frame * 640:(frame + 1) * 640] + ref)
    result = subprocess.run([str(ROOT / '.realtime-build/aec_pipe.exe')], input=bytes(packet),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=True)
    clean = array.array('h', result.stdout)
    # 前半段选择参数，后半段独立检查，避免只报告单个最小能量片段。
    middle = len(clean) // 2
    fitting = clean[max(0, middle - 48000):middle]
    validation = clean[max(middle, len(clean) - 80000):]
    rows.append({'reference_delay_ms': 120 + delta_ms,
                 'fit_mean_square': sum(x*x for x in fitting) / max(1, len(fitting)),
                 'validation_mean_square': sum(x*x for x in validation) / max(1, len(validation))})
best = min(rows, key=lambda row: row['fit_mean_square'])
record = {'选择': best, '全部候选': rows,
          '边界': '只用单段房间回灌做延迟候选筛选；需重新实测及真人双讲验证'}
(directory / 'delay-scan.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(best))
