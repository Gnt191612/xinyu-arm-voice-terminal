"""连续PCM的语句切分；活动判定由真实ARM门控或回声消除后VAD提供。"""
from collections import deque


class SpeechEndpoint:
    def __init__(self, frame_bytes=640, pre_frames=15, start_frames=3,
                 silence_frames=40, max_frames=750):
        if min(frame_bytes, pre_frames, start_frames, silence_frames, max_frames) < 1:
            raise ValueError('分帧参数必须为正数')
        if pre_frames < start_frames or max_frames <= pre_frames + silence_frames:
            raise ValueError('预缓冲必须覆盖开口确认，最长句必须容纳预缓冲与句尾')
        self.frame_bytes = frame_bytes
        self.pre = deque(maxlen=pre_frames)
        self.start_frames = start_frames
        self.silence_frames = silence_frames
        self.max_frames = max_frames
        self.frames = None
        self.active_run = 0
        self.quiet_run = 0

    def feed(self, pcm, active):
        """返回(事件, PCM)：开口事件可立即撤销旧回复，结束事件才提交新句。"""
        if len(pcm) != self.frame_bytes:
            raise ValueError('必须输入完整的固定长度PCM帧')
        if self.frames is None:
            self.pre.append(pcm)
            self.active_run = self.active_run + 1 if active else 0
            if self.active_run >= self.start_frames:
                self.frames = list(self.pre)
                self.pre.clear()
                self.quiet_run = 0
                return '开口', None
            return None, None
        self.frames.append(pcm)
        self.quiet_run = 0 if active else self.quiet_run + 1
        if self.quiet_run >= self.silence_frames or len(self.frames) >= self.max_frames:
            audio = b''.join(self.frames)
            self.frames = None
            self.active_run = 0
            self.quiet_run = 0
            return '结束', audio
        return None, None
