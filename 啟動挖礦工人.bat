@echo off
CHCP 65001 > nul
setlocal
title NerdMiner Stratum Worker
echo ==========================================
echo    NerdMiner 挖礦工人 (Worker) 啟動工具
echo ==========================================
echo.
echo 正在啟動 NerdMiner 挖礦工人...
"C:\Program Files\Python313\python.exe" worker.py
pause
