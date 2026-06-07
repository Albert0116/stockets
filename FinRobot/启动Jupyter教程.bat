@echo off
chcp 65001 >nul
title Jupyter Lab - FinRobot 教程

cd /d "%~dp0"
echo 正在启动 Jupyter Lab，请稍候...
echo 浏览器将自动打开，教程在 tutorials_beginner/ 目录中

"C:\Users\lxz_y\.conda\envs\finrobot\Scripts\jupyter.exe" lab --notebook-dir=. 

pause
