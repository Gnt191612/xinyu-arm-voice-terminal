"""持续采集、AEC、自然分句与抢话；只托管自己启动的进程。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import deque
import array
import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
import wave

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.realtime-deps'))
sys.path.append(str(ROOT / '.deps'))
from audio_core import Gate
from realtime_audio import EchoCanceller, InterruptiblePlayer, RenderReference
from speech_endpoint import SpeechEndpoint
from voice_activity import VoiceActivityDetector
from supervise_bridge import board_connected, stop_owned_process


def write_wav(path, pcm):
    with wave.open(str(path), 'wb') as target:
        target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        target.writeframes(pcm)


def find_adb():
    adb = shutil.which('adb')
    if adb:
        return adb
    for parent in ROOT.parents:
        path = parent / 'flash_tools/android-platform-tools/platform-tools/adb.exe'
        if path.is_file():
            return str(path)
    raise RuntimeError('找不到adb.exe')


def find_rndis_host():
    """仅读取本任务网卡地址；不重配网络，也不触碰其他网卡。"""
    command = ("$ProgressPreference='SilentlyContinue'; "
               "$a=@(Get-NetAdapter | Where-Object { $_.MacAddress -eq '02-11-30-00-00-01' }); "
               "if($a.Count -ne 1){exit 1}; "
               "Get-NetIPAddress -InterfaceIndex $a[0].ifIndex -AddressFamily IPv4 | "
               "Where-Object AddressState -eq 'Preferred' | Select-Object -ExpandProperty IPAddress")
    encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
    result = subprocess.check_output(['powershell.exe', '-NoProfile', '-EncodedCommand', encoded],
        timeout=15, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    addresses = result.decode('ascii').split()
    if '192.168.113.1' in addresses:
        return '192.168.113.1'
    local = [address for address in addresses if address.startswith('169.254.')]
    if len(local) == 1:
        return local[0]
    raise RuntimeError('本任务USB网卡没有唯一可用地址，未修改网络配置')


def main():
    parser = argparse.ArgumentParser(description='持续监听和外放抢话会话')
    parser.add_argument('--serial', default='20080411')
    parser.add_argument('--host', help='不指定时只读取本任务USB网卡的固定或链路本地地址')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--reference-delay-ms', type=float, default=120)
    parser.add_argument('--output-device', type=int)
    parser.add_argument('--duration', type=float, default=0, help='限定连续采集秒数，不含模型加载；0为直到断板或Ctrl+C')
    parser.add_argument('--calibration-wav', type=Path, help='只播放指定音频并保存回灌与AEC结果，不调用模型')
    parser.add_argument('--start-xinyu', action='store_true', help='本机心语未运行时启动并托管，退出时只关闭本次启动的模型进程')
    args = parser.parse_args()
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    adb = find_adb()
    if not board_connected(adb, args.serial):
        raise SystemExit('指定开发板未连接，未启动任何音频任务。')
    directory = ROOT / 'records/实时交互' / uuid.uuid4().hex
    directory.mkdir(parents=True)
    stop = threading.Event()
    player = worker = capture = echo = network = xinyu_process = None
    logs = []
    events = []
    started = time.monotonic()
    watchdog = None
    status = '异常退出'
    received_frames = 0
    calibration_openings = 0
    cleanup = ThreadPoolExecutor(max_workers=4)
    recent_audio = deque(maxlen=3000)
    fallback = None

    def event(kind, **details):
        entry = {'time': time.monotonic() - started, 'event': kind, **details}
        events.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    def watch_board():
        missing = None
        while not stop.wait(0.2):
            if board_connected(adb, args.serial):
                missing = None
            else:
                missing = missing or time.monotonic()
                if time.monotonic() - missing >= 0.75:
                    stop.set()
                    if player:
                        player.stop()
                    return

    try:
        # 上传源码而不是覆盖原来的单轮客户端。
        if args.host is None:
            args.host = find_rndis_host()
        subprocess.run([adb, '-s', args.serial, 'push', str(ROOT / 'board_stream.py'),
                        '/mnt/UDISK/xinyu-arm-check/board_stream.py'], check=True, timeout=5,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                       stdout=subprocess.DEVNULL)
        reference = RenderReference()
        player = InterruptiblePlayer(reference, args.output_device)
        aec_log = open(directory / 'aec.log', 'wb')
        logs.append(aec_log)
        echo = EchoCanceller(ROOT / '.realtime-build/aec_pipe.exe', aec_log)
        endpoint = SpeechEndpoint()
        voice_detector = VoiceActivityDetector()
        continuation_detector = VoiceActivityDetector(mode=1)
        watchdog = threading.Thread(target=watch_board, daemon=True)
        watchdog.start()
        if args.start_xinyu and not args.calibration_wav:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def healthy():
                try:
                    with opener.open(config['xinyu_url'].rstrip('/') + '/health', timeout=0.5) as response:
                        return response.status == 200
                except OSError:
                    return False
            if not healthy():
                project = Path(os.environ.get('XINYU_PROJECT_DIR') or
                               ROOT.parents[1] / '机器学习/情感陪伴参赛作业')
                executable = project / '.venv/Scripts/python.exe'
                application = project / '体验/chat_app.py'
                if not executable.is_file() or not application.is_file():
                    raise RuntimeError('未找到既有心语入口；没有下载或安装其他模型')
                model_log = open(directory / 'xinyu.log', 'wb')
                logs.append(model_log)
                xinyu_process = subprocess.Popen([str(executable), '-u', str(application)],
                                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                                 cwd=str(project), stdout=model_log, stderr=subprocess.STDOUT)
                event('启动本次托管心语，退出时自动清理')
                deadline = time.monotonic() + 120
                while not healthy():
                    if stop.wait(0.2) or xinyu_process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('心语启动未完成或开发板已断开，清理本次进程')
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((args.host, args.port))
            listener.listen(1)
            listener.settimeout(0.2)
            capture_log = open(directory / 'board.log', 'wb')
            logs.append(capture_log)
            command = ('export PYTHONHOME=/mnt/UDISK/xinyu-runtime35/usr; '
                       'export LD_LIBRARY_PATH=/mnt/UDISK/xinyu-runtime35/usr/lib; '
                       'exec /mnt/UDISK/xinyu-runtime35/usr/bin/python3 '
                       '/mnt/UDISK/xinyu-arm-check/board_stream.py --host {} --port {}').format(args.host, args.port)
            capture = subprocess.Popen([adb, '-s', args.serial, 'shell', command],
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                       stdout=capture_log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 10
            while not stop.is_set() and time.monotonic() < deadline:
                try:
                    network, address = listener.accept()
                    break
                except socket.timeout:
                    if capture.poll() is not None:
                        raise RuntimeError('板端采集启动失败，见board.log')
            if network is None:
                raise RuntimeError('没有收到开发板连续音频连接')
        network.settimeout(0.2)
        hello = bytearray()
        while not hello.endswith(b'\n') and len(hello) < 4096:
            part = network.recv(1)
            if not part:
                raise RuntimeError('音频握手提前结束')
            hello.extend(part)
        hello = json.loads(hello)
        if not hmac.compare_digest(hello.get('token', ''), config['token']):
            raise RuntimeError('音频流鉴权失败')
        if hello.get('backend') != 'ARM汇编动态库' or hello.get('format') != 'pcm16-16000-mono':
            raise RuntimeError('板端后端或音频格式不符')
        event('连续采集已连接', peer=address[0], backend=hello['backend'])
        stream_started = time.monotonic()
        if args.calibration_wav:
            player.play(args.calibration_wav.read_bytes())
            event('回声校准播放开始')
        frames = bytearray()
        history = []
        pending_history = None
        turn_directory = None
        generation = 0
        previous_sequence = -1
        anchor = None
        lagging = False
        last_data = time.monotonic()
        raw_file = open(directory / 'microphone.pcm', 'wb')
        ref_file = open(directory / 'reference.pcm', 'wb')
        clean_file = open(directory / 'clean.pcm', 'wb')
        arm_file = open(directory / 'arm-frames.csv', 'w', encoding='utf-8')
        arm_file.write('sequence,sum_abs,active\n')
        logs.extend([raw_file, ref_file, clean_file, arm_file])
        while not stop.is_set():
            if args.duration and time.monotonic() - stream_started >= args.duration:
                status = '限定测试正常结束'
                break
            try:
                part = network.recv(649 * 10)
                if not part:
                    status = '开发板音频流关闭'
                    break
                frames.extend(part)
                last_data = time.monotonic()
            except socket.timeout:
                if time.monotonic() - last_data > 1.5:
                    status = '开发板音频流超时'
                    break
            while len(frames) >= 649:
                sequence, arm_total, arm_active = struct.unpack_from('<IIB', frames)
                microphone = bytes(frames[9:649])
                del frames[:649]
                if sequence != previous_sequence + 1:
                    raise RuntimeError('连续音频序号不连续，停止而非拼接错位帧')
                previous_sequence = sequence
                received_frames += 1
                now = time.monotonic()
                if anchor is None:
                    anchor = now
                capture_time = anchor + sequence * 0.02
                lag = now - capture_time
                if lag > 1.0 or lag < -0.15:
                    event('音频时序漂移', drift=now - capture_time)
                    raise RuntimeError('音频积压超过1秒或采样时钟超前，停止会话')
                if lag > 0.15 and not lagging:
                    event('音频接收暂时滞后，沿用原始采样时间轴', lag=lag)
                    lagging = True
                elif lag < 0.1 and lagging:
                    event('音频接收滞后已恢复')
                    lagging = False
                rendered = reference.at(capture_time - args.reference_delay_ms / 1000)
                clean = echo.process_frame(microphone, rendered)
                recent_audio.append((microphone, rendered, clean))
                # 连续诊断只保存开头60秒，避免长时间监听无限占用磁盘。
                if sequence < 3000:
                    raw_file.write(microphone)
                    ref_file.write(rendered)
                    clean_file.write(clean)
                    arm_file.write('{},{},{}\n'.format(sequence, arm_total, arm_active))
                onset_active = voice_detector.detect(clean)
                continuation_active = continuation_detector.detect(clean)
                active = continuation_active if endpoint.frames is not None else onset_active
                kind, phrase = endpoint.feed(clean, active)
                if args.calibration_wav:
                    if kind == '开口':
                        calibration_openings += 1
                    continue
                if kind == '开口':
                    generation += 1
                    was_playing = player.active
                    player.stop()
                    # 被截断的整段回复不作为已经完整说出的对话历史。
                    pending_history = None
                    if worker is not None:
                        # 暂存旧任务，待新句确实识别成功才丢弃；短噪声不能吞掉上一句。
                        if fallback is None:
                            fallback = (worker, turn_directory)
                        else:
                            cleanup.submit(stop_owned_process, worker)
                        worker = None
                    event('开口并撤销旧回复', generation=generation, interrupted_playback=was_playing)
                elif kind == '结束':
                    turn_directory = directory / ('turn-{}'.format(generation))
                    turn_directory.mkdir()
                    write_wav(turn_directory / 'clean.wav', phrase)
                    (turn_directory / 'endpoint.json').write_text(json.dumps({
                        'onset_frames': endpoint.start_frames,
                        'sha256': hashlib.sha256((turn_directory / 'clean.wav').read_bytes()).hexdigest()
                    }, ensure_ascii=False), encoding='utf-8')
                    diagnostic_frames = list(recent_audio)[-(len(phrase) // 640):]
                    write_wav(turn_directory / 'microphone.wav', b''.join(frame[0] for frame in diagnostic_frames))
                    write_wav(turn_directory / 'reference.wav', b''.join(frame[1] for frame in diagnostic_frames))
                    (turn_directory / 'history.json').write_text(json.dumps(history[-38:], ensure_ascii=False), encoding='utf-8')
                    log = open(turn_directory / 'worker.log', 'wb')
                    logs.append(log)
                    worker = subprocess.Popen([sys.executable, '-u', str(ROOT / 'realtime_worker.py'), str(turn_directory)],
                                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                               cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
                    event('自然句尾提交', generation=generation, seconds=len(phrase) / 32000)
            if worker is not None and worker.poll() is not None:
                result_path = turn_directory / 'worker-result.json'
                succeeded = False
                if not result_path.exists():
                    event('单句任务异常退出', returncode=worker.returncode)
                else:
                    payload = json.loads(result_path.read_text(encoding='utf-8'))
                    if payload['ok']:
                        succeeded = True
                        if fallback is not None:
                            cleanup.submit(stop_owned_process, fallback[0])
                            fallback = None
                        result = payload['result']
                        player.play(base64.b64decode(result['audio_wav']))
                        pending_history = [{'role': 'user', 'content': result['recognized_text']},
                                           {'role': 'assistant', 'content': result['reply_text']}]
                        event('开始回答', recognized_text=result['recognized_text'], reply_text=result['reply_text'])
                    else:
                        event('单句任务失败', error=payload['error'])
                worker = None
                if not succeeded and fallback is not None:
                    worker, turn_directory = fallback
                    fallback = None
                    event('新片段无有效回复，恢复上一句待答任务')
            if pending_history is not None and not player.active:
                event('回答播放自然结束')
                history.extend(pending_history)
                pending_history = None
        if stop.is_set():
            status = '开发板断开，自动退出'
    except KeyboardInterrupt:
        status = '用户结束会话'
    except Exception as exc:
        status = '失败：' + str(exc)
        event('会话失败', error=str(exc))
    finally:
        stop.set()
        if player:
            player.close()
        if network:
            network.close()
        owned = [process for process in (worker, fallback[0] if fallback else None,
                 capture, echo.process if echo else None, xinyu_process)
                 if process is not None]
        # 并行清理自建进程，避免多个独立超时相加导致断板后拖延退出。
        list(cleanup.map(stop_owned_process, owned))
        cleanup.shutdown(wait=True)
        if echo:
            echo.process.stdin.close()
            echo.process.stdout.close()
        if watchdog:
            watchdog.join(timeout=0.6)
        # 有界保存最近60秒，覆盖等待真人操作较久的场景；不无限增长。
        for index, name in enumerate(('最近麦克风.pcm', '最近播放参考.pcm', '最近消回声.pcm')):
            with open(directory / name, 'wb') as diagnostic:
                for frame in recent_audio:
                    diagnostic.write(frame[index])
        for log in logs:
            log.close()
        (directory / 'session.json').write_text(json.dumps({'status': status, 'events': events,
            'seconds': time.monotonic() - started, 'reference_delay_ms': args.reference_delay_ms,
            'stream_frames': received_frames, 'calibration_openings': calibration_openings,
            'aec': 'SpeexDSP 1.2.1，500ms滤波器；效果需本机实测'}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(status + '；记录：' + str(directory), flush=True)
    return 2 if status.startswith('失败') else 0


if __name__ == '__main__':
    raise SystemExit(main())
