"""显式调用UAC，不代点、不绕过管理员授权。"""
import base64
import ctypes
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = "$ProjectRoot = '" + str(root).replace("'", "''") + "'\n"
source += (root / 'tools/repair_rndis_device.ps1').read_text(encoding='utf-8')
encoded = base64.b64encode(source.encode('utf-16-le')).decode('ascii')
result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + encoded, str(root), 0)
if result <= 32:
    raise SystemExit('管理员授权未完成，没有恢复驱动或配置地址。')
print('已请求管理员授权；结果保存在records/RNDIS传输/设备恢复结果.json。')
