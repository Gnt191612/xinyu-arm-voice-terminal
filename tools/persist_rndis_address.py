"""请求UAC后保存用户已授权的USB网卡持久地址。"""
import base64
import ctypes
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = "$ProjectRoot = '" + str(root).replace("'", "''") + "'\n"
source += (root / 'tools/persist_rndis_address.ps1').read_text(encoding='utf-8')
encoded = base64.b64encode(source.encode('utf-16-le')).decode('ascii')
result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + encoded, str(root), 0)
if result <= 32:
    raise SystemExit('管理员授权未完成，没有保存持久地址。')
print('已请求管理员授权；结果保存在records/RNDIS传输/持久配置结果.json。')
