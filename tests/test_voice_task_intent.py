"""语音明确任务与倾诉、否定和引用的边界。"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('voice_task_intent',
    ROOT / 'integration/task_intent.py')
intent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intent)


class VoiceTaskIntentTests(unittest.TestCase):
    def requested(self, text):
        return intent.assistant_task_requested([{'role': 'user', 'content': text}])

    def test_explicit_delegation(self):
        for text in ('不要讲故事了，帮我想一个早餐。', '你帮我想一个早餐。', '给我推荐一本书', '帮我规划明天的安排'):
            self.assertTrue(self.requested(text), text)

    def test_complaint_and_negation_keep_companion_mode(self):
        for text in ('我今天很累', '不要给我建议', '帮我想个早餐，不过我现在只想倾诉', '不用帮我想，我自己来'):
            self.assertFalse(self.requested(text), text)

    def test_quote_and_reverse_roles_are_not_tasks(self):
        for text in ('解释这句话“帮我推荐一本书”', '我帮你想一个早餐', '听我讲个故事'):
            self.assertFalse(self.requested(text), text)
