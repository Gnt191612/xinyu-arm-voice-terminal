"""校验命令行下载的中文模型ZIP并解压，不覆盖已有模型。"""
import hashlib
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'models'
archive = root / 'vosk-model-small-cn-0.22.zip'
target = root / 'vosk-model-small-cn-0.22'
size = archive.stat().st_size
if not 35_000_000 <= size <= 55_000_000:
    raise SystemExit(f'文件大小异常：{size}字节，官方标注约42MB')
if target.exists():
    raise SystemExit('模型目录已存在，停止解压以避免覆盖')
with zipfile.ZipFile(archive) as source:
    bad = source.testzip()
    if bad:
        raise SystemExit('ZIP CRC校验失败：' + bad)
    for member in source.infolist():
        resolved = (root / member.filename).resolve()
        if not resolved.is_relative_to(root.resolve()) or not member.filename.startswith('vosk-model-small-cn-0.22/'):
            raise SystemExit('ZIP含不安全或不符预期的路径')
    source.extractall(root)
manifest = {'url': 'https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip',
    'size': size, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'zip_crc': '通过', 'directory': str(target.resolve()),
    'note': 'SHA256是本次下载指纹，非与官方签名或官方SHA交叉验证'}
(root / 'download_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(manifest, ensure_ascii=False, indent=2))
