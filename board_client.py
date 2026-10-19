"""板端按回车录音，半双工播放；--wav用于明确的文件联调。"""
import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from audio_core import Gate, read_wav
from board_audio import list_audio_devices

ROOT = Path(__file__).resolve().parent


def check_audio_tools(capture_device, playback_device, playback_target='board'):
    if not capture_device or (playback_target == 'board' and not playback_device):
        raise ValueError('真实录音必须显式指定--capture-device；板端播放模式还需--playback-device')
    missing = [name for name in (('arecord', 'aplay') if playback_target == 'board' else ('arecord',)) if not shutil.which(name)]
    if missing:
        raise ValueError('固件缺少ALSA工具：' + ', '.join(missing) + '；请在匹配的Tina SDK中补齐alsa-utils')


def send_turn(server, token, wav, history):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(server.rstrip('/') + '/turn',
        json.dumps({'audio_wav': base64.b64encode(wav).decode('ascii'), 'history': history}).encode('utf-8'),
        {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token}, method='POST')
    try:
        with opener.open(request, timeout=360) as response:
            # 板端为 Python 3.5.6：其 json.load 不接受 bytes（3.6 起才支持），此处显式解码。
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode('utf-8', errors='replace')) from exc


def main():
    parser = argparse.ArgumentParser(description='心语ARM语音终端')
    parser.add_argument('--server', help='电脑桥接地址，如http://192.168.1.20:8765')
    parser.add_argument('--list-audio', action='store_true', help='只列出录放音设备，不录音、不访问电脑服务')
    parser.add_argument('--wav', type=Path, help='仅联调已有WAV，不调用ALSA')
    parser.add_argument('--library', type=Path, default=ROOT / 'arm/libpcm_gate.so')
    parser.add_argument('--reference', action='store_true', help='仅电脑联调使用，不冒充板端汇编')
    parser.add_argument('--capture-device', help='实际USB麦克风设备，如plughw:CARD=实际ID,DEV=0')
    parser.add_argument('--playback-device', help='实际音箱输出设备，不默认选择录音声卡')
    parser.add_argument('--playback-target', choices=('pc', 'board'), default='pc',
                        help='默认电脑外放；board需额外指定板端播放设备')
    parser.add_argument('--records-dir', type=Path, default=ROOT / 'records' / '板端',
                        help='记录目录；Tina建议指定已确认可写且空间充足的挂载点')
    parser.add_argument('--threshold', type=int, default=500)
    args = parser.parse_args()
    if args.list_audio:
        print(json.dumps({'devices': list_audio_devices(),
                          'scope': '仅枚举端点；USB声卡的录音口不是自动选中的麦克风，实际出声待验'},
                         ensure_ascii=False, indent=2))
        return
    if not args.server:
        parser.error('语音会话必须指定--server')
    token = os.environ.get('XINYU_BRIDGE_TOKEN', '')
    if not token:
        raise SystemExit('请设置环境变量XINYU_BRIDGE_TOKEN')
    if not args.reference and not (platform.system() == 'Linux' and platform.machine().startswith('arm')
                                   and struct.calcsize('P') == 4):
        raise SystemExit('真实动态库模式需要32位ARM Linux；电脑文件联调请明确添加--reference')
    if args.reference and not args.wav:
        raise SystemExit('参考实现仅允许--wav文件联调；开发板录音必须使用ARM汇编')
    if not args.wav:
        try:
            check_audio_tools(args.capture_device, args.playback_device, args.playback_target)
        except ValueError as exc:
            parser.error(str(exc))
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
        directory = Path(os.path.abspath(str(args.records_dir))) / uuid.uuid4().hex
        directory.mkdir(parents=True)
        record = {'backend': gate.backend, 'machine': platform.machine(),
                  'capture_device': args.capture_device, 'playback_device': args.playback_device,
                  'audio_source': '已有WAV文件' if args.wav else 'ALSA录音设备',
                  'playback_command_completed': False, 'audible_output_verified': False}
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
            if result.get('playback_target', 'board') != args.playback_target:
                raise ValueError('电脑与板端播放模式不一致，请统一--playback-target')
            if args.playback_target == 'board':
                reply = base64.b64decode(result.pop('audio_wav'), validate=True)
                read_wav(reply, max_seconds=120)
                (directory / 'reply.wav').write_bytes(reply)
                record['reply_sha256'] = hashlib.sha256(reply).hexdigest()
            record['response'] = result
            record['playback_target'] = args.playback_target
            print('服务模式：' + result['mode'])
            print('识别：' + result['recognized_text'])
            print('回复：' + result['reply_text'])
            if args.playback_target == 'pc':
                print('电脑播放命令已完成；实际出声待人工确认。' if result.get('playback_command_completed')
                      else '电脑未报告播放完成；模拟模式不实际播放声音。')
            elif not args.wav:
                subprocess.run(['aplay', '-D', args.playback_device, str(directory / 'reply.wav')], check=True, timeout=120)
                record['playback_command_completed'] = True
                print('ALSA播放命令已完成；音箱是否实际出声仍需人工确认。')
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
