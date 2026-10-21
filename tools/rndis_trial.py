"""临时USB组合试验；未确认则恢复原ADB，不修改开机配置。"""
import json
import subprocess
import sys
import time
from pathlib import Path

G = Path('/sys/kernel/config/usb_gadget/g1')
ROOT = Path('/mnt/UDISK/xinyu-arm-check/rndis-trial')
STATE = ROOT / 'state.json'
ATTRS = ('idVendor', 'idProduct', 'bDeviceClass', 'bDeviceSubClass',
         'bDeviceProtocol', 'strings/0x409/product', 'os_desc/use',
         'os_desc/b_vendor_code', 'os_desc/qw_sign')


def read(path):
    return path.read_text().strip('\x00\n')


def write(path, value):
    path.write_text(str(value) + '\n')


def restore():
    state = json.loads(STATE.read_text())
    write(G / 'UDC', '')
    for path in (G / 'configs/c.1/rndis.usb0', G / 'os_desc/c.1'):
        if path.is_symlink():
            path.unlink()
    for name in ATTRS:
        if name != 'os_desc/qw_sign' or state[name]:
            write(G / name, state[name])
    write(G / 'UDC', state['udc'])
    subprocess.call(['ip', 'link', 'set', 'usb0', 'down'], stderr=subprocess.DEVNULL)
    subprocess.call(['ip', 'addr', 'del', '192.168.113.2/30', 'dev', 'usb0'],
                    stderr=subprocess.DEVNULL)
    subprocess.call(['ip', 'addr', 'del', '169.254.113.2/16', 'dev', 'usb0'],
                    stderr=subprocess.DEVNULL)
    (ROOT / 'restored').write_text('已恢复原ADB')
    print('已恢复原ADB配置', flush=True)


def guard():
    for unused in range(300):
        if (ROOT / 'confirmed').exists() or (ROOT / 'restored').exists():
            return
        time.sleep(1)
    restore()


def apply():
    links = sorted(p.name for p in (G / 'configs/c.1').iterdir() if p.is_symlink())
    if links != ['ffs.adb'] or (G / 'os_desc/c.1').exists():
        raise RuntimeError('当前不是预期的纯ADB配置，停止试验')
    if ROOT.exists():
        raise RuntimeError('试验目录已存在，先核对上次状态，不覆盖')
    state = {name: read(G / name) for name in ATTRS}
    state['udc'] = read(G / 'UDC')
    if not state['udc']:
        raise RuntimeError('当前USB未绑定，停止试验')
    ROOT.mkdir()
    STATE.write_text(json.dumps(state))
    log = open(str(ROOT / 'guard.log'), 'w')
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'guard'],
                     stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                     start_new_session=True)
    try:
        write(G / 'UDC', '')
        rndis = G / 'functions/rndis.usb0'
        rndis.mkdir(exist_ok=True)
        write(rndis / 'dev_addr', '02:11:30:00:00:02')
        write(rndis / 'host_addr', '02:11:30:00:00:01')
        write(rndis / 'os_desc/interface.rndis/compatible_id', 'RNDIS')
        write(rndis / 'os_desc/interface.rndis/sub_compatible_id', '5162001')
        write(G / 'idVendor', '0x0525')
        write(G / 'idProduct', '0xa4a2')
        write(G / 'bDeviceClass', '0xef')
        write(G / 'bDeviceSubClass', '0x02')
        write(G / 'bDeviceProtocol', '0x01')
        write(G / 'strings/0x409/product', 'T113 ADB RNDIS')
        write(G / 'os_desc/b_vendor_code', '0xcd')
        write(G / 'os_desc/qw_sign', 'MSFT100')
        write(G / 'os_desc/use', '1')
        (G / 'configs/c.1/ffs.adb').unlink()
        (G / 'configs/c.1/rndis.usb0').symlink_to(rndis)
        (G / 'configs/c.1/ffs.adb').symlink_to(G / 'functions/ffs.adb')
        (G / 'os_desc/c.1').symlink_to(G / 'configs/c.1')
        write(G / 'UDC', state['udc'])
        for unused in range(10):
            if Path('/sys/class/net/usb0').exists():
                break
            time.sleep(1)
        subprocess.check_call(['ip', 'addr', 'replace', '192.168.113.2/30', 'dev', 'usb0'])
        subprocess.check_call(['ip', 'addr', 'replace', '169.254.113.2/16', 'dev', 'usb0'])
        subprocess.check_call(['ip', 'link', 'set', 'usb0', 'up'])
        print('组合已绑定；300秒未确认则恢复原ADB', flush=True)
    except Exception:
        restore()
        raise


if __name__ == '__main__':
    action = sys.argv[1]
    if action in ('start', 'restore-start'):
        log = open(str(ROOT.parent / 'rndis-launch.log'), 'w')
        child_action = 'apply' if action == 'start' else 'restore'
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), child_action],
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        print('临时试验进程：' + str(process.pid), flush=True)
    elif action == 'apply':
        time.sleep(2)
        apply()
    elif action == 'guard':
        guard()
    elif action == 'restore':
        time.sleep(2)
        restore()
    elif action == 'confirm':
        (ROOT / 'confirmed').write_text('电脑已验证组合连接')
    else:
        raise ValueError('未知操作')
