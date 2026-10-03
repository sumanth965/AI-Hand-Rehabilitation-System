@echo off
setlocal
title AI Hand Rehabilitation System

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment (.venv) not found!
    echo Please run 'setup_windows.bat' first to install required dependencies.
    echo.
    pause
    exit /b 1
)

:: Activate the virtual environment
call .venv\Scripts\activate.bat

:: Set UTF-8 encoding for clean Unicode/console output
set "PYTHONIOENCODING=utf-8"

:: Start the application (passes any arguments like --dashboard)
python main.py %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with error code %ERRORLEVEL%.
    echo You can run 'python diagnose_environment.py' to diagnose environment issues.
    pause
)
