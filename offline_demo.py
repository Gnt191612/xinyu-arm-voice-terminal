"""启动前准备USB及离线文件；由外层守护托管，不操作键鼠或Windows网络设置。"""
import argparse
import json
import re
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
from realtime_session import find_adb, find_rndis_host
from supervise_bridge import board_connected

BOARD = '/mnt/UDISK/xinyu-arm-check'
ENV = ('export PYTHONHOME=/mnt/UDISK/xinyu-runtime35/usr; '
       'export LD_LIBRARY_PATH=/mnt/UDISK/xinyu-runtime35/usr/lib; '
       '/mnt/UDISK/xinyu-runtime35/usr/bin/python3 ')
FLAGS = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class PreparationPending(RuntimeError):
    """USB切换已提交，本次电脑进程应退出而不是等待重连。"""


def run_adb(adb, serial, *arguments, timeout=3):
    result = subprocess.run([adb, '-s', serial, *arguments], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, creationflags=FLAGS)
    if result.returncode:
        raise RuntimeError('开发板命令未成功，已停止准备：' + result.stderr.decode('utf-8', errors='replace')[:250])
    return result.stdout.decode('utf-8', errors='replace').strip()


def local_preflight():
    settings = json.loads((ROOT / 'asr-settings.json').read_text(encoding='utf-8'))
    required = [ROOT / '.realtime-build/aec_pipe.exe', ROOT / 'tts-settings.json', ROOT / 'tts-winrt.ps1']
    if settings['backend'] == 'sensevoice':
        model = ROOT / 'models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17'
        required.extend([model / 'model.int8.onnx', model / 'tokens.txt', ROOT / '.asr-deps/sherpa_onnx/__init__.py'])
    elif settings['backend'] == 'vosk':
        config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
        required.append(ROOT / config['vosk_model'] / 'am/final.mdl')
    else:
        raise RuntimeError('未知识别后端，未启动在线服务')
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file() or not path.stat().st_size]
    if missing:
        raise RuntimeError('离线文件缺失：' + '、'.join(missing))


def prepare(adb, serial):
    local_preflight()
    if not board_connected(adb, serial):
        raise RuntimeError('指定开发板未连接，未配置USB')
    for source, target in ((ROOT / 'tools/rndis_trial.py', 'rndis_trial_autoprep.py'),
                           (ROOT / 'tools/board_prepare.py', 'board_prepare.py')):
        run_adb(adb, serial, 'push', str(source), BOARD + '/tools/' + target)
    def board(action):
        return json.loads(run_adb(adb, serial, 'shell', ENV + BOARD + '/tools/board_prepare.py ' + action))
    initial = board('status')
    if initial['mode'] not in ('adb', 'ready'):
        raise RuntimeError('未知USB状态，未配置')
    changed = initial['mode'] == 'adb'
    if changed:
        print('当前为纯ADB，开始一次临时RNDIS准备；未改固件。', flush=True)
        board('start')
        raise PreparationPending('已提交一次板端USB准备，本次电脑进程立即退出，不启动模型。请等待USB就绪后手动再次启动演示；不会自动重连。')
    deadline = time.monotonic() + 25
    host = None
    while time.monotonic() < deadline:
        if not board_connected(adb, serial):
            time.sleep(0.1)
            continue
        current = board('status')
        if current['mode'] == 'ready':
            try:
                host = find_rndis_host()
                break
            except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
        time.sleep(0.2)
    if host is None:
        raise RuntimeError('USB或电脑专用网卡未就绪，未启动模型；没有重复改写USB')
    final = board('confirm')
    audio = run_adb(adb, serial, 'shell', 'arecord -l')
    if len(re.findall(r'^card \d+:.*device \d+:.*USB Audio', audio, re.MULTILINE)) != 1:
        raise RuntimeError('未检测到唯一USB麦克风，未启动模型')
    address = run_adb(adb, serial, 'shell', 'ip addr show usb0')
    expected = '169.254.113.2/16' if host.startswith('169.254.') else '192.168.113.2/30'
    if expected not in address:
        raise RuntimeError('板端专用网段与电脑地址不匹配，未启动模型')
    if initial['boot_id'] != final['boot_id']:
        raise RuntimeError('准备期间开发板重启，停止而不继续演示')
    record = {'准备通过': True, '起始模式': initial['mode'], '临时配置已执行': changed,
              'host': host, 'boot_id': final['boot_id'], '串号': serial,
              '范围': '不改Windows网卡、Wi-Fi、防火墙、固件和开机脚本；不启动模型'}
    output = ROOT / 'records/启动准备'
    output.mkdir(parents=True, exist_ok=True)
    (output / ('准备-' + str(time.time_ns()) + '.json')).write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return host


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serial', default='20080411')
    parser.add_argument('--duration', type=float, default=0)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    try:
        host = prepare(find_adb(), args.serial)
    except PreparationPending as exc:
        print(str(exc), flush=True)
        return 3
    except (RuntimeError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print('启动准备失败，未启动模型：' + str(exc), flush=True)
        return 2
    if args.prepare_only:
        return 0
    return subprocess.call([sys.executable, '-u', str(ROOT / 'realtime_session.py'),
        '--serial', args.serial, '--host', host, '--start-xinyu', '--duration', str(args.duration)],
        stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr, creationflags=FLAGS)


if __name__ == '__main__':
    raise SystemExit(main())
