"""USB麦克风与USB声卡分离枚举的离线回归，不表示实机兼容通过。"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board_audio import list_audio_devices
from board_client import main


class AudioDeviceTests(unittest.TestCase):
    def test_separate_usb_devices_and_card_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pcm').write_text(
                '01-00: USB Mic : USB Audio : capture 1\n'
                '02-00: USB Card : USB Audio : playback 1 : capture 1\n')
            for index, identifier in ((1, 'Mic'), (2, 'SoundCard')):
                card = root / ('card' + str(index))
                card.mkdir()
                (card / 'id').write_text(identifier)
                (card / 'usbid').write_text('0000:0000')
            devices = list_audio_devices(root)
        self.assertEqual(devices[0]['endpoint'], 'plughw:CARD=Mic,DEV=0')
        self.assertTrue(devices[0]['capture'])
        self.assertFalse(devices[0]['playback'])
        self.assertEqual(devices[1]['endpoint'], 'plughw:CARD=SoundCard,DEV=0')
        self.assertTrue(devices[1]['capture'])
        self.assertTrue(devices[1]['playback'])
        self.assertEqual(len(devices), 2)

    def test_missing_card_id_is_explicit_numeric_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pcm').write_text('03-01: Codec : playback 1\n')
            device = list_audio_devices(root)[0]
        self.assertEqual(device['endpoint'], 'plughw:3,1')
        self.assertFalse(device['stable_card_id'])
        self.assertIsNone(device['usb_id'])

    def test_no_pcm_returns_empty_not_fake_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(list_audio_devices(Path(directory)), [])

    def test_enumeration_needs_no_server_token_or_arm_library(self):
        output = io.StringIO()
        with patch('sys.argv', ['board_client.py', '--list-audio']), \
             patch('board_client.list_audio_devices', return_value=[]), \
             patch('board_client.Gate') as gate, \
             patch('board_client.send_turn') as send, \
             contextlib.redirect_stdout(output):
            main()
        self.assertEqual(json.loads(output.getvalue())['devices'], [])
        gate.assert_not_called()
        send.assert_not_called()
