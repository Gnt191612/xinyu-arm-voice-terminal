"""只托管本次桥接：指定开发板断开后，结束自己创建的进程树。"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def board_connected(adb, serial):
    try:
        result = subprocess.run([adb, 'devices'], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=0.5,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        return result.returncode == 0 and any(
            line.split() == [serial, 'device']
            for line in result.stdout.decode('utf-8', errors='replace').splitlines())
    except (OSError, subprocess.TimeoutExpired):
        return False


def stop_owned_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        # PID来自本进程的Popen，不按名称批量结束Python或独立心语服务。
        try:
            result = subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=1, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode and process.poll() is None:
                process.kill()
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
    else:
        import signal
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=0.5)


def supervise(process, connected, clock=time.monotonic, sleep=time.sleep):
    missing_since = None
    try:
        while process.poll() is None:
            if connected():
                missing_since = None
            else:
                if missing_since is None:
                    missing_since = clock()
                if clock() - missing_since >= 0.75:
                    print('开发板已断开或调试连接持续失效，停止本次桥接。', flush=True)
                    return 4
            sleep(0.2)
        return process.returncode
    finally:
        stop_owned_process(process)


def main():
    parser = argparse.ArgumentParser(description='开发板连接绑定的电脑桥接')
    parser.add_argument('--serial', default='20080411', help='仅监视这台开发板，不接受其他设备代替')
    parser.add_argument('--adb')
    parser.add_argument('--realtime', action='store_true', help='独立守护实时会话，断板时结束本次整棵进程树')
    parser.add_argument('--duration', type=float, default=0, help='实时会话测试时限')
    parser.add_argument('--prepare', action='store_true', help='启动前检查并临时准备RNDIS及离线文件')
    parser.add_argument('--prepare-only', action='store_true', help='只准备，不启动模型和语音')
    args = parser.parse_args()
    adb = args.adb or shutil.which('adb')
    if not adb:
        for parent in ROOT.parents:
            candidate = parent / 'flash_tools/android-platform-tools/platform-tools/adb.exe'
            if candidate.is_file():
                adb = str(candidate)
                break
    if not adb or not board_connected(adb, args.serial):
        raise SystemExit('指定开发板未连接，不启动识别服务。')
    entry = 'offline_demo.py' if args.prepare or args.prepare_only else ('realtime_session.py' if args.realtime else 'pc_server.py')
    command = [sys.executable, '-u', str(ROOT / entry)]
    if args.realtime or args.prepare or args.prepare_only:
        command.extend(['--serial', args.serial, '--start-xinyu', '--duration', str(args.duration)])
        if args.prepare or args.prepare_only:
            command.remove('--start-xinyu')
        if args.prepare_only:
            command.append('--prepare-only')
    process = subprocess.Popen(command, cwd=str(ROOT), start_new_session=os.name != 'nt',
                               stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        return supervise(process, lambda: board_connected(adb, args.serial))
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
