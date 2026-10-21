"""音色切换不能破坏可打断播放和AEC使用的音频格式。"""
import array
from pathlib import Path
import tempfile
import unittest
import wave
from tts_audio import normalize_tts_wave


class TtsAudioTests(unittest.TestCase):
    def make_wave(self, path, channels, rate, width=2):
        with wave.open(str(path), 'wb') as audio:
            audio.setparams((channels, width, rate, 0, 'NONE', 'not compressed'))
            audio.writeframes(array.array('h', [1000] * (rate * channels)).tobytes())

    def test_existing_player_format_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'voice.wav'
            self.make_wave(path, 1, 16000)
            original = path.read_bytes()
            normalize_tts_wave(path)
            self.assertEqual(path.read_bytes(), original)

    def test_modern_voice_is_converted_without_duration_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'voice.wav'
            self.make_wave(path, 2, 24000)
            normalize_tts_wave(path)
            with wave.open(str(path), 'rb') as audio:
                self.assertEqual(audio.getparams()[:3], (1, 2, 16000))
                self.assertAlmostEqual(audio.getnframes() / 16000, 1, places=3)

    def test_unsupported_format_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'voice.wav'
            self.make_wave(path, 1, 16000, width=1)
            with self.assertRaises(ValueError):
                normalize_tts_wave(path)
