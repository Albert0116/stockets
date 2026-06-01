@echo off
chcp 65001 >nul
title FinRobot + DeepSeek 股票分析系统
echo.
echo  ============================================
echo   FinRobot + DeepSeek  股票分析系统
echo  ============================================
echo.

cd /d "%~dp0"

"C:\Users\lxz_y\.conda\envs\finrobot\python.exe" start_analysis.py

pause
