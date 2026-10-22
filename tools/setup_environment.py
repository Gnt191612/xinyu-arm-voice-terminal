"""准备电脑端隔离依赖和公开模型；不连接开发板，不启动心语，不覆盖配置。"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17'
MODEL_SHA = '7d1efa2138a65b0b488df37f8b89e3d91a60676e416f515b952358d83dfd347e'
SPEEX_SHA = '8c777343e4a6399569c72abc38a95b24db56882c83dbdb6c6424a5f4aeb54d3d'


def run(command):
    subprocess.run([str(arg) for arg in command], check=True, cwd=ROOT)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fetch(url, path, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or sha(path) != expected:
        partial = path.with_name(path.name + '.partial')
        run(['curl.exe', '--fail', '--location', '--noproxy', '*', '--connect-timeout', '20',
             '--max-time', '900', '--output', partial, url])
        if not partial.stat().st_size or sha(partial) != expected:
            raise RuntimeError('下载摘要不符，未使用文件：' + str(partial))
        partial.replace(path)


def unpack(archive, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as package:
        for member in package.getmembers():
            if not (destination / member.name).resolve().is_relative_to(destination.resolve()):
                raise RuntimeError('归档路径越界')
            if not (member.isfile() or member.isdir()):
                raise RuntimeError('拒绝归档链接或特殊文件')
        package.extractall(destination)


def check():
    for folder in ('.deps', '.realtime-deps', '.asr-deps'):
        sys.path.insert(0, str(ROOT / folder))
    missing = [name for name in ('numpy', 'sounddevice', 'webrtcvad', 'sherpa_onnx', 'vosk')
               if importlib.util.find_spec(name) is None]
    for name in ('.realtime-build/aec_pipe.exe', 'config.json',
                 'models/' + MODEL + '/model.int8.onnx', 'models/' + MODEL + '/tokens.txt',
                 '.asr-deps/sherpa_onnx/__init__.py'):
        if not (ROOT / name).is_file():
            missing.append(name)
    print(json.dumps({'电脑文件检查通过': not missing, '缺失': missing,
                      '边界': '不验证板端、音箱、音色、心语服务或真人交互'}, ensure_ascii=False))
    return bool(missing)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='只读检查，不安装不下载')
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 11) or sys.maxsize <= 2 ** 32:
        raise RuntimeError('请使用64位Python 3.11，不支持直接改用3.13以上版本')
    if args.check:
        return int(check())
    if os.name != 'nt':
        raise RuntimeError('正式电脑入口需要Windows；板端是另一套ARM Linux环境')
    run([sys.executable, '-m', 'pip', 'install', '--target', ROOT / '.deps',
         '--no-compile', '-r', ROOT / 'requirements.txt'])
    run([sys.executable, '-m', 'pip', 'install', '--target', ROOT / '.realtime-deps',
         '--no-compile', 'numpy==2.3.5', 'sounddevice==0.5.6', 'webrtcvad-wheels==2.0.14.post1'])
    run([sys.executable, '-m', 'pip', 'install', '--target', ROOT / '.asr-deps',
         '--no-compile', 'sherpa-onnx==1.13.8'])
    if not (ROOT / 'models' / MODEL / 'model.int8.onnx').is_file():
        archive = ROOT / '.asr-downloads' / (MODEL + '.tar.bz2')
        fetch('https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/' + archive.name,
              archive, MODEL_SHA)
        unpack(archive, ROOT / 'models')
    source = ROOT / '.realtime-build/speexdsp-1.2.1'
    archive = ROOT / '.realtime-build/speexdsp-1.2.1.tar.gz'
    if not source.is_dir():
        fetch('https://downloads.xiph.org/releases/speex/speexdsp-1.2.1.tar.gz', archive, SPEEX_SHA)
        unpack(archive, archive.parent)
    run([sys.executable, ROOT / 'tools/build_aec.py'])
    if not (ROOT / 'config.json').exists():
        run([sys.executable, ROOT / 'tools/init_config.py'])
    print('电脑端资源准备完成。还需按复现指南配置板端、中文音色和独立心语服务。')
    return int(check())


if __name__ == '__main__':
    raise SystemExit(main())
