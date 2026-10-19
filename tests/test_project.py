"""离线模拟测试，不把固定文本或测试音当成真实识别与模型输出。"""
import base64
import io
import json
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from audio_core import Gate, read_wav
from pc_server import Pipeline, make_handler, validate_history


def wav_bytes(samples, rate=16000, channels=1):
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        target.setparams((channels, 2, rate, 0, 'NONE', 'not compressed'))
        target.writeframes(struct.pack('<' + 'h' * len(samples), *samples))
    return output.getvalue()


class Tests(unittest.TestCase):
    def test_pcm_minimum(self):
        self.assertEqual(Gate().frame([-32768, 32767, 0, -1])[0], 65536)

    def test_empty_frame(self):
        self.assertEqual(Gate().frame([]), (0, False))

    def test_exact_threshold(self):
        self.assertEqual(Gate().frame([500, -500]), (1000, True))

    def test_below_threshold(self):
        self.assertEqual(Gate().frame([499, -499]), (998, False))

    def test_silence(self):
        self.assertFalse(Gate().analyze([0] * 1600)['accepted'])

    def test_clipping_interference(self):
        self.assertEqual(Gate().analyze([32767, -32768] * 800)['reason'], '削波超过20%')

    def test_isolated_impulse(self):
        self.assertFalse(Gate().analyze([3000] * 320 + [0] * 1280)['accepted'])

    def test_normal_activity(self):
        self.assertTrue(Gate().analyze([1000, -1000] * 800)['accepted'])

    def test_noise_limitation(self):
        # 连续强噪声也会通过，显式保留这个局限而非隐瞒。
        self.assertTrue(Gate().analyze([900, -900] * 800)['accepted'])

    def test_wav_roundtrip(self):
        samples, pcm = read_wav(wav_bytes([-32768, 100, -100]))
        self.assertEqual(list(samples), [-32768, 100, -100])
        self.assertEqual(len(pcm), 6)

    def test_invalid_wav(self):
        for data in (b'not wav', wav_bytes([1] * 10, 8000), wav_bytes([]), wav_bytes([1] * 10)[:-2]):
            with self.assertRaises(ValueError):
                read_wav(data)

    def test_invalid_history(self):
        for history in (None, [{'role': 'user', 'content': '不完整'}], [{'role': 'system', 'content': 'x'}] * 2, [] * 0 + [{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': 'y'}] * 20):
            with self.assertRaises(ValueError):
                validate_history(history)
        validate_history([{'role': 'user', 'content': 'x'}, {'role': 'assistant', 'content': 'y'}] * 19)

    def test_interface_limits(self):
        for samples in ([32768], [0] * 65536):
            with self.assertRaises(ValueError):
                Gate().frame(samples)
        with self.assertRaises(ValueError):
            Gate(threshold=-1)

    def test_http_flow(self):
        config = {'threshold': 500}
        pipeline = Pipeline(dict(config, playback_target='board'), simulate=True)
        with tempfile.TemporaryDirectory() as temp:
            pipeline.records = Path(temp)
            token = 'test-only-token-01234567890123456789'
            server = HTTPServer(('127.0.0.1', 0), make_handler(pipeline, token))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            address = f'http://127.0.0.1:{server.server_port}/turn'
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def request(payload, correct=True):
                req = urllib.request.Request(address, json.dumps(payload).encode(),
                    {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (token if correct else 'wrong')})
                return opener.open(req, timeout=5)

            try:
                wav = wav_bytes([1000, -1000] * 1600)
                payload = {'audio_wav': base64.b64encode(wav).decode(), 'history': []}
                with request(payload) as response:
                    result = json.load(response)
                self.assertIn('模拟', result['mode'])
                read_wav(base64.b64decode(result['audio_wav']))
                self.assertTrue((Path(temp) / result['id'] / 'result.json').is_file())
                for payload, correct, status in ((payload, False, 401), ({'audio_wav': '!!'}, True, 400), ([], True, 400)):
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        request(payload, correct)
                    self.assertEqual(caught.exception.code, status)
                silence = {'audio_wav': base64.b64encode(wav_bytes([0] * 1600)).decode(), 'history': []}
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    request(silence)
                self.assertEqual(caught.exception.code, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
