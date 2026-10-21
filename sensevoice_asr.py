"""可选的本地中文识别后端，不联网、不改心语模型。"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


class SenseVoice:
    def __init__(self):
        sys.path.insert(0, str(ROOT / '.asr-deps'))
        sys.path.append(str(ROOT / '.deps'))
        import sherpa_onnx
        model = ROOT / 'models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17'
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model / 'model.int8.onnx'), tokens=str(model / 'tokens.txt'),
            num_threads=2, provider='cpu', language='zh', use_itn=True)

    def __call__(self, pcm):
        import numpy as np
        stream = self.recognizer.create_stream()
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768
        stream.accept_waveform(16000, samples)
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()
