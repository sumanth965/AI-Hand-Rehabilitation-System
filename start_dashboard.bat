@echo off
title AI Hand Rehab - Therapist Dashboard
echo ======================================
echo   Therapist Dashboard
echo ======================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

set "PYTHON=python"
set "PYTHONIOENCODING=utf-8"

echo [1/2] Checking dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet 2>nul

echo [2/2] Starting dashboard...
echo.
%PYTHON% therapist_dashboard.py 8081

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Dashboard stopped unexpectedly. Check the output above.
    pause
)
