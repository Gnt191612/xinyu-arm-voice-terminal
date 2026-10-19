"""只读检查板端运行条件，不录音、不修改混音器、不切换USB角色。"""
import argparse
import json
import platform
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from board_audio import list_audio_devices


def check_board(library, inventory_only=False, playback_target='pc'):
    report = {'machine': platform.machine(), 'system': platform.system(),
              'python': sys.version, 'library': str(library), 'errors': [],
              'pointer_bits': struct.calcsize('P') * 8,
              'check_mode': '仅环境清点' if inventory_only else '环境与动态库检查',
              'assembly_checked': False, 'hardware_audio_verified': False}
    errors = report['errors']
    arm = (report['system'] == 'Linux' and report['machine'].startswith('arm')
           and report['pointer_bits'] == 32)
    if not arm:
        errors.append('必须在32位ARM Linux板端执行；此结果不是T113实测通过')
    if sys.version_info < (3, 5):
        errors.append('板端需要Python 3.5或更新版本及ctypes/libffi等标准库支持')
    for name, filename in (('model', '/proc/device-tree/model'),
                           ('cards', '/proc/asound/cards'), ('pcm', '/proc/asound/pcm')):
        path = Path(filename)
        report[name] = path.read_text(errors='replace').replace('\x00', '').strip() if path.is_file() else ''
    pcm = report['pcm']
    report['audio_devices'] = list_audio_devices()
    for command in (('arecord', 'aplay') if playback_target == 'board' else ('arecord',)):
        executable = shutil.which(command)
        if not executable:
            errors.append('缺少' + command + '，请在匹配的Tina SDK中补齐alsa-utils')
            continue
        try:
            result = subprocess.run([executable, '-l'], stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, universal_newlines=True, timeout=10)
            report[command] = {'returncode': result.returncode, 'output': result.stdout}
            if result.returncode:
                errors.append(command + '列举设备失败')
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(command + '执行失败：' + str(exc))
    # 部分Tina固件不导出/proc/asound，使用ALSA工具输出补充判断。
    for direction, command in (('capture', 'arecord'), ('playback', 'aplay')):
        if direction == 'playback' and playback_target == 'pc':
            continue
        listed = report.get(command, {}).get('output', '')
        if not re.search(direction + r'\s+[1-9][0-9]*', pcm) and not re.search(r'card\s+\d+.*device\s+\d+', listed):
            errors.append('没有发现' + direction + ' PCM设备；检查驱动、USB Host与接线')
    if arm and not inventory_only:
        try:
            from audio_core import Gate
            gate = Gate(library.resolve())
            if gate.frame([-32768, 32767, 0, -1]) != (65536, True) or gate.frame([]) != (0, False):
                raise ValueError('汇编动态库边界结果不符')
            report['assembly'] = '真实动态库已加载，PCM16边界与空帧通过；不是性能测试'
            report['assembly_checked'] = True
        except (ImportError, OSError, AttributeError, ValueError) as exc:
            errors.append('动态库加载或符号/ABI检查失败：' + str(exc))
    report['passed'] = not errors
    report['scope'] = '只读环境与动态库检查；未验证真人录音、网络或音箱实际出声'
    return report


def main():
    parser = argparse.ArgumentParser(description='Tina板端只读环境检查')
    parser.add_argument('--library', type=Path, default=ROOT / 'arm/libpcm_gate.so')
    parser.add_argument('--playback-target', choices=('pc', 'board'), default='pc')
    parser.add_argument('--inventory-only', action='store_true',
                        help='编译动态库前只清点环境；不代表汇编或硬件验收通过')
    args = parser.parse_args()
    report = check_board(args.library, args.inventory_only, args.playback_target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
