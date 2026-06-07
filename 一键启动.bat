@echo off
chcp 65001 >nul
title FinRobot AI 股票分析系统

echo.
echo   ========================================
echo     FinRobot AI 股票分析系统 v1.0
echo     DeepSeek + Finnhub + yfinance
echo   ========================================
echo.

set PATH=C:\Program Files\nodejs;%PATH%

echo [1/2] 启动后端 API 服务 (端口 8888) ...
start "FinRobot Backend" /min "%UserProfile%\.conda\envs\finrobot\python.exe" "%~dp0server.py"

echo [2/2] 启动前端界面 (端口 5173) ...
start "FinRobot Frontend" /min cmd /c "cd /d %~dp0 && npm run dev"

timeout /t 6 /nobreak >nul

echo.
echo   系统启动完毕！
echo   浏览器访问: http://localhost:5173
echo.
echo   按任意键关闭本窗口（服务将继续在后台运行）
pause >nul
