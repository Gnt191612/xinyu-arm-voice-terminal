@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0.deps"
set "PYTHONIOENCODING=utf-8"
python supervise_bridge.py
exit /b %errorlevel%
