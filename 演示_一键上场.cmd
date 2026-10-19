@echo off
rem ============================================================
rem  一键上场：自检 -> 起桥接 -> 板端录一轮 -> 打印识别与回复
rem  任何一步不满足都会停住并说明怎么处理，不会静默失败
rem  echo 文本里一律用全角括号，避免提前闭合 if 块
rem ============================================================
setlocal
cd /d "%~dp0"
title 心语语音交互终端 - 一键上场

set "ADB="
for /f "delims=" %%i in ('where adb 2^>nul') do if not defined ADB set "ADB=%%i"
if not defined ADB if exist "%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB if exist "%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB goto no_adb

echo ============================================================
echo   心语语音交互终端 - 一键上场
echo ============================================================
echo.

rem ---------- 1. 心语服务 ----------
curl -s -o nul -w "%%{http_code}" --max-time 3 http://127.0.0.1:7860/health > "%TEMP%\xy_code.txt" 2>nul
set "CODE="
set /p CODE=<"%TEMP%\xy_code.txt"
if not "%CODE%"=="200" goto no_xinyu
echo [1/5] 心语服务 ......... 在线（127.0.0.1:7860）

rem ---------- 2. 板端连接 ----------
"%ADB%" start-server >nul 2>&1
set "DEV="
for /f "skip=1 tokens=1,2" %%a in ('"%ADB%" devices') do if "%%b"=="device" set "DEV=%%a"
if not defined DEV goto no_device
echo [2/5] 板端连接 ......... %DEV%

"%ADB%" shell "ip -4 addr show usb0" 2>nul | findstr /c:"192.168.113.2" >nul
if errorlevel 1 goto no_usb0
ipconfig | findstr /c:"192.168.113.1" >nul
if errorlevel 1 goto no_nic
echo [3/5] 网络地址 ......... 板端 192.168.113.2 / 电脑 192.168.113.1

"%ADB%" shell "ls /dev/snd/pcmC2D0c" 2>nul | findstr /c:"pcmC2D0c" >nul
if errorlevel 1 goto no_mic
"%ADB%" shell "amixer -c 2 sget Mic" 2>nul | findstr /c:"Capture 16" >nul
if errorlevel 1 "%ADB%" shell "amixer -c 2 sset Mic 100%% cap" >nul 2>&1
echo [4/5] USB 麦克风 ....... card 2，增益 100%%

rem ---------- 3. 电脑桥接 ----------
netstat -ano | findstr /c:":8765" | findstr /c:"LISTENING" >nul
if not errorlevel 1 goto bridge_ok
echo [5/5] 电脑桥接 ......... 启动中（新窗口）
start "心语桥接" "%~dp0演示_1_启动电脑桥接.cmd"
set /a WAIT=0
:wait_bridge
set /a WAIT+=1
timeout /t 1 /nobreak >nul
netstat -ano | findstr /c:":8765" | findstr /c:"LISTENING" >nul
if not errorlevel 1 goto bridge_ok
if %WAIT% GEQ 30 goto no_bridge
goto wait_bridge
:bridge_ok
echo [5/5] 电脑桥接 ......... 监听 8765

rem ---------- 4. 令牌与板端脚本 ----------
set "TOKEN="
for /f "delims=" %%t in ('python -c "import json;print(json.load(open('config.json',encoding='utf-8-sig'))['token'])"') do set "TOKEN=%%t"
if not defined TOKEN goto no_token
"%ADB%" push "tools\board_round.sh" /tmp/board_round.sh >nul 2>&1

rem ---------- 5. 对话循环 ----------
:round
echo.
echo ============================================================
echo   请对着板子上的 USB 麦克风说话，说一句完整的话
echo   （录音 8 秒；说完停一下，随后电脑会念出心语回复）
echo ============================================================
echo.
"%ADB%" shell "XINYU_BRIDGE_TOKEN=%TOKEN% ROUND_SECONDS=8 sh /tmp/board_round.sh"
echo.
echo ------------------------------------------------------------
set "AGAIN="
set /p AGAIN=输入 y 再录一轮，其他任意键结束： 
if /i "%AGAIN%"=="y" goto round
goto done

:done
echo.
echo 结束。桥接窗口可以留着，下次再双击本脚本会直接复用。
pause
exit /b 0

rem ================= 异常分支 =================
:no_adb
echo [停止] 找不到 adb.exe：请安装 Android platform-tools 并加入 PATH
pause & exit /b 2

:no_xinyu
echo [停止] 心语服务没在跑（127.0.0.1:7860 无响应）
echo        请先启动心语，浏览器打开 http://127.0.0.1:7860/health 确认返回 200
pause & exit /b 3

:no_device
echo [停止] 电脑没认到板子：检查 OTG 线是否插在板子 OTG 口、板子是否已上电
pause & exit /b 4

:no_usb0
echo [停止] 板端 usb0 没有 192.168.113.2：板子固件的 USB 网络没起来，重启板子再试
pause & exit /b 5

:no_nic
echo [停止] 电脑缺 192.168.113.1：请用管理员 PowerShell 执行下面一行
echo        Get-NetAdapter ^| Where-Object InterfaceDescription -like '*RNDIS*' ^| ForEach-Object { New-NetIPAddress -InterfaceIndex $_.ifIndex -IPAddress 192.168.113.1 -PrefixLength 30 }
pause & exit /b 6

:no_mic
echo [停止] 板端没枚举到 USB 麦克风（card 2 缺失）：把麦克风插到板子的 HOST 口
pause & exit /b 7

:no_bridge
echo [停止] 电脑桥接 30 秒内没有监听 8765：看新开的窗口里报什么错
pause & exit /b 8

:no_token
echo [停止] 读不到 config.json 里的令牌：确认文件存在且未被改坏
pause & exit /b 9
