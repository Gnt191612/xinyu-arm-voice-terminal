"""AEC后的人声活动分类，不将音量等同于语音。"""
import array
from audio_core import Gate


def analyze_realtime_audio(samples, endpoint_confirmed=False):
    """实时任务再次使用同一人声分类，保留削波检查，不接受请求端自称已通过。"""
    result = Gate(threshold=50).analyze(samples)
    if endpoint_confirmed:
        # 接续主会话的有状态人声判定，不用新建VAD状态重新否决同一片段。
        result['accepted'] = len(samples) >= 960 and result['clipping_ratio'] <= 0.2
        result['endpoint_confirmed'] = True
        result['reason'] = ('削波超过20%' if result['clipping_ratio'] > 0.2 else
                            ('实时端点已确认连续人声' if result['accepted'] else '音频不足连续3帧'))
        return result
    detector = VoiceActivityDetector()
    run = longest = 0
    for frame in result['frames']:
        part = samples[frame['offset']:frame['offset'] + frame['count']]
        active = len(part) == 320 and detector.detect(part.tobytes())
        frame['active'] = active
        run = run + 1 if active else 0
        longest = max(longest, run)
    result['longest_active_frames'] = longest
    result['accepted'] = longest >= 3 and result['clipping_ratio'] <= 0.2
    result['reason'] = ('削波超过20%' if result['clipping_ratio'] > 0.2 else
                        ('存在连续人声帧' if result['accepted'] else '不足3个连续人声帧'))
    result['classifier'] = 'WebRTC VAD模式3，与实时分句一致'
    return result


class VoiceActivityDetector:
    def __init__(self, mode=3):
        import webrtcvad
        self.detector = webrtcvad.Vad(mode)

    def detect(self, pcm):
        if len(pcm) != 640:
            raise ValueError('人声检测需要20毫秒PCM16帧')
        samples = array.array('h', pcm)
        # 排除近零数值，不能替代WebRTC语音分类。
        return sum(abs(x) for x in samples) >= 320 * 50 and self.detector.is_speech(pcm, 16000)
