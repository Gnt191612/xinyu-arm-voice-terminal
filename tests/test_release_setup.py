"""发布准备和新重试路径的离线检查，不触碰实际开发板。"""
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import supervise_bridge

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_setup', ROOT / 'tools/setup_environment.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class ReleaseTests(unittest.TestCase):
    def test_unpack_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive = base / 'sample.tar'
            with tarfile.open(archive, 'w') as package:
                item = tarfile.TarInfo('../outside.txt')
                item.size = 1
                package.addfile(item, io.BytesIO(b'x'))
            with self.assertRaises(RuntimeError):
                setup.unpack(archive, base / 'out')
            self.assertFalse((base / 'outside.txt').exists())

    def test_unpack_regular_file(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            archive = base / 'sample.tar'
            with tarfile.open(archive, 'w') as package:
                item = tarfile.TarInfo('source/COPYING')
                item.size = 2
                package.addfile(item, io.BytesIO(b'ok'))
            setup.unpack(archive, base / 'out')
            self.assertEqual((base / 'out/source/COPYING').read_bytes(), b'ok')

    def test_retry_stops_without_reconnect_wait(self):
        process = MagicMock()
        process.poll.return_value = 0
        with patch.object(supervise_bridge.subprocess, 'Popen', return_value=process) as start, \
                patch.object(supervise_bridge, 'supervise', return_value=4):
            result = supervise_bridge.supervise_with_retry('adb', 'serial', lambda: ['test'],
                lambda: False, clock=lambda: 0, sleep=lambda value: None)
        self.assertEqual(result, 4)
        self.assertEqual(start.call_count, 1)

    def test_pending_usb_is_not_retried(self):
        process = MagicMock()
        process.poll.return_value = 0
        with patch.object(supervise_bridge.subprocess, 'Popen', return_value=process) as start, \
                patch.object(supervise_bridge, 'supervise', return_value=3):
            self.assertEqual(supervise_bridge.supervise_with_retry('adb', 'serial',
                lambda: ['test'], lambda: True), 3)
        self.assertEqual(start.call_count, 1)

    def test_prepare_flags_survive_retry_builder(self):
        seen = []
        def capture(adb, serial, builder, connected):
            seen.extend(builder())
            return 0
        with patch('sys.argv', ['supervise_bridge.py', '--realtime', '--prepare']), \
                patch.object(supervise_bridge.shutil, 'which', return_value='adb'), \
                patch.object(supervise_bridge, 'board_connected', return_value=True), \
                patch.object(supervise_bridge, 'supervise_with_retry', side_effect=capture):
            self.assertEqual(supervise_bridge.main(), 0)
        self.assertTrue(any(item.endswith('offline_demo.py') for item in seen))
        self.assertNotIn('--start-xinyu', seen)


if __name__ == '__main__':
    unittest.main()
