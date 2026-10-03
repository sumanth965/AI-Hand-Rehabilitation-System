@echo off
setlocal enabledelayedexpansion
title AI Hand Rehabilitation System - Windows Setup

echo ======================================================================
echo   AI HAND REHABILITATION SYSTEM -- AUTOMATED WINDOWS SETUP
echo ======================================================================
echo.

:: 1. Check Python installation
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo.
    echo Please install Python 3.12 (64-bit) from:
    echo   https://www.python.org/downloads/release/python-31210/
    echo IMPORTANT: Check the box "Add python.exe to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Check Python Version and Architecture
echo [1/5] Checking Python Version and Architecture...
python -c "import sys, platform; sys.exit(0 if (sys.version_info.major == 3 and 10 <= sys.version_info.minor <= 12 and platform.architecture()[0] == '64bit') else 1)" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARNING / ERROR] Incompatible Python detected!
    python -c "import sys, platform; print(f'Detected: Python {sys.version.split()[0]} ({platform.architecture()[0]})')"
    echo.
    echo Requirement: Python 3.10 to 3.12, 64-bit (Tested: Python 3.12.10 AMD64).
    echo Python 3.13 is NOT currently supported by Google MediaPipe on Windows.
    echo 32-bit Python is NOT supported by MediaPipe or OpenCV.
    echo.
    set /p CONTINUE="Do you still want to proceed anyway? (Y/N): "
    if /i "!CONTINUE!" NEQ "Y" (
        echo Setup aborted. Please install Python 3.12 64-bit.
        pause
        exit /b 1
    )
) else (
    for /f "delims=" %%v in ('python -c "import sys; print(sys.version.split()[0])"') do set PY_VER=%%v
    echo   [+] Python Version: !PY_VER! (64-bit) -- OK
)

:: 3. Create Virtual Environment
echo.
echo [2/5] Setting up Virtual Environment (.venv)...
if not exist ".venv\Scripts\activate.bat" (
    echo   [*] Creating clean virtual environment in .venv...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        echo Check file permissions or reinstall Python with standard venv support.
        pause
        exit /b 1
    )
    echo   [+] Virtual environment created successfully.
) else (
    echo   [+] Existing .venv found.
)

:: 4. Activate Virtual Environment
call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: 5. Upgrade pip safely & install dependencies
echo.
echo [3/5] Upgrading pip and wheel tooling...
python -m pip install --upgrade pip setuptools wheel --quiet

echo.
echo [4/5] Installing Required Dependencies from requirements.txt...
echo   (This may take 1-3 minutes on a fresh install for MediaPipe and Pygame)
python -m pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Package installation failed.
    echo Common reasons:
    echo   - Internet connection issue during download
    echo   - Python version mismatch (e.g. Python 3.13 cannot install mediapipe)
    echo   - Microsoft Visual C++ Redistributable missing (https://aka.ms/vs/17/release/vc_redist.x64.exe)
    echo.
    pause
    exit /b 1
)

:: 6. Verification
echo.
echo [5/5] Verifying System Components and Imports...
python -c "
import sys

components = [
    ('MediaPipe', 'import mediapipe; mp_hands = mediapipe.solutions.hands'),
    ('OpenCV', 'import cv2'),
    ('NumPy', 'import numpy; assert int(numpy.__version__.split(\".\")[0]) < 2, \"NumPy 2.x breaks MediaPipe!\"'),
    ('Pygame', 'import pygame; pygame.init()'),
    ('SQLite', 'import sqlite3'),
    ('Security/Crypto', 'import bcrypt, cryptography'),
    ('Speech/TTS', 'import pyttsx3'),
    ('Project Core', 'import physio, admin_dashboard, adaptive_ai_engine, clinical_intelligence')
]

all_ok = True
print('')
for name, test_cmd in components:
    try:
        exec(test_cmd)
        print(f'  {name:<18}: OK')
    except Exception as e:
        print(f'  {name:<18}: FAILED ({e})')
        all_ok = False

sys.exit(0 if all_ok else 1)
"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ======================================================================
    echo  SETUP ENCOUNTERED VERIFICATION ERRORS
    echo ======================================================================
    echo Please review the failed component above.
    echo You can run 'python diagnose_environment.py' for full diagnostics.
    echo ======================================================================
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo  AI HAND REHABILITATION SYSTEM SETUP COMPLETED SUCCESSFULLY!
echo ======================================================================
echo.
echo To launch the Patient Application:
echo   run_project.bat
echo.
echo To launch the Therapist Admin Dashboard:
echo   run_project.bat --dashboard
echo   (or start_dashboard.bat)
echo.
echo To run full system diagnostics at any time:
echo   .venv\Scripts\activate
echo   python diagnose_environment.py
echo.
echo ======================================================================
pause
