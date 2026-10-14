@echo off
CHCP 65001 > nul
setlocal

:: 設定程式路徑
set PYTHON_EXE="C:\Program Files\Python313\python.exe"
set NGROK_EXE="C:\ProgramData\chocolatey\bin\ngrok.exe"
set BOT_FILE="C:\Users\user\Documents\telegram bot\mining_monitor_pool_bot.py"

echo ==========================================
echo    礦池監控機器人 (Mining Bot) 啟動工具
echo ==========================================

:: 1. 清理舊的程序
echo [1/3] 正在清理舊的程序...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM ngrok.exe /T 2>nul
timeout /t 2 > nul

:: 2. 啟動 ngrok 隧道
echo [2/3] 正在啟動 ngrok 隧道 (Port 8000)...
start "ngrok_tunnel" /min %NGROK_EXE% http 8000
echo      等待隧道建立網址 (12秒)...
timeout /t 12 > nul

:: 3. 啟動機器人
echo [3/3] 正在啟動礦池監控機器人 (Webhook 模式)...
%PYTHON_EXE% -u %BOT_FILE%

pause
