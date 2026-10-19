"""电脑预检的离线回归，不访问模型或扬声器。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.check_pc import check_pc


class PcPreflightTests(unittest.TestCase):
    def test_missing_config_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = check_pc(Path(directory))
        self.assertFalse(result['passed'])
        self.assertTrue(result['errors'])

    def test_failed_health_and_no_secret_output(self):
        secret = 'test-only-secret-token-0123456789'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config.json').write_text(json.dumps({
                'token': secret, 'xinyu_url': 'http://127.0.0.1:1',
                'vosk_model': 'missing', 'listen_host': '127.0.0.1'}))
            with patch('tools.check_pc.urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = OSError('离线测试')
                result = check_pc(root)
        self.assertFalse(result['passed'])
        self.assertFalse(result['checks']['xinyu_health_reachable'])
        self.assertNotIn(secret, json.dumps(result))
