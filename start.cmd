@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title YOLO Studio
where python >nul 2>nul
if not errorlevel 1 (
    python launch.py
    goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 launch.py
    goto finished
)
echo [ERROR] Python was not found. Please install Python 3.11 or 3.12 and enable Add Python to PATH.
:finished
if errorlevel 1 (
    echo.
    echo Startup failed. Please check the message above.
    pause
)
endlocal
