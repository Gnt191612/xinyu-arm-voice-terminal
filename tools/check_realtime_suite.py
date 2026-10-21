"""保存实际运行的回归结果，不伪造测试数量或实机结论。"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[1]
output = root / 'records/实时交互'
output.mkdir(parents=True, exist_ok=True)
environment = dict(os.environ, PYTHONIOENCODING='utf-8')
started = time.monotonic()
result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
                        cwd=str(root), env=environment, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=30)
(output / '回归测试.stdout.log').write_bytes(result.stdout)
(output / '回归测试.stderr.log').write_bytes(result.stderr)
match = re.search(r'Ran (\d+) tests', result.stderr.decode('utf-8', errors='replace'))
record = {'退出码': result.returncode, '测试数': int(match.group(1)) if match else None,
          '耗时秒': time.monotonic() - started,
          '通过': result.returncode == 0, '边界': '自动和隔离测试，不代替外放抢话及拔板实测'}
(output / '回归测试结果.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
raise SystemExit(result.returncode)
