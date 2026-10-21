"""实时交互基础测试；不冒充麦克风、回声消除或实机抢话验收。"""
import subprocess
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from speech_endpoint import SpeechEndpoint
from supervise_bridge import board_connected, supervise, stop_owned_process
import supervise_bridge


class EndpointTests(unittest.TestCase):
    def endpoint(self):
        return SpeechEndpoint(frame_bytes=2, pre_frames=4, start_frames=2,
                              silence_frames=3, max_frames=12)

    def test_silence_and_short_noise_do_not_start(self):
        endpoint = self.endpoint()
        for active in [False] * 50 + [True, False] * 20:
            self.assertEqual(endpoint.feed(b'00', active), (None, None))

    def test_start_preserves_prefix_and_silence_ends(self):
        endpoint = self.endpoint()
        for frame, active in [(b'00', False), (b'11', True)]:
            endpoint.feed(frame, active)
        self.assertEqual(endpoint.feed(b'22', True), ('开口', None))
        for frame in (b'33', b'44'):
            self.assertEqual(endpoint.feed(frame, False), (None, None))
        self.assertEqual(endpoint.feed(b'55', False), ('结束', b'001122334455'))
        self.assertEqual(endpoint.feed(b'66', False), (None, None))

    def test_long_speech_is_bounded_and_next_sentence_works(self):
        endpoint = self.endpoint()
        events = [endpoint.feed(b'00', True) for _ in range(12)]
        self.assertEqual(events[-1], ('结束', b'00' * 12))
        self.assertEqual(endpoint.feed(b'11', True), (None, None))
        self.assertEqual(endpoint.feed(b'22', True), ('开口', None))

    def test_partial_frame_rejected(self):
        with self.assertRaises(ValueError):
            self.endpoint().feed(b'0', True)


class LifecycleTests(unittest.TestCase):
    @patch('supervise_bridge.supervise', return_value=4)
    @patch('supervise_bridge.subprocess.Popen')
    @patch('supervise_bridge.board_connected', return_value=True)
    def test_realtime_entry_has_independent_hidden_supervisor(self, connected, spawn, monitor):
        with patch.object(sys, 'argv', ['supervise_bridge.py', '--adb', 'adb', '--realtime']):
            self.assertEqual(supervise_bridge.main(), 4)
        command = spawn.call_args.args[0]
        self.assertTrue(command[2].endswith('realtime_session.py'))
        self.assertIn('--start-xinyu', command)
        self.assertEqual(spawn.call_args.kwargs['creationflags'],
                         subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        monitor.assert_called_once()

    @patch('supervise_bridge.subprocess.run')
    def test_other_board_does_not_keep_session_alive(self, run):
        run.return_value = Mock(returncode=0, stdout=b'List of devices attached\nother\tdevice\n')
        self.assertFalse(board_connected('adb', '20080411'))
        run.return_value.stdout += b'20080411\tdevice\n'
        self.assertTrue(board_connected('adb', '20080411'))

    @patch('supervise_bridge.stop_owned_process')
    def test_disconnect_stops_owned_process_within_budget(self, stop):
        process = Mock()
        process.poll.return_value = None
        now = [0.0]
        result = supervise(process, lambda: False, clock=lambda: now[0],
                           sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        self.assertEqual(result, 4)
        self.assertLess(now[0], 1.1)
        stop.assert_called_once_with(process)

    def test_real_owned_child_is_reaped(self):
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                   start_new_session=sys.platform != 'win32')
        started = time.monotonic()
        try:
            stop_owned_process(process)
            self.assertIsNotNone(process.poll())
            self.assertLess(time.monotonic() - started, 3)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    @unittest.skipUnless(os.name == 'nt', '本测试验证Windows自建进程树清理')
    def test_owned_descendant_is_also_reaped(self):
        import ctypes
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'owned-child.pid'
            code = ('import subprocess,sys,time;from pathlib import Path;'
                    'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);'
                    'Path(sys.argv[1]).write_text(str(p.pid));time.sleep(60)')
            process = subprocess.Popen([sys.executable, '-c', code, str(marker)])
            child_pid = None
            try:
                deadline = time.monotonic() + 3
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(marker.exists())
                child_pid = int(marker.read_text())
                stop_owned_process(process)
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.OpenProcess.restype = ctypes.c_void_p
                kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                handle = kernel.OpenProcess(0x1000, False, child_pid)
                if handle:
                    status = ctypes.c_ulong()
                    try:
                        self.assertTrue(kernel.GetExitCodeProcess(handle, ctypes.byref(status)))
                        self.assertNotEqual(status.value, 259)
                    finally:
                        kernel.CloseHandle(handle)
            finally:
                if process.poll() is None:
                    stop_owned_process(process)
