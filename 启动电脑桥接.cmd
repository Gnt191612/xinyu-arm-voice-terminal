@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0.deps"
set "PYTHONIOENCODING=utf-8"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe pc_server.py %*
) else (
    python pc_server.py %*
)
pause
