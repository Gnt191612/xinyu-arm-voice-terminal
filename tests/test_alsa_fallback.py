"""缺少proc接口时的ALSA枚举回归；不依赖真实声卡。"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from board_audio import list_alsa_devices


class AlsaFallbackTests(unittest.TestCase):
    def test_capture_only_device(self):
        with patch('board_audio.shutil.which', side_effect=lambda name: '/usr/bin/arecord' if name == 'arecord' else None), patch('board_audio.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='card 2: Mic [USB Mic], device 0: USB Audio [USB Audio]')):
            devices = list_alsa_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]['endpoint'], 'plughw:CARD=Mic,DEV=0')
        self.assertTrue(devices[0]['capture'])
        self.assertFalse(devices[0]['playback'])
        self.assertIsNone(devices[0]['usb_id'])

    def test_failed_command_does_not_invent_devices(self):
        with patch('board_audio.shutil.which', return_value='/usr/bin/tool'), patch('board_audio.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='no soundcards found')):
            self.assertEqual(list_alsa_devices(), [])
