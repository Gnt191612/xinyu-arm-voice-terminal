"""隔离准备公开离线识别资源；下载、解包和测试均受断板守护。"""
import bz2
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from realtime_session import find_adb
from supervise_bridge import board_connected, supervise


def run(command, timeout=180):
    subprocess.run(command, check=True, timeout=timeout,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def prepare():
    downloads = ROOT / '.asr-downloads'
    downloads.mkdir(exist_ok=True)
    metadata = downloads / 'release.json'
    run(['curl.exe', '-fL', '--noproxy', '*', '--connect-timeout', '15',
         '-o', str(metadata), 'https://api.github.com/repos/k2-fsa/sherpa-onnx/releases/tags/asr-models'], 60)
    name = 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17.tar.bz2'
    asset = next(item for item in json.loads(metadata.read_text(encoding='utf-8'))['assets'] if item['name'] == name)
    archive = downloads / name
    if not archive.exists() or archive.stat().st_size != asset['size']:
        run(['curl.exe', '-fL', '--noproxy', '*', '--connect-timeout', '15',
             '-o', str(archive), asset['browser_download_url']], 180)
    if archive.stat().st_size != asset['size']:
        raise RuntimeError('模型归档大小与官方发布元数据不符')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if asset.get('digest') and asset['digest'] != 'sha256:' + digest:
        raise RuntimeError('模型归档摘要与官方发布元数据不符')
    with bz2.open(archive, 'rb') as stream:
        while stream.read(1024 * 1024):
            pass
    destination = ROOT / 'models'
    with tarfile.open(archive, 'r:bz2') as package:
        for member in package.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()) or member.issym() or member.islnk():
                raise RuntimeError('归档包含越界路径或链接，停止解包')
        package.extractall(destination)
    wheels = downloads / 'wheels'
    wheels.mkdir(exist_ok=True)
    run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '-d', str(wheels), 'sherpa-onnx'])
    for path in wheels.glob('*.whl'):
        with zipfile.ZipFile(path) as package:
            if package.testzip():
                raise RuntimeError('依赖wheel完整性校验失败')
    run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(wheels),
         '--target', str(ROOT / '.asr-deps'), '--no-compile', 'sherpa-onnx'])
    record = {'模型归档': str(archive), '字节数': archive.stat().st_size,
              '官方大小一致': True, 'SHA256': digest, '压缩完整性': True,
              '目录': str(destination / name[:-8]), '依赖目录': str(ROOT / '.asr-deps'),
              '边界': '仅准备公开文件；不代表实际识别质量已通过'}
    (ROOT / 'records/实时交互/离线识别资源.json').write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if '--child' in sys.argv:
        prepare()
    else:
        adb = find_adb()
        if not board_connected(adb, '20080411'):
            raise SystemExit('开发板未连接，不启动准备任务')
        child = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()), '--child'],
            stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), start_new_session=os.name != 'nt')
        raise SystemExit(supervise(child, lambda: board_connected(adb, '20080411')))
