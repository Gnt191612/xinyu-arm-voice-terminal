"""只读检查电脑部署条件，不启动模型、不合成或播放、不打印令牌。"""
import importlib.util
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_pc(root=ROOT):
    report = {'checks': {}, 'errors': [],
              'scope': '电脑部署预检；不代表模型权重、实际对话、RNDIS或音箱实测通过'}
    checks = report['checks']
    try:
        config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        report['errors'].append('无法读取本地配置：' + str(exc))
        report['passed'] = False
        return report
    token = config.get('token', '')
    checks['token_valid'] = isinstance(token, str) and len(token) >= 24 and token.isascii()
    checks['playback_target'] = config.get('playback_target', 'pc')
    checks['listen_host'] = config.get('listen_host')
    checks['board_can_reach_loopback_binding'] = False
    checks['vosk_installed'] = importlib.util.find_spec('vosk') is not None
    checks['windows_playback_available'] = os.name == 'nt' and importlib.util.find_spec('winsound') is not None
    checks['powershell_available'] = shutil.which('powershell.exe') is not None
    model = Path(config.get('vosk_model', 'models/vosk-model-small-cn-0.22'))
    if not model.is_absolute():
        model = root / model
    checks['vosk_model_files'] = all((model / name).is_file() for name in ('am/final.mdl', 'conf/model.conf'))
    checks['tts_script_exists'] = (root / 'tts.ps1').is_file()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(config['xinyu_url'].rstrip('/') + '/health', timeout=5) as response:
            health = json.load(response)
        checks['xinyu_health_reachable'] = isinstance(health, dict)
    except (OSError, ValueError, KeyError):
        checks['xinyu_health_reachable'] = False
    for name in ('token_valid', 'vosk_installed', 'windows_playback_available',
                 'powershell_available', 'vosk_model_files', 'tts_script_exists', 'xinyu_health_reachable'):
        if not checks[name]:
            report['errors'].append('未通过：' + name)
    report['warnings'] = ['尚未检查Windows中文声音与默认输出设备，实际出声需单独验证。',
                          '绑定127.0.0.1仅供本机；RNDIS就绪后需绑定实际专网地址，当前不自动改配置。']
    report['passed'] = not report['errors']
    return report


if __name__ == '__main__':
    result = check_pc()
    output = ROOT / 'records/电脑部署预检'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['passed'] else 1)
