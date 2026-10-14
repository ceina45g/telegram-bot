@echo off
CHCP 65001 > nul
setlocal

set PYTHON_EXE="C:\Program Files\Python313\python.exe"
set NGROK_EXE="C:\ProgramData\chocolatey\bin\ngrok.exe"
set BOT_FILE="C:\Users\user\Documents\telegram bot\mining_monitor_pool_bot.py"

echo ==========================================
echo    Telegram Bot Webhook 啟動程式
echo ==========================================

echo [1/3] 正在清理舊行程...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM ngrok.exe /T 2>nul
timeout /t 2 > nul

echo [2/3] 正在啟動 ngrok (Port 8000)...
start "ngrok_tunnel" /min %NGROK_EXE% http 8000
echo      等待隧道建立中 (15秒)...
timeout /t 15 > nul

echo [3/3] 正在啟動 FastAPI 機器人...
%PYTHON_EXE% -u %BOT_FILE%

pause
