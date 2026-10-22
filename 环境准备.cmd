@echo off
setlocal
cd /d "%~dp0"
py -3.11 tools\setup_environment.py
set "RESULT=%errorlevel%"
echo.
echo Exit code: %RESULT%
pause
exit /b %RESULT%
