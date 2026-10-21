"""板端临时准备，复用既有RNDIS实现，不修改固件或开机脚本。"""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import rndis_trial_autoprep as trial

ROOT = Path('/mnt/UDISK/xinyu-arm-check')


def status():
    for name in ('libpcm_gate.so', 'bridge-token.txt'):
        if not (ROOT / name).is_file() or not (ROOT / name).stat().st_size:
            raise RuntimeError('板端离线运行文件缺失，未修改USB')
    links = sorted(path.name for path in (trial.G / 'configs/c.1').iterdir() if path.is_symlink())
    vendor = trial.read(trial.G / 'idVendor')
    product = trial.read(trial.G / 'idProduct')
    if links == ['ffs.adb'] and (vendor, product) == ('0x18d1', '0xd002'):
        mode = 'adb'
    elif links == ['ffs.adb', 'rndis.usb0'] and (vendor, product) == ('0x0525', '0xa4a2'):
        mode = 'ready'
    else:
        raise RuntimeError('USB配置不是本项目已验证状态，未修改')
    return {'mode': mode, 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def apply():
    time.sleep(0.3)
    if status()['mode'] != 'adb':
        raise RuntimeError('状态已变化，未重复配置USB')
    if trial.ROOT.exists():
        if not ((trial.ROOT / 'confirmed').exists() or (trial.ROOT / 'restored').exists()):
            raise RuntimeError('存在未确认的旧USB试验，保留原状并停止')
        archive = ROOT / ('rndis-trial-before-auto-' + uuid.uuid4().hex)
        trial.ROOT.rename(archive)
        print('旧记录保留：' + str(archive), flush=True)
    trial.apply()


if __name__ == '__main__':
    if sys.argv[1] == 'status':
        print(json.dumps(status()), flush=True)
    elif sys.argv[1] == 'start':
        if status()['mode'] != 'adb':
            raise RuntimeError('非纯ADB状态，未启动配置')
        log = open(str(ROOT / 'rndis-auto-prepare.log'), 'a')
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'apply'],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print(json.dumps({'started_pid': child.pid}), flush=True)
    elif sys.argv[1] == 'apply':
        apply()
    elif sys.argv[1] == 'confirm':
        if status()['mode'] != 'ready':
            raise RuntimeError('USB未就绪，不确认')
        (trial.ROOT / 'confirmed').write_text('启动准备已验证USB组合和电脑地址')
        print(json.dumps(status()), flush=True)
    else:
        raise ValueError('未知准备操作')
