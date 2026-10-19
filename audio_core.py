"""PCM校验与声音门控；开发板必须显式加载真实ARM模块。"""
import array
import ctypes
import io
import sys
import wave

RATE = 16000
FRAME = 320
MAX_SECONDS = 15


def read_wav(data, max_seconds=MAX_SECONDS):
    try:
        with wave.open(io.BytesIO(data), 'rb') as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, RATE, 'NONE'):
                raise ValueError('音频必须是16000Hz、单声道、16位未压缩PCM WAV')
            count = source.getnframes()
            if not 0 < count <= RATE * max_seconds:
                raise ValueError('音频长度必须大于0且不超过{}秒'.format(max_seconds))
            pcm = source.readframes(count)
            if len(pcm) != count * 2:
                raise ValueError('WAV数据被截断')
    except (wave.Error, EOFError) as exc:
        raise ValueError('无效WAV文件') from exc
    samples = array.array('h')
    samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    return samples, pcm


class Gate:
    def __init__(self, library=None, threshold=500):
        if not 0 <= threshold <= 32768:
            raise ValueError('门限必须在0至32768之间')
        self.threshold = threshold
        self.library = ctypes.CDLL(str(library)) if library else None
        self.backend = 'ARM汇编动态库' if library else 'Python参考实现 非实机汇编'
        if self.library:
            self.library.pcm_sum_abs_arm.argtypes = [ctypes.POINTER(ctypes.c_int16), ctypes.c_uint32]
            self.library.pcm_sum_abs_arm.restype = ctypes.c_uint32
            self.library.pcm_gate_arm.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
            self.library.pcm_gate_arm.restype = ctypes.c_uint32

    def frame(self, samples):
        n = len(samples)
        if n > 65535 or any(not -32768 <= x <= 32767 for x in samples):
            raise ValueError('帧长度或PCM16样本超出接口范围')
        if self.library:
            block = (ctypes.c_int16 * n)(*samples)
            total = self.library.pcm_sum_abs_arm(block, n)
            active = bool(self.library.pcm_gate_arm(total, n, self.threshold))
        else:
            total = sum(abs(x) for x in samples)
            active = bool(n and total >= n * self.threshold)
        return total, active

    def analyze(self, samples):
        frames = []
        run = longest = 0
        for offset in range(0, len(samples), FRAME):
            total, active = self.frame(samples[offset:offset + FRAME])
            frames.append({'offset': offset, 'count': len(samples[offset:offset + FRAME]), 'sum_abs': total, 'active': active})
            run = run + 1 if active else 0
            longest = max(longest, run)
        clipping = sum(x in (-32768, 32767) for x in samples) / len(samples) if samples else 0
        accepted = longest >= 3 and clipping <= 0.2
        return {'backend': self.backend, 'threshold': self.threshold, 'frames': frames,
                'longest_active_frames': longest, 'clipping_ratio': clipping, 'accepted': accepted,
                'reason': '削波超过20%' if clipping > 0.2 else ('存在连续声音帧' if accepted else '不足3个连续声音帧')}
