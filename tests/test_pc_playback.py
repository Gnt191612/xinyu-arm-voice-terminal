"""无HUB电脑播放模式的离线验证；不实际播放声音。"""
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from board_client import check_audio_tools
from pc_server import Pipeline, test_tone


class PcPlaybackTests(unittest.TestCase):
    def test_capture_only(self):
        with patch('board_client.shutil.which', side_effect=lambda name: '/usr/bin/arecord' if name == 'arecord' else None):
            check_audio_tools('plughw:CARD=Mic,DEV=0', None, 'pc')
            with self.assertRaises(ValueError):
                check_audio_tools('plughw:CARD=Mic,DEV=0', None, 'board')

    def test_simulated_pc_does_not_play_or_return_audio(self):
        with tempfile.TemporaryDirectory() as directory, patch('pc_server.play_on_pc') as play:
            pipeline = Pipeline({'threshold': 500}, simulate=True)
            pipeline.records = Path(directory)
            result = pipeline.process({'audio_wav': base64.b64encode(test_tone()).decode('ascii')})
            self.assertEqual(result['playback_target'], 'pc')
            self.assertNotIn('audio_wav', result)
            self.assertFalse(result['playback_command_completed'])
            play.assert_not_called()

    def test_windows_player_uses_file_synchronously(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import Mock
        from pc_server import play_on_pc
        sound = SimpleNamespace(PlaySound=Mock(), SND_FILENAME=131072)
        with patch.dict(sys.modules, winsound=sound):
            play_on_pc(Path('reply.wav'))
        sound.PlaySound.assert_called_once_with('reply.wav', sound.SND_FILENAME)

    def test_invalid_target(self):
        with self.assertRaises(ValueError):
            Pipeline({'threshold': 500, 'playback_target': 'invalid'}, simulate=True)
