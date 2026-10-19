@echo off
rem ============================================================
rem  演示 1：启动电脑桥接（真实模式，监听 RNDIS 专网地址）
rem  用法：双击本文件；保持窗口开启，再做演示 2。
rem ============================================================
cd /d "%~dp0"
set "PYTHONPATH=%~dp0.deps"
set "PYTHONIOENCODING=utf-8"
echo.
echo  ===== 心语语音交互终端 - 电脑桥接（真实模式）=====
echo  监听地址取自 config.json（当前应为 192.168.113.1:8765）
echo  保持本窗口不关；另开窗口运行 演示_2_板端跑一轮.cmd
echo  停止：Ctrl+C
echo  ==================================================
echo.
python pc_server.py
echo.
echo 桥接已退出。
pause
