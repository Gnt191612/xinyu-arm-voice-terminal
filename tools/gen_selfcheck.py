# -*- coding: utf-8 -*-
"""生成“演示前自检”批处理（GBK 编码，供默认 936 控制台中文显示）。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "演示_0_演示前自检.cmd"

SCRIPT = r"""@echo off
rem ============================================================
rem  演示 0：演示前自检（只读检查 + 安全自动修复）
rem  检查：adb / 板端网卡地址 / 电脑 RNDIS 地址 / USB 麦克风 / 增益 / 心语 / 桥接
rem  说明：echo 文本中一律用全角括号，避免提前闭合 if 语句块
rem ============================================================
setlocal
cd /d "%~dp0"
set "ADB="
for /f "delims=" %%i in ('where adb 2^>nul') do if not defined ADB set "ADB=%%i"
if not defined ADB if exist "%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB if exist "%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"

echo ============================================================
echo   心语语音交互终端 - 演示前自检
echo ============================================================
echo.

if not defined ADB goto no_adb
"%ADB%" start-server >nul 2>&1
set "DEV="
for /f "skip=1 tokens=1,2" %%a in ('"%ADB%" devices') do if "%%b"=="device" set "DEV=%%a"
if not defined DEV goto no_device
echo [1] adb 设备 ....... [OK] %DEV%
goto check_usb0

:no_adb
echo [1] adb 设备 ....... [缺失] 找不到 adb，请把 platform-tools 加入 PATH
goto tail

:no_device
echo [1] adb 设备 ....... [失败] 没有设备，检查 OTG 线与板子电源
goto tail

:check_usb0
"%ADB%" shell "ip -4 addr show usb0" 2>nul | findstr /c:"192.168.113.2" >nul
if errorlevel 1 echo [2] 板端网卡 ....... [失败] usb0 无 192.168.113.2，可能需要重启板子
if not errorlevel 1 echo [2] 板端网卡 ....... [OK] 192.168.113.2

ipconfig | findstr /c:"192.168.113.1" >nul
if errorlevel 1 echo [3] 电脑网卡 ....... [失败] 缺 192.168.113.1，需管理员在 USB 网卡上设 192.168.113.1/30
if not errorlevel 1 echo [3] 电脑网卡 ....... [OK] 192.168.113.1

"%ADB%" shell "ls /dev/snd/pcmC2D0c" 2>nul | findstr /c:"pcmC2D0c" >nul
if errorlevel 1 echo [4] USB 麦克风 ..... [失败] card 2 未出现，检查麦克风是否插在 HOST 口
if not errorlevel 1 echo [4] USB 麦克风 ..... [OK] card 2 已枚举

rem 增益档位 0-16，16 即 100%；批处理里避免匹配百分号
"%ADB%" shell "amixer -c 2 sget Mic" 2>nul | findstr /c:"Capture 16" >nul
if not errorlevel 1 goto gain_ok
"%ADB%" shell "amixer -c 2 sset Mic 100%% cap" >nul 2>&1
echo [5] 麦克风增益 ..... [已修复] 刚才不是 100%%，现已设为 100%% / +23.81dB
goto gain_done
:gain_ok
echo [5] 麦克风增益 ..... [OK] 100%%
:gain_done

:tail
curl -s -o nul -w "%%{http_code}" --max-time 3 http://127.0.0.1:7860/health > "%TEMP%\xinyu_code.txt" 2>nul
set "CODE="
set /p CODE=<"%TEMP%\xinyu_code.txt"
if "%CODE%"=="200" echo [6] 心语服务 ....... [OK] 127.0.0.1:7860
if not "%CODE%"=="200" echo [6] 心语服务 ....... [失败] 7860 无响应，请先启动心语服务

netstat -ano | findstr /c:":8765" | findstr /c:"LISTENING" >nul
if errorlevel 1 echo [7] 电脑桥接 ....... [未启动] 请运行 演示_1_启动电脑桥接.cmd
if not errorlevel 1 echo [7] 电脑桥接 ....... [OK] 8765 监听中

echo.
echo 提示：1-5 全部 OK 且 6、7 就绪，就可以双击 演示_2_板端跑一轮.cmd 上场了。
echo ============================================================
pause
"""


def main():
    with OUT.open("w", encoding="gbk", newline="\r\n") as fh:
        fh.write(SCRIPT)
    print("已生成:", OUT, OUT.stat().st_size, "字节")


if __name__ == "__main__":
    main()
