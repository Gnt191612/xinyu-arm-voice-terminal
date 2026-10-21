"""使用已校验的官方SpeexDSP源码构建隔离的AEC可执行文件。"""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
archive = ROOT / '.realtime-build/speexdsp-1.2.1.tar.gz'
expected = '8c777343e4a6399569c72abc38a95b24db56882c83dbdb6c6424a5f4aeb54d3d'
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit('源码归档校验不符，停止构建')
source = ROOT / '.realtime-build/speexdsp-1.2.1'
command = ['C:/MinGW/bin/gcc.exe', '-O2', '-static', '-DFLOATING_POINT', '-DUSE_KISS_FFT',
           '-DEXPORT=', '-I', str(source / 'include'), '-I', str(source / 'libspeexdsp'),
           str(ROOT / 'tools/aec_pipe.c')]
command.extend(str(source / 'libspeexdsp' / name) for name in
               ('mdf.c', 'fftwrap.c', 'kiss_fft.c', 'kiss_fftr.c'))
command.extend(['-lm', '-o', str(ROOT / '.realtime-build/aec_pipe.exe')])
subprocess.run(command, check=True, cwd=str(ROOT))
print('AEC已构建；许可证保留于官方源码目录COPYING，仍须运行算法与实机测试。')
