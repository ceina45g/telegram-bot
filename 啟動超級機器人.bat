@echo off
title Pro Mining Management Bot - Robust Starter
chcp 65001 > nul

:: ================= 設定路徑 (請根據實際路徑修改) =================
set "PYTHON_EXE=C:\Program Files\Python313\python.exe"
set "NGROK_EXE=C:\ProgramData\chocolatey\bin\ngrok.exe"
set "BOT_SCRIPT=unified_super_bot.py"
set "LOG_FILE=super_bot_live.log"
set "PORT=8888"
:: =============================================================

echo ==========================================
echo    Pro Mining Management Bot - 超級啟動器
echo ==========================================

:: 1. 檢查 Python 環境
echo [%time%] 正在檢查 Python 環境...
if not exist "%PYTHON_EXE%" (
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [錯誤] 找不到 Python，請安裝 Python 3.10+ 並勾選 "Add to PATH"。
        pause
        exit /b
    )
    set "PYTHON_EXE=python"
)
echo [確認] Python 已經就緒。

:: 2. 檢查 Ngrok 環境
echo [%time%] 正在檢查 Ngrok 環境...
if not exist "%NGROK_EXE%" (
    ngrok version >nul 2>&1
    if errorlevel 1 (
        echo [錯誤] 找不到 Ngrok，請將 ngrok.exe 放入此資料夾或安裝路徑。
        pause
        exit /b
    )
    set "NGROK_EXE=ngrok"
)
echo [確認] Ngrok 已經就緒。

:: 3. 清理舊的行程
echo [%time%] 正在清理舊的機器人行程...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im ngrok.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT%') do (
    if not "%%a"=="" taskkill /f /pid %%a >nul 2>&1
)

:: 4. 重新啟動 Ngrok 隧道
echo [%time%] 正在重新啟動 Ngrok 隧道 (Port %PORT%)...
start /min "" "%NGROK_EXE%" http %PORT%
echo [%time%] 等待 Ngrok 建立連線 (8秒)...
timeout /t 8 > nul

:: 5. 啟動機器人主程式
:start
echo [%time%] 啟動 正在啟動機器人主程式 (%BOT_SCRIPT%)...
echo [%time%] 您可以在 Telegram 輸入 /start 測試功能。
echo [%time%] 詳細日誌請查看: %LOG_FILE%

"%PYTHON_EXE%" "%BOT_SCRIPT%" >> "%LOG_FILE%" 2>&1

echo [%time%] 警告: 程式異常退出，將在 5 秒後重新啟動...
timeout /t 5 > nul
goto start
