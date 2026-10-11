"""启动模拟桥接并实际调用客户端命令，完整保留模拟记录。"""
import json
import os
import subprocess
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pc_server import Pipeline, make_handler, test_tone

out = ROOT / 'records/客户端模拟冒烟'
out.mkdir(parents=True, exist_ok=True)
(out / 'input.wav').write_bytes(test_tone())
token = 'local-smoke-test-only-0123456789'
pipeline = Pipeline({'threshold': 500}, simulate=True)
server = HTTPServer(('127.0.0.1', 0), make_handler(pipeline, token))
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    environment = dict(os.environ, XINYU_BRIDGE_TOKEN=token, PYTHONIOENCODING='utf-8')
    result = subprocess.run([sys.executable, str(ROOT / 'board_client.py'), '--reference',
        '--wav', str(out / 'input.wav'), '--server', f'http://127.0.0.1:{server.server_port}'],
        env=environment, capture_output=True, text=True, encoding='utf-8', timeout=20)
    (out / 'console.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
    passed = result.returncode == 0 and '模拟回复' in result.stdout and '本轮失败' not in result.stdout
    (out / 'result.json').write_text(json.dumps({'scope': '电脑模拟输入→参考门控→模拟桥接→回复文件，非真实模型、非实机',
        'returncode': result.returncode, 'passed': passed}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(result.stdout)
    if not passed:
        sys.exit(1)
finally:
    server.shutdown()
    server.server_close()
    thread.join(3)
