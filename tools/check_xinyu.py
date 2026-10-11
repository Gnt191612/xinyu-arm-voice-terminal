"""仅检查已有心语服务，不启动旧模型、不改配置。"""
import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
out = root / 'records/心语服务检查'
out.mkdir(parents=True, exist_ok=True)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    with opener.open(config['xinyu_url'].rstrip('/') + '/health', timeout=3) as response:
        health = json.load(response)
    result = {'reachable': True, 'health': health,
        'note': '健康接口只反映服务声明，不能代替权重SHA核验或完整对话测试'}
except OSError as exc:
    result = {'reachable': False, 'error': str(exc),
        'note': '本轮未启动心语服务，不能宣称真实模型联调成功'}
(out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
