@echo off
rem ============================================================
rem  演示 3：打开板端 shell（排查用）
rem ============================================================
setlocal
cd /d "%~dp0"
set "ADB="
for /f "delims=" %%i in ('where adb 2^>nul') do if not defined ADB set "ADB=%%i"
if not defined ADB if exist "%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB if exist "%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe" set "ADB=%~dp0..\..\..\flash_tools\android-platform-tools\platform-tools\adb.exe"
if not defined ADB (
  echo [错误] 找不到 adb。
  pause & exit /b 2
)
echo 进入板端 shell：输入 exit 退出。
"%ADB%" shell
pause
