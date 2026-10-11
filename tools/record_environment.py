"""保存实际依赖版本与源代码指纹，便于复现测试。"""
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
packages = {item.metadata['Name']: item.version for item in importlib.metadata.distributions(path=[str(root / '.deps')])}
sources = [*root.glob('*.py'), *root.glob('*.ps1'), *root.glob('*.cmd'),
           *root.glob('arm/*.S'), *root.glob('arm/*.s'), *root.glob('arm/*.c'),
           *root.glob('tests/*.py'), *root.glob('tools/*.py')]
result = {'python': sys.version, 'platform': platform.platform(), 'packages_in_project_deps': packages,
          'source_sha256': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}}
out = root / 'records/环境记录'
out.mkdir(parents=True, exist_ok=True)
(out / 'environment.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print('已保存隔离依赖版本和源代码SHA256，无令牌内容。')
