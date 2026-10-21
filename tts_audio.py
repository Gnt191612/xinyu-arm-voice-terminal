"""将本机音色输出统一为可打断播放器及AEC所需的16kHz单声道PCM16。"""
import audioop
import io
import wave


def normalize_tts_wave(path):
    with wave.open(str(path), 'rb') as source:
        channels, width, rate = source.getparams()[:3]
        if source.getcomptype() != 'NONE' or width != 2 or channels not in (1, 2):
            raise ValueError('本机音色必须输出单/双声道PCM16 WAV')
        if (channels, width, rate) == (1, 2, 16000):
            return
        pcm = source.readframes(source.getnframes())
    if channels == 2:
        pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
    if rate != 16000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        target.writeframes(pcm)
    path.write_bytes(output.getvalue())
