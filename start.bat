@echo off
title AI Physiotherapy System
echo ======================================
echo   AI Hand Rehabilitation System
echo ======================================
echo.

set "PYTHON=python"
set "PYTHONIOENCODING=utf-8"

echo [1/2] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet --user 2>nul

echo [2/2] Starting system...
echo.
%PYTHON% zero_keyboard_physio.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Something went wrong. Check the output above.
    pause
)
