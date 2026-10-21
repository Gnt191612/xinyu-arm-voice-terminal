"""实际播放参考缓冲、可打断外放与SpeexDSP进程接口。"""
from collections import deque
import io
import subprocess
import threading
import time
import wave


class RenderReference:
    def __init__(self):
        self.blocks = deque(maxlen=150)
        self.lock = threading.Lock()

    def append(self, timestamp, pcm):
        with self.lock:
            self.blocks.append((timestamp, pcm))

    def at(self, timestamp):
        result = bytearray(640)
        with self.lock:
            blocks = list(self.blocks)
        for start, pcm in blocks:
            offset = round((start - timestamp) * 16000)
            first = max(0, offset)
            end = min(320, offset + len(pcm) // 2)
            if end > first:
                source = first - offset
                result[first * 2:end * 2] = pcm[source * 2:(source + end - first) * 2]
        return bytes(result)


class InterruptiblePlayer:
    def __init__(self, reference, device=None):
        import sounddevice as sd
        self.reference = reference
        self.lock = threading.Lock()
        self.pcm = b''
        self.offset = 0
        self.active = False
        self.stream = sd.RawOutputStream(samplerate=16000, channels=1, dtype='int16',
                                         blocksize=320, latency='low', device=device,
                                         callback=self.callback)
        self.stream.start()

    def callback(self, out, frames, timing, status):
        with self.lock:
            block = self.pcm[self.offset:self.offset + frames * 2]
            self.offset += len(block)
            self.active = self.offset < len(self.pcm)
        block = block.ljust(frames * 2, b'\0')
        out[:] = block
        self.reference.append(time.monotonic() + timing.outputBufferDacTime - timing.currentTime, block)

    def play(self, wav):
        with wave.open(io.BytesIO(wav), 'rb') as source:
            if source.getparams()[:3] != (1, 2, 16000):
                raise ValueError('回复必须为16kHz单声道PCM16')
            pcm = source.readframes(source.getnframes())
        with self.lock:
            self.pcm, self.offset, self.active = pcm, 0, bool(pcm)

    def stop(self):
        with self.lock:
            self.pcm, self.offset, self.active = b'', 0, False

    def close(self):
        self.stop()
        self.stream.abort()
        self.stream.close()


class EchoCanceller:
    def __init__(self, executable, log):
        self.process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=log,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def process_frame(self, microphone, reference):
        if len(microphone) != 640 or len(reference) != 640:
            raise ValueError('AEC每帧必须为320个PCM16采样')
        self.process.stdin.write(microphone + reference)
        self.process.stdin.flush()
        clean = self.process.stdout.read(640)
        if len(clean) != 640:
            raise RuntimeError('AEC进程意外退出')
        return clean

    def close(self):
        from supervise_bridge import stop_owned_process
        stop_owned_process(self.process)
        self.process.stdin.close()
        self.process.stdout.close()
