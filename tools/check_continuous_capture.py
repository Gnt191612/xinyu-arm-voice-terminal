"""板端回环实测持续采集与ARM分帧，不代表RNDIS或回声消除通过。"""
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

ROOT = Path('/mnt/UDISK/xinyu-arm-check')
output = ROOT / 'continuous-capture-check'
output.mkdir(exist_ok=True)
log = open(str(output / 'capture.log'), 'wb')
process = None
network = None
received = bytearray()
sequences = []
active = 0
started = time.monotonic()
try:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 18770))
        listener.listen(1)
        listener.settimeout(5)
        process = subprocess.Popen([sys.executable, str(ROOT / 'board_stream.py'),
                                    '--host', '127.0.0.1', '--port', '18770'],
                                   stdout=log, stderr=subprocess.STDOUT)
        network, address = listener.accept()
    network.settimeout(2)
    hello = b''
    while not hello.endswith(b'\n'):
        part = network.recv(1)
        if not part or len(hello) > 4096:
            raise RuntimeError('握手数据异常')
        hello += part
    backend = json.loads(hello.decode())['backend']
    while len(sequences) < 150:
        received.extend(network.recv(649 * 10))
        while len(received) >= 649:
            sequence, total, is_active = struct.unpack_from('<IIB', received)
            del received[:649]
            sequences.append(sequence)
            active += bool(is_active)
    closed_at = time.monotonic()
    network.close()
    network = None
    process.wait(timeout=3)
    elapsed = time.monotonic() - started
    record = {'场景': '板端TCP回环持续采集与真实ARM逐帧处理',
              '后端': backend, '帧数': len(sequences), '每帧毫秒': 20,
              '序号连续': sequences == list(range(len(sequences))),
              '活动帧数': active, '耗时': elapsed,
              '连接关闭后采集进程退出': process.poll() is not None,
              '连接关闭后退出秒数': time.monotonic() - closed_at,
              '边界': '不是RNDIS传输、不是房间AEC或抢话实测'}
    (output / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False), flush=True)
finally:
    if network:
        network.close()
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=2)
    log.close()
