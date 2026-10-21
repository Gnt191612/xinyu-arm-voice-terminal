"""本地识别后端接入及空语义保护，不加载真实模型。"""
import base64
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import pc_server


class LocalAsrPipelineTests(unittest.TestCase):
    def request(self):
        data = io.BytesIO()
        with wave.open(data, 'wb') as audio:
            audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            audio.writeframes(b'\xe8\x03' * 960)
        return {'audio_wav': base64.b64encode(data.getvalue()).decode(), 'history': []}

    def test_punctuation_only_never_reaches_model(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(pc_server, 'ROOT', Path(directory)), \
             patch.object(pc_server, 'json_post') as post:
            pipeline = pc_server.Pipeline({'threshold': 500}, transcriber=lambda pcm: '。！？')
            with self.assertRaisesRegex(ValueError, '没有识别到文字'):
                pipeline.process(self.request())
            post.assert_not_called()

    def test_offline_transcript_reaches_model_unchanged(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(pc_server, 'ROOT', Path(directory)), \
             patch.object(pc_server, 'json_post', return_value={'response_text': ''}) as post:
            pipeline = pc_server.Pipeline({'threshold': 500, 'xinyu_url': 'http://127.0.0.1'},
                                          transcriber=lambda pcm: '请讲一个睡前故事。')
            with self.assertRaisesRegex(ValueError, '心语未返回'):
                pipeline.process(self.request())
            self.assertEqual(post.call_args.args[1]['history'][-1]['content'], '请讲一个睡前故事。')
