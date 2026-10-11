"""仅首次创建本地配置，保留现有配置与访问令牌。"""
import json
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'config.json'
if target.exists():
    raise SystemExit('config.json已存在，不覆盖')
config = json.loads((root / 'config.example.json').read_text(encoding='utf-8'))
config['token'] = secrets.token_hex(32)
target.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
print('已创建本地随机令牌配置；令牌未打印。默认仅监听127.0.0.1。')
