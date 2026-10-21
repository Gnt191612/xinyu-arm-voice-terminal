"""候选校验不能吞掉否定、叙述或故事之外的请求。"""
import unittest
from speech_text import select_voice_text


class SpeechTextTests(unittest.TestCase):
    def select(self, *texts):
        return select_voice_text({'alternatives': [{'text': text} for text in texts]})

    def test_recorded_confusion_uses_real_request_candidate(self):
        result = self.select('轻巧 一个 睡前 故事', '倾向 一个 睡前 故事', '请 将 一个 睡前 故事')
        self.assertEqual(result['text'], '请讲一个睡前故事')
        self.assertEqual(result['raw'], '轻巧一个睡前故事')
        self.assertTrue(result['reason'])

    def test_no_request_candidate_means_no_rewrite(self):
        self.assertEqual(self.select('轻巧一个睡前故事')['text'], '轻巧一个睡前故事')

    def test_negation_is_not_overridden(self):
        self.assertEqual(self.select('不要讲一个睡前故事', '请讲一个睡前故事')['text'], '不要讲一个睡前故事')

    def test_listener_and_narration_are_not_overridden(self):
        for text in ('听我讲一个睡前故事', '我写了一个睡前故事', '昨天听一个睡前故事'):
            self.assertEqual(self.select(text, '请讲一个睡前故事')['text'], text)

    def test_analysis_is_not_overridden(self):
        for text in ('分析请讲一个睡前故事是什么意思', '解释一个睡前故事', '推荐一个睡前故事'):
            self.assertEqual(self.select(text, '请讲一个睡前故事')['text'], text)

    def test_story_content_must_match(self):
        self.assertEqual(self.select('轻巧一个睡前故事', '请讲一个冒险故事')['text'], '轻巧一个睡前故事')

    def test_non_story_and_normal_result_are_unchanged(self):
        self.assertEqual(select_voice_text({'text': '我 想 聊聊天'})['text'], '我想聊聊天')

    def test_rewrite_request_is_not_changed_to_storytelling(self):
        text = '请将一个睡前故事改成诗歌'
        self.assertEqual(self.select(text)['text'], text)
