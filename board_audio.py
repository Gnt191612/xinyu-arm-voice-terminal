"""列出ALSA录放音端点；不猜测设备用途、不录音、不更改系统配置。"""
import os
import re
import shutil
import subprocess
from pathlib import Path


def list_alsa_devices():
    """Tina未导出proc音频列表时，只读调用ALSA工具，不推断USB身份。"""
    devices = {}
    for command, direction in (('arecord', 'capture'), ('aplay', 'playback')):
        executable = shutil.which(command)
        if not executable:
            continue
        try:
            result = subprocess.run([executable, '-l'], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, universal_newlines=True, timeout=10,
                                    env=dict(os.environ, LC_ALL='C'))
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode:
            continue
        for line in result.stdout.splitlines():
            match = re.search(r'card\s+(\d+):\s*([^\s\[]+)\s*\[.*?\],\s*device\s+(\d+):', line)
            if not match:
                continue
            card, card_id, device = match.groups()
            item = devices.setdefault((int(card), int(device)), {
                'card_index': int(card), 'card_id': card_id, 'device_index': int(device),
                'usb_id': None, 'endpoint': 'plughw:CARD=' + card_id + ',DEV=' + device,
                'stable_card_id': True, 'capture': False, 'playback': False,
                'description': line.strip(), 'source': 'ALSA工具；USB身份需另行核实'})
            item[direction] = True
    return list(devices.values())


def list_audio_devices(proc_root=Path('/proc/asound')):
    pcm_file = proc_root / 'pcm'
    devices = []
    if not pcm_file.is_file():
        return list_alsa_devices() if proc_root == Path('/proc/asound') else devices
    for line in pcm_file.read_text(errors='replace').splitlines():
        match = re.match(r'\s*(\d+)-(\d+):', line)
        if not match:
            continue
        card, device = (int(value) for value in match.groups())
        card_dir = proc_root / ('card' + str(card))
        id_file, usb_file = card_dir / 'id', card_dir / 'usbid'
        card_id = id_file.read_text().strip() if id_file.is_file() else None
        usb_id = usb_file.read_text().strip() if usb_file.is_file() else None
        endpoint = ('plughw:CARD=' + card_id + ',DEV=' + str(device)) if card_id else ('plughw:' + str(card) + ',' + str(device))
        devices.append({'card_index': card, 'card_id': card_id, 'device_index': device,
                        'usb_id': usb_id, 'endpoint': endpoint,
                        'stable_card_id': bool(card_id),
                        'capture': bool(re.search(r'capture\s+[1-9][0-9]*', line)),
                        'playback': bool(re.search(r'playback\s+[1-9][0-9]*', line)),
                        'description': line.strip()})
    return devices
