"""显式向已准备固件与Python的T113部署本项目源码和自编译动态库，不刷固件。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = '/mnt/UDISK/xinyu-arm-check'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True, help='adb devices中确认的目标串号')
    parser.add_argument('--library', type=Path, required=True, help='匹配musl armhf ABI的libpcm_gate.so')
    parser.add_argument('--apply', action='store_true', help='确认部署；默认只检查电脑文件')
    args = parser.parse_args()
    library = args.library.resolve()
    header = library.read_bytes()[:20]
    if len(header) < 20 or header[:6] != b'\x7fELF\x01\x01' or header[18:20] != b'\x28\x00':
        raise RuntimeError('需要32位小端ARM ELF动态库，不能使用Windows或RISC-V产物')
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    token = config['token']
    if not isinstance(token, str) or not token.isascii() or len(token) < 24:
        raise RuntimeError('本地令牌无效')
    adb = shutil.which('adb')
    if not adb:
        raise RuntimeError('请先把官方platform-tools加入PATH')
    def run(*items, **kwargs):
        return subprocess.run([adb, '-s', args.serial, *items], check=True, timeout=15, **kwargs)
    run('get-state')
    files = ('audio_core.py', 'board_audio.py', 'board_stream.py')
    for name in files:
        if not (ROOT / name).is_file():
            raise RuntimeError('源码缺失：' + name)
    if not args.apply:
        print('电脑文件与ADB检查通过。确认固件、Python3.5.6/ctypes已按指南配置后，加--apply部署。')
        return
    run('shell', 'test -x /mnt/UDISK/xinyu-runtime35/usr/bin/python3 && mkdir -p ' + TARGET + '/tools')
    for name in files:
        run('push', str(ROOT / name), TARGET + '/' + name)
    run('push', str(library), TARGET + '/libpcm_gate.so')
    for name, destination in (('board_prepare.py', 'board_prepare.py'),
                              ('rndis_trial.py', 'rndis_trial_autoprep.py')):
        run('push', str(ROOT / 'tools' / name), TARGET + '/tools/' + destination)
    # 令牌只经标准输入传输，不打印到命令行和日志。
    run('shell', 'umask 077; cat > ' + TARGET + '/bridge-token.txt', input=token.encode('ascii'))
    print('项目文件已部署；未修改USB组合、固件或开机脚本。还需实际运行验收。')


if __name__ == '__main__':
    main()
