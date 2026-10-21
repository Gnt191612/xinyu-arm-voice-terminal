"""实时任务门控保持静音和削波保护，不重新套用旧音量门限。"""
import array
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.realtime-deps'))
from voice_activity import analyze_realtime_audio


class RealtimeVoiceGateTests(unittest.TestCase):
    def test_confirmed_endpoint_does_not_reset_vad_state(self):
        with patch('voice_activity.VoiceActivityDetector.detect', return_value=False) as detect:
            result = analyze_realtime_audio(array.array('h', [100] * 960), endpoint_confirmed=True)
            self.assertTrue(result['accepted'])
            detect.assert_not_called()

    def test_confirmed_endpoint_still_rejects_clipping_and_short_audio(self):
        for samples in ([32767] * 960, [100] * 320):
            self.assertFalse(analyze_realtime_audio(array.array('h', samples), endpoint_confirmed=True)['accepted'])

    def test_silence_is_rejected(self):
        self.assertFalse(analyze_realtime_audio(array.array('h', [0] * 16000))['accepted'])

    @patch('voice_activity.VoiceActivityDetector.detect', return_value=True)
    def test_classified_low_volume_speech_is_not_rejected_by_old_threshold(self, detect):
        result = analyze_realtime_audio(array.array('h', [100] * 960))
        self.assertTrue(result['accepted'])
        self.assertEqual(result['longest_active_frames'], 3)

    @patch('voice_activity.VoiceActivityDetector.detect', return_value=True)
    def test_clipping_protection_is_preserved(self, detect):
        result = analyze_realtime_audio(array.array('h', [32767] * 960))
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], '削波超过20%')
