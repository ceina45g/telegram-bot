@echo off
CHCP 65001 > nul
setlocal

:: 設定程式路徑
set PYTHON_EXE="C:\Program Files\Python313\python.exe"
set BOT_FILE="C:\Users\user\Documents\telegram bot\public_pool_monitor_bot.py"

echo ==========================================
echo    Public Pool 監控機器人 啟動工具
echo ==========================================

:: 1. 清理舊的程序
echo [1/2] 正在清理舊的 Python 程序...
taskkill /F /IM python.exe /T 2>nul
timeout /t 2 > nul

:: 2. 啟動機器人
echo [2/2] 正在啟動 Public Pool 監控機器人...
%PYTHON_EXE% -u %BOT_FILE%

pause
