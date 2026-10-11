@echo off
cd /d "%~dp0"
set "PYTHONPATH=%~dp0.deps"
set "PYTHONIOENCODING=utf-8"
set "PROJECT_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PROJECT_PYTHON=.venv\Scripts\python.exe"
%PROJECT_PYTHON% tools/run_tests.py
if errorlevel 1 goto end
%PROJECT_PYTHON% tools/verify_arm.py
if errorlevel 1 goto end
%PROJECT_PYTHON% tools/check_client.py
if errorlevel 1 goto end
%PROJECT_PYTHON% tools/check_speech.py
:end
pause
