@echo off
chcp 65001 >nul
title FinRobot AI

echo.
echo   ========================================
echo     FinRobot AI Stock Analysis v1.0
echo     DeepSeek + Finnhub + yfinance
echo   ========================================
echo.

set PATH=C:\Program Files\nodejs;%PATH%

echo [1/2] Starting backend API (port 8888) ...
start "FinRobot Backend" /min "%UserProfile%\.conda\envs\finrobot\python.exe" "%~dp0server.py"

echo [2/2] Starting frontend UI (port 5173) ...
start "FinRobot Frontend" /min cmd /c "cd /d %~dp0 && npm run dev"

timeout /t 6 /nobreak >nul

echo.
echo   System ready!
echo   Open browser: http://localhost:5173
echo.
echo   Press any key to close this window (services will keep running)
pause >nul
