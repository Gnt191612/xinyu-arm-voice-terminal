"""验证板端源文件不依赖Python3.6语法；不等同于ARM实机运行。"""
import ast
import unittest
from pathlib import Path


class Python35Tests(unittest.TestCase):
    def test_board_sources_parse(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('audio_core.py', 'board_audio.py', 'board_client.py', 'board_stream.py',
                     'tools/check_board.py', 'tools/board_prepare.py', 'tools/rndis_trial.py'):
            with self.subTest(name=name):
                ast.parse((root / name).read_text(encoding='utf-8'), feature_version=(3, 5))
