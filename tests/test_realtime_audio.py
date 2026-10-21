"""AEC播放参考和打断缓冲测试，不打开真实音箱。"""
import array
import io
import threading
from types import SimpleNamespace
import unittest
import wave
from unittest.mock import patch
from realtime_audio import RenderReference, InterruptiblePlayer


class AudioTests(unittest.TestCase):
    def test_reference_alignment_and_missing_reference(self):
        reference = RenderReference()
        pcm = array.array('h', range(320)).tobytes()
        reference.append(10.0, pcm)
        self.assertEqual(reference.at(10.0), pcm)
        shifted = array.array('h', reference.at(10.01))
        self.assertEqual(list(shifted[:160]), list(range(160, 320)))
        self.assertEqual(list(shifted[160:]), [0] * 160)
        self.assertEqual(reference.at(20), b'\0' * 640)

    def test_reference_storage_is_bounded(self):
        reference = RenderReference()
        for i in range(1000):
            reference.append(i * 0.02, b'\0' * 640)
        self.assertEqual(len(reference.blocks), 150)

    def test_interrupt_next_callback_is_silent_and_reference_is_real_output(self):
        player = object.__new__(InterruptiblePlayer)
        player.reference = RenderReference()
        player.lock = threading.Lock()
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as target:
            target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            target.writeframes(b'\x01\x00' * 960)
        player.play(buffer.getvalue())
        out = bytearray(640)
        timing = SimpleNamespace(outputBufferDacTime=1, currentTime=1)
        with patch('realtime_audio.time.monotonic', return_value=10):
            player.callback(out, 320, timing, None)
        self.assertEqual(out, b'\x01\x00' * 320)
        self.assertEqual(player.reference.at(10), out)
        player.stop()
        self.assertFalse(player.active)
        player.callback(out, 320, timing, None)
        self.assertEqual(out, b'\0' * 640)
