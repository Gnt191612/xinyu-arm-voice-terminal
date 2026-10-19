@echo off
rem ============================================================
rem  演示 2：板端跑一轮（ALSA 录音 5 秒 → ARM 汇编门控 → RNDIS 上传）
rem  用法：先运行 演示_1_启动电脑桥接.cmd，再双击本文件。
rem        看到“请现在对着麦克风说话”后立刻说话。
rem ============================================================
setlocal
cd /d "%~dp0"

set "ADB="
for /f "delims=" %%i in ('where adb 2^>nul') do if not defined ADB set "ADB=%%i"
if not defined ADB if exist "%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB if exist "%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB (
  echo [错误] 找不到 adb。请把 platform-tools 加入 PATH，或放到 flash_tools 目录。
  pause & exit /b 2
)
echo 使用 adb: %ADB%

set "TOKEN="
for /f "delims=" %%t in ('python -c "import json;print(json.load(open('config.json',encoding='utf-8-sig'))['token'])"') do set "TOKEN=%%t"
if not defined TOKEN (
  echo [错误] 无法从 config.json 读取令牌。
  pause & exit /b 3
)

echo.
echo === 设备状态 ===
"%ADB%" devices
echo.
echo === 推送板端脚本 ===
"%ADB%" push "tools\board_round.sh" /tmp/board_round.sh
echo.
echo ============================================================
echo   马上开始录音 5 秒：请现在对着板子上的 USB 麦克风说话！
echo   （录完会自动上传、识别、心语回复、电脑念出来）
echo ============================================================
echo.
"%ADB%" shell "XINYU_BRIDGE_TOKEN=%TOKEN% sh /tmp/board_round.sh"
echo.
echo === 本轮结束 ===
pause
