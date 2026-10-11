"""运行离线自动测试并保存实际控制台输出。"""
import io
import json
import platform
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
output = ROOT / 'records/自动测试'
output.mkdir(parents=True, exist_ok=True)
(output / 'output.txt').write_text(stream.getvalue(), encoding='utf-8')
(output / 'result.json').write_text(json.dumps({'environment': platform.platform(),
    'python': sys.version, 'tests': result.testsRun, 'failures': len(result.failures),
    'errors': len(result.errors), 'passed': result.wasSuccessful(),
    'scope': '参考实现、协议和模拟服务，非真实语音模型、非T113实机'}, ensure_ascii=False, indent=2), encoding='utf-8')
print(stream.getvalue())
sys.exit(0 if result.wasSuccessful() else 1)
