@echo off
title AI Hand Rehab - Therapist Dashboard
echo ======================================
echo   Therapist Dashboard
echo ======================================
echo.

set "PYTHON=python"
set "PYTHONIOENCODING=utf-8"

echo [1/2] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet --user 2>nul

echo [2/2] Starting dashboard...
echo.
%PYTHON% therapist_dashboard.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Dashboard stopped unexpectedly. Check the output above.
    pause
)
