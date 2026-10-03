"""
AI Hand Rehabilitation System - Environment Diagnostics Tool

Performs a non-destructive audit of the local hardware, Python runtime,
installed dependencies, computer vision pipeline, database integrity,
and optional local LLM services.
"""

import sys
import os
import platform
import sqlite3
import urllib.request
import json
import ctypes


def get_ram_gb() -> float | None:
    """Detect total physical RAM on Windows in GB."""
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return round(stat.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        pass
    return None


def run_diagnostics():
    print("=" * 70)
    print(" AI HAND REHABILITATION SYSTEM -- ENVIRONMENT DIAGNOSTICS")
    print("=" * 70)

    critical_failures = []
    warnings = []

    # ---------------------------------------------------------
    # 1. SYSTEM & ARCHITECTURE
    # ---------------------------------------------------------
    print("\n[1/6] Operating System & Hardware Platform:")
    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    arch, _ = platform.architecture()
    machine = platform.machine()
    ram_gb = get_ram_gb()

    print(f"  * OS:           {os_name} {os_release} (Build {os_version})")
    print(f"  * Architecture: {arch} ({machine})")
    if ram_gb is not None:
        print(f"  * Total RAM:    {ram_gb} GB")
    else:
        print("  * Total RAM:    NOT VERIFIED")

    if os_name != "Windows":
        warnings.append(f"Operating system is {os_name}; project was built and tested for Windows.")

    if arch != "64bit":
        critical_failures.append(
            f"Detected {arch} architecture. MediaPipe and OpenCV require 64-bit Python on Windows."
        )

    # ---------------------------------------------------------
    # 2. PYTHON RUNTIME
    # ---------------------------------------------------------
    print("\n[2/6] Python Runtime:")
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    in_venv = sys.prefix != sys.base_prefix

    print(f"  * Version:      Python {py_str}")
    print(f"  * Executable:   {sys.executable}")
    print(f"  * Virtual Env:  {'Active (' + sys.prefix + ')' if in_venv else 'None (Running in Global Python)'}")

    if not in_venv:
        warnings.append("Not currently running inside a virtual environment (.venv). Using a venv is recommended.")

    if py_ver.major != 3 or py_ver.minor not in (10, 11, 12):
        if py_ver.minor >= 13:
            critical_failures.append(
                f"Python {py_str} is incompatible. MediaPipe has no prebuilt Windows wheels for Python 3.13+. Please use Python 3.12.x."
            )
        else:
            critical_failures.append(
                f"Python {py_str} is below the minimum supported version (Python 3.10+ required)."
            )
    else:
        print("  * Version Gate: PASS (Python 3.10-3.12 supported)")

    # ---------------------------------------------------------
    # 3. REQUIRED PACKAGES
    # ---------------------------------------------------------
    print("\n[3/6] Package Dependency Verification:")
    expected_packages = [
        ("numpy", "1.26.4", True),
        ("mediapipe", "0.10.21", True),
        ("cv2", "4.11.0", True),
        ("pygame", "2.6.1", True),
        ("scipy", "1.17.1", False),
        ("sklearn", "1.9.0", True),
        ("matplotlib", "3.11.0", True),
        ("pyttsx3", "2.99", True),
        ("reportlab", "5.0.0", True),
        ("bcrypt", "5.0.0", True),
        ("cryptography", "49.0.0", True),
    ]

    for mod_name, expected_ver, is_critical in expected_packages:
        try:
            mod = __import__(mod_name)
            ver = getattr(mod, "__version__", "Installed")
            
            # Special check for NumPy 2.x
            if mod_name == "numpy":
                major = int(ver.split(".")[0])
                if major >= 2:
                    critical_failures.append(
                        f"NumPy {ver} is installed. NumPy 2.x breaks MediaPipe. Downgrade to: pip install numpy==1.26.4"
                    )
                    print(f"  [-] numpy:        {ver} (ERROR: Must be <2.0.0, recommended 1.26.4)")
                    continue
            
            print(f"  [+] {mod_name:<13} {ver:<15} (Target: {expected_ver})")
        except ImportError as e:
            if is_critical:
                critical_failures.append(f"Missing required package: {mod_name} ({e})")
                print(f"  [-] {mod_name:<13} MISSING (CRITICAL)")
            else:
                warnings.append(f"Optional package not installed: {mod_name} ({e})")
                print(f"  [!] {mod_name:<13} MISSING (Optional)")

    # Test MediaPipe Hands initialization
    try:
        import mediapipe as mp
        import numpy as np
        hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            max_num_hands=1,
            min_detection_confidence=0.5
        )
        dummy = np.zeros((240, 320, 3), dtype=np.uint8)
        hands.process(dummy)
        hands.close()
        print("  [+] MediaPipe Hands Pipeline: OPERATIONAL")
    except Exception as e:
        critical_failures.append(f"MediaPipe Hands pipeline failed initialization: {e}")
        print(f"  [-] MediaPipe Hands Pipeline: FAILED ({e})")

    # ---------------------------------------------------------
    # 4. HARDWARE: CAMERA & SENSORS
    # ---------------------------------------------------------
    print("\n[4/6] Hardware Diagnostics (Webcam):")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            if ret and frame is not None:
                print(f"  [+] Camera Detected: Index 0")
                print(f"  [+] Resolution:      {w}x{h} @ {fps:.1f} FPS")
                print(f"  [+] Frame Capture:   SUCCESS")
            else:
                warnings.append("Camera index 0 opened but could not read frame. Another app may be using the camera.")
                print("  [!] Camera opened but frame capture failed.")
        else:
            warnings.append("No accessible camera found at index 0. Ensure webcam is connected and not blocked by privacy settings.")
            print("  [!] No webcam accessible at index 0.")
    except Exception as e:
        warnings.append(f"Camera check encountered an exception: {e}")
        print(f"  [!] Camera check failed: {e}")

    # ---------------------------------------------------------
    # 5. DATABASE & SECURITY KEYS
    # ---------------------------------------------------------
    print("\n[5/6] Database & Cryptographic Key Safety:")
    db_file = "rehab_data.db"
    key_file = "secret.key"

    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as kf:
                key_data = kf.read().strip()
            if len(key_data) == 32:
                print(f"  [+] Cryptographic Key:  {key_file} present (Valid 256-bit AES key)")
            else:
                warnings.append(f"secret.key size is {len(key_data)} bytes (expected 32 bytes).")
                print(f"  [!] Cryptographic Key:  {key_file} present but unexpected size ({len(key_data)} bytes)")
        except Exception as e:
            warnings.append(f"Error reading secret.key: {e}")
            print(f"  [!] Cryptographic Key:  Error reading ({e})")
    else:
        print(f"  [*] Cryptographic Key:  {key_file} not found (A new key will be auto-generated on first run)")

    if os.path.exists(db_file):
        try:
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            integrity = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
            table_count = cursor.fetchone()[0]
            sessions_count = 0
            try:
                cursor.execute("SELECT count(*) FROM sessions;")
                sessions_count = cursor.fetchone()[0]
            except Exception:
                pass
            conn.close()
            print(f"  [+] Database File:      {db_file} present")
            print(f"  [+] SQLite Integrity:   {integrity}")
            print(f"  [+] Schema Tables:      {table_count} tables detected")
            print(f"  [+] Historical Sessions:{sessions_count} sessions recorded")
        except Exception as e:
            critical_failures.append(f"Database {db_file} exists but failed read check: {e}")
            print(f"  [-] Database File:      CORRUPTED OR UNREADABLE ({e})")
    else:
        print(f"  [*] Database File:      {db_file} not present (A clean database schema will be initialized on first run)")

    # ---------------------------------------------------------
    # 6. OPTIONAL SERVICES (OLLAMA LLM)
    # ---------------------------------------------------------
    print("\n[6/6] Optional Services (Virtual Sensei LLM Enhancer):")
    ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        req = urllib.request.Request(f"{ollama_host}/api/tags")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed_models = [m.get("name") for m in data.get("models", [])]
            print(f"  [+] Ollama Service:     REACHABLE ({ollama_host})")
            print(f"  [+] Local Models:       {installed_models if installed_models else 'None pulled yet'}")
            print(f"  [*] LLM Enhancer Mode:  {'ENABLED' if os.getenv('OLLAMA_SENSEI_USE_LLM', '0') == '1' else 'DISABLED (Default rule-based fallback active)'}")
    except Exception:
        print(f"  [*] Ollama Service:     NOT DETECTED (Optional)")
        print(f"  [*] Fallback System:    ACTIVE — Built-in clinical rule engine provides full voice coaching offline.")

    # ---------------------------------------------------------
    # SUMMARY REPORT
    # ---------------------------------------------------------
    print("\n" + "=" * 70)
    print(" DIAGNOSTIC SUMMARY")
    print("=" * 70)

    if not critical_failures and not warnings:
        print(" STATUS: EXCELLENT (All checks passed with zero issues)")
    elif not critical_failures:
        print(f" STATUS: READY WITH WARNINGS ({len(warnings)} non-critical note(s))")
        for w in warnings:
            print(f"   * WARNING: {w}")
    else:
        print(f" STATUS: FAILED ({len(critical_failures)} critical issue(s) detected)")
        for f in critical_failures:
            print(f"   * CRITICAL: {f}")
        print("\n Recommended Fixes:")
        print("   1. Ensure Python 3.12 64-bit is installed (https://www.python.org/downloads/)")
        print("   2. Run: setup_windows.bat to configure a clean virtual environment")
        print("   3. Run: pip install -r requirements.txt")

    print("=" * 70)
    return 0 if not critical_failures else 1


if __name__ == "__main__":
    sys.exit(run_diagnostics())
