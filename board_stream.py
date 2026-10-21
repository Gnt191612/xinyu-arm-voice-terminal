"""板端持续采集：真实ARM逐帧处理后经RNDIS发送，不按固定录音窗口监听。"""
import argparse
import array
import json
import re
from pathlib import Path
import socket
import select
import struct
import subprocess
import sys
from audio_core import Gate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='192.168.113.1')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--device', help='不指定时选择唯一的USB采集声卡')
    args = parser.parse_args()
    if args.device is None:
        listing = subprocess.check_output(['arecord', '-l']).decode('utf-8', errors='replace')
        devices = re.findall(r'^card (\d+):.*device (\d+):.*USB Audio', listing, re.MULTILINE)
        if len(devices) != 1:
            raise RuntimeError('未找到唯一的USB麦克风，停止而不误用其他声卡')
        args.device = 'plughw:{},{}'.format(*devices[0])
    root = Path(__file__).resolve().parent
    gate = Gate(root / 'libpcm_gate.so', 500)
    token = (root / 'bridge-token.txt').read_text().strip()
    capture = None
    try:
        with socket.create_connection((args.host, args.port), timeout=3) as network:
            network.settimeout(2)
            network.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            network.sendall((json.dumps({'token': token, 'format': 'pcm16-16000-mono',
                                       'backend': gate.backend}) + '\n').encode())
            capture = subprocess.Popen(['arecord', '-q', '-D', args.device, '-t', 'raw',
                                        '-f', 'S16_LE', '-r', '16000', '-c', '1',
                                        '--buffer-time=80000', '--period-time=20000'],
                                       stdout=subprocess.PIPE)
            sequence = 0
            while True:
                if select.select([network], [], [], 0)[0]:
                    if not network.recv(1):
                        break
                    raise RuntimeError('音频连接收到非预期控制数据')
                pcm = b''
                while len(pcm) < 640:
                    part = capture.stdout.read(640 - len(pcm))
                    if not part:
                        raise RuntimeError('麦克风采集已结束')
                    pcm += part
                samples = array.array('h', pcm)
                if sys.byteorder != 'little':
                    samples.byteswap()
                total, active = gate.frame(samples)
                network.sendall(struct.pack('<IIB', sequence, total, active) + pcm)
                sequence += 1
    finally:
        if capture is not None:
            capture.terminate()
            try:
                capture.wait(timeout=1)
            except subprocess.TimeoutExpired:
                capture.kill()
                capture.wait()


if __name__ == '__main__':
    main()
