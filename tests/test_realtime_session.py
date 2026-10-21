"""隔离会话集成测试：音频与任务均为测试替身，不冒充实机抢话。"""
import array
import base64
import io
import json
import math
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from audio_core import Gate
import wave

import realtime_session as session


class FakeProcess:
    def __init__(self, done=False):
        self.returncode = 0 if done else None
        self.pid = 123

    def poll(self):
        return self.returncode


class FakeEcho:
    def __init__(self, *args):
        self.process = FakeProcess()
        self.process.stdin = io.BytesIO()
        self.process.stdout = io.BytesIO()

    def process_frame(self, microphone, reference):
        return microphone


class FakePlayer:
    instances = []

    def __init__(self, *args):
        self.active = False
        self.closed = False
        self.instances.append(self)

    def play(self, wav):
        self.active = True

    def stop(self):
        self.active = False

    def close(self):
        self.stop()
        self.closed = True


class SlowOnceEcho(FakeEcho):
    def __init__(self, *args):
        super().__init__(*args)
        self.frames = 0

    def process_frame(self, microphone, reference):
        self.frames += 1
        if self.frames == 40:
            time.sleep(0.3)
        return microphone


class FakeVoiceDetector:
    def __init__(self, mode=3):
        pass

    def detect(self, pcm):
        return Gate(threshold=500).frame(array.array('h', pcm))[1]


class SessionTests(unittest.TestCase):
    @patch('realtime_session.subprocess.check_output')
    def test_usb_address_selection_is_read_only_and_prefers_fixed(self, query):
        query.return_value = b'169.254.234.131\r\n192.168.113.1\r\n'
        self.assertEqual(session.find_rndis_host(), '192.168.113.1')
        query.return_value = b'169.254.234.131\r\n'
        self.assertEqual(session.find_rndis_host(), '169.254.234.131')
        query.return_value = b'10.0.0.1\r\n'
        with self.assertRaises(RuntimeError):
            session.find_rndis_host()

    def test_sentence_reply_barge_in_and_stream_close_cleanup(self):
        self.run_session(False)

    def test_empty_interruption_does_not_swallow_pending_answer(self):
        self.run_session(True)

    def test_short_receive_delay_does_not_discard_audio(self):
        self.run_session(False, SlowOnceEcho)

    def run_session(self, recover_pending, echo_type=FakeEcho):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.json').write_text(json.dumps({'token': 'test-only-token', 'threshold': 500}))
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            processes = []
            feed_threads = []

            def feed():
                with socket.create_connection(('127.0.0.1', port)) as network:
                    network.sendall((json.dumps({'token': 'test-only-token', 'backend': 'ARM汇编动态库',
                                               'format': 'pcm16-16000-mono'}) + '\n').encode())
                    speech = array.array('h', [int(2500 * math.sin(2 * math.pi * 440 * i / 16000))
                                               for i in range(320)]).tobytes()
                    pattern = [False] * 10 + [True] * 20 + [False] * 45 + [True] * 10 + [False] * (45 if recover_pending else 5)
                    import struct
                    for sequence, active in enumerate(pattern):
                        network.sendall(struct.pack('<IIB', sequence, 1000 if active else 0, active) +
                                        (speech if active else b'\0' * 640))
                        time.sleep(0.02)

            def spawn(argv, **kwargs):
                if 'realtime_worker.py' in str(argv):
                    directory = Path(argv[-1])
                    result = {'ok': True, 'result': {'recognized_text': '测试替身输入',
                              'reply_text': '测试替身回复', 'audio_wav': base64.b64encode(b'test').decode()}}
                    if recover_pending and 'turn-2' == directory.name:
                        result = {'ok': False, 'error': '测试替身：新片段没有文字'}
                        processes[1].returncode = 0
                    (directory / 'worker-result.json').write_text(json.dumps(result))
                    process = FakeProcess(done=not (recover_pending and directory.name == 'turn-1'))
                else:
                    process = FakeProcess()
                    thread = threading.Thread(target=feed)
                    feed_threads.append(thread)
                    thread.start()
                processes.append(process)
                return process

            def stop(process):
                process.returncode = -1

            argv = ['realtime_session.py', '--host', '127.0.0.1', '--port', str(port), '--duration', '4']
            with patch.object(session, 'ROOT', root), patch.object(session, 'find_adb', return_value='test-adb'), \
                 patch.object(session, 'board_connected', return_value=True), \
                 patch.object(session, 'InterruptiblePlayer', FakePlayer), \
                 patch.object(session, 'EchoCanceller', echo_type), \
                 patch.object(session, 'VoiceActivityDetector', FakeVoiceDetector), \
                 patch.object(session.subprocess, 'run'), patch.object(session.subprocess, 'Popen', side_effect=spawn), \
                 patch.object(session, 'stop_owned_process', side_effect=stop), patch('sys.argv', argv):
                self.assertEqual(session.main(), 0)
            for thread in feed_threads:
                thread.join(timeout=1)
                self.assertFalse(thread.is_alive())
            result_path = next(root.glob('records/实时交互/*/session.json'))
            result = json.loads(result_path.read_text(encoding='utf-8'))
            self.assertEqual(result['status'], '开发板音频流关闭')
            if echo_type is SlowOnceEcho:
                self.assertTrue(any(x['event'] == '音频接收暂时滞后，沿用原始采样时间轴' for x in result['events']))
            self.assertTrue(any(x['event'] == '自然句尾提交' for x in result['events']))
            if recover_pending:
                self.assertTrue(any(x['event'] == '新片段无有效回复，恢复上一句待答任务' for x in result['events']))
                self.assertTrue(any(x['event'] == '开始回答' for x in result['events']))
            else:
                self.assertTrue(any(x.get('interrupted_playback') for x in result['events']))
            self.assertTrue(FakePlayer.instances[-1].closed)
            self.assertTrue(all(process.poll() is not None for process in processes))
