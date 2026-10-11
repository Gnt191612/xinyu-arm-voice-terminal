"""板端按回车录音，半双工播放；--wav用于明确的文件联调。"""
import argparse
import base64
import hashlib
import json
import os
import platform
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from audio_core import Gate, read_wav

ROOT = Path(__file__).resolve().parent


def send_turn(server, token, wav, history):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(server.rstrip('/') + '/turn',
        json.dumps({'audio_wav': base64.b64encode(wav).decode('ascii'), 'history': history}).encode('utf-8'),
        {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}, method='POST')
    try:
        with opener.open(request, timeout=360) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode('utf-8', errors='replace')) from exc


def main():
    parser = argparse.ArgumentParser(description='心语ARM语音终端')
    parser.add_argument('--server', required=True, help='电脑桥接地址，如http://192.168.1.20:8765')
    parser.add_argument('--wav', type=Path, help='仅联调已有WAV，不调用ALSA')
    parser.add_argument('--library', type=Path, default=ROOT / 'arm/libpcm_gate.so')
    parser.add_argument('--reference', action='store_true', help='仅电脑联调使用，不冒充板端汇编')
    parser.add_argument('--capture-device', default='default')
    parser.add_argument('--playback-device', default='default')
    parser.add_argument('--threshold', type=int, default=500)
    args = parser.parse_args()
    token = os.environ.get('XINYU_BRIDGE_TOKEN', '')
    if not token:
        raise SystemExit('请设置环境变量XINYU_BRIDGE_TOKEN')
    if not args.reference and not (platform.system() == 'Linux' and platform.machine().startswith('arm')):
        raise SystemExit('真实动态库模式需要32位ARM Linux；电脑文件联调请明确添加--reference')
    if args.reference and not args.wav:
        raise SystemExit('参考实现仅允许--wav文件联调；开发板录音必须使用ARM汇编')
    gate = Gate(None if args.reference else args.library.resolve(), args.threshold)
    history = []
    print('后端：' + gate.backend)
    while True:
        if not args.wav:
            command = input('回车录制5秒；输入new重开20轮额度；输入q退出：').strip()
            if command == 'q':
                break
            if command == 'new':
                history.clear()
                continue
        if len(history) >= 40:
            print('已达到20轮，请输入new重新开始。')
            continue
        directory = ROOT / 'records' / '板端' / uuid.uuid4().hex
        directory.mkdir(parents=True)
        record = {'backend': gate.backend, 'machine': platform.machine()}
        started = time.perf_counter()
        try:
            if args.wav:
                wav = args.wav.read_bytes()
                (directory / 'input.wav').write_bytes(wav)
            else:
                subprocess.run(['arecord', '-D', args.capture_device, '-t', 'wav', '-f', 'S16_LE',
                                '-r', '16000', '-c', '1', '-d', '5', str(directory / 'input.wav')], check=True, timeout=15)
                wav = (directory / 'input.wav').read_bytes()
            samples, _ = read_wav(wav)
            record['input_sha256'] = hashlib.sha256(wav).hexdigest()
            record['gate'] = gate.analyze(samples)
            if not record['gate']['accepted']:
                raise ValueError(record['gate']['reason'])
            result = send_turn(args.server, token, wav, history)
            reply = base64.b64decode(result.pop('audio_wav'), validate=True)
            read_wav(reply, max_seconds=120)
            (directory / 'reply.wav').write_bytes(reply)
            record['response'] = result
            record['reply_sha256'] = hashlib.sha256(reply).hexdigest()
            print('服务模式：' + result['mode'])
            print('识别：' + result['recognized_text'])
            print('回复：' + result['reply_text'])
            if not args.wav:
                subprocess.run(['aplay', '-D', args.playback_device, str(directory / 'reply.wav')], check=True, timeout=120)
            else:
                print('文件联调已保存回复WAV，未播放到开发板音箱。')
            history.extend([{'role': 'user', 'content': result['recognized_text']},
                            {'role': 'assistant', 'content': result['reply_text']}])
            record['status'] = '成功'
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            record['status'] = '失败'
            record['error'] = str(exc)
            print('本轮失败：' + str(exc))
        finally:
            record['total_seconds'] = time.perf_counter() - started
            (directory / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print('记录：' + str(directory))
        if args.wav:
            break


if __name__ == '__main__':
    main()
