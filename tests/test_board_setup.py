"""板端部署检查的离线测试；模拟路径不等于实机验证。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board_client import check_audio_tools
from tools.check_board import check_board


class BoardSetupTests(unittest.TestCase):
    def test_inventory_does_not_load_assembly(self):
        with patch('tools.check_board.platform.machine', return_value='armv7l'), \
             patch('tools.check_board.platform.system', return_value='Linux'), \
             patch('tools.check_board.struct.calcsize', return_value=4), \
             patch('tools.check_board.Path.is_file', return_value=True), \
             patch('tools.check_board.Path.read_text', return_value='capture 1 playback 1'), \
             patch('tools.check_board.shutil.which', return_value='/usr/bin/tool'), \
             patch('tools.check_board.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='设备列表')), \
             patch('audio_core.Gate') as gate:
            result = check_board(Path('not-built.so'), inventory_only=True)
        self.assertTrue(result['passed'])
        self.assertFalse(result['assembly_checked'])
        self.assertFalse(result['hardware_audio_verified'])
        gate.assert_not_called()

    def test_full_check_loads_and_checks_assembly(self):
        with patch('tools.check_board.platform.machine', return_value='armv7l'), \
             patch('tools.check_board.platform.system', return_value='Linux'), \
             patch('tools.check_board.struct.calcsize', return_value=4), \
             patch('tools.check_board.Path.is_file', return_value=True), \
             patch('tools.check_board.Path.read_text', return_value='capture 1 playback 1'), \
             patch('tools.check_board.shutil.which', return_value='/usr/bin/tool'), \
             patch('tools.check_board.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='设备列表')), \
             patch('audio_core.Gate') as gate:
            gate.return_value.frame.side_effect = [(65536, True), (0, False)]
            result = check_board(Path('test-only.so'))
        self.assertTrue(result['passed'])
        self.assertTrue(result['assembly_checked'])
        self.assertFalse(result['hardware_audio_verified'])
        self.assertEqual(gate.return_value.frame.call_count, 2)

    def test_reject_64bit_python_on_arm(self):
        with patch('tools.check_board.platform.machine', return_value='armv7l'), \
             patch('tools.check_board.platform.system', return_value='Linux'), \
             patch('tools.check_board.struct.calcsize', return_value=8), \
             patch('tools.check_board.Path.is_file', return_value=False), \
             patch('tools.check_board.shutil.which', return_value=None):
            result = check_board(Path('missing.so'))
        self.assertFalse(result['passed'])
        self.assertFalse(result['assembly_checked'])

    def test_require_explicit_devices(self):
        with self.assertRaisesRegex(ValueError, '显式指定'):
            check_audio_tools(None, 'default')

    def test_missing_alsa_tools(self):
        with patch('board_client.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'alsa-utils'):
                check_audio_tools('plughw:CARD=Mic,DEV=0', 'plughw:CARD=Codec,DEV=0')

    def test_explicit_devices_with_tools(self):
        with patch('board_client.shutil.which', return_value='/usr/bin/tool'):
            check_audio_tools('plughw:CARD=Mic,DEV=0', 'plughw:CARD=Codec,DEV=0')

    def test_pc_cannot_pass_as_board(self):
        with patch('tools.check_board.platform.machine', return_value='x86_64'), \
             patch('tools.check_board.platform.system', return_value='Linux'), \
             patch('tools.check_board.Path.is_file', return_value=False), \
             patch('tools.check_board.shutil.which', return_value=None):
            result = check_board(Path('missing.so'))
        self.assertFalse(result['passed'])
        self.assertTrue(any('32位ARM' in item for item in result['errors']))
        self.assertNotIn('assembly', result)
