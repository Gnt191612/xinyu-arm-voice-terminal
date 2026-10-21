"""真实RNDIS持续流稳定性和主进程资源记录，不代替真人双讲。"""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from supervise_bridge import stop_owned_process


class Memory(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [
        (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
        'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def main():
    output = ROOT / 'records/实时交互/稳定性复核'
    output.mkdir(exist_ok=True)
    log = open(output / 'session.log', 'wb')
    process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'realtime_session.py'), '--duration', '190',
        '--calibration-wav', str(ROOT / 'records/实时交互/校准播放.wav')], cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    memory_api = ctypes.WinDLL('psapi').GetProcessMemoryInfo
    memory_api.argtypes = [ctypes.c_void_p, ctypes.POINTER(Memory), ctypes.c_ulong]
    handle = kernel.OpenProcess(0x410, False, process.pid)
    samples = []
    started = time.monotonic()
    try:
        while process.poll() is None:
            state = Memory()
            state.cb = ctypes.sizeof(state)
            if handle and memory_api(handle, ctypes.byref(state), state.cb):
                samples.append({'seconds': time.monotonic() - started,
                                'working_set_mb': state.WorkingSetSize / 1048576,
                                'private_mb': state.PrivateUsage / 1048576})
            if time.monotonic() - started > 210:
                raise RuntimeError('会话未在限定时长内退出')
            time.sleep(5)
        record = {'returncode': process.returncode, 'samples': samples,
                  'seconds': time.monotonic() - started,
                  '边界': '真实RNDIS与AEC回灌/静音持续流，不是真人对话或物理拔板'}
        (output / 'resources.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'returncode': process.returncode, 'seconds': record['seconds'],
                          '资源采样数': len(samples)}), flush=True)
    finally:
        stop_owned_process(process)
        if handle:
            kernel.CloseHandle(handle)
        log.close()


if __name__ == '__main__':
    main()
