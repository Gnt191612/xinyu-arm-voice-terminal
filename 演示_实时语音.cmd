@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0.realtime-deps;%~dp0.deps"
set "PYTHONIOENCODING=utf-8"
set "DEMO_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not exist "%DEMO_PYTHON%" set "DEMO_PYTHON=python"
"%DEMO_PYTHON%" supervise_bridge.py --realtime --prepare
exit /b %errorlevel%
