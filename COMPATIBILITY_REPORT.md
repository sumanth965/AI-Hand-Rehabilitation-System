# Compatibility Report & Cross-Laptop Portability Audit

> **System**: AI Hand Rehabilitation System / Zero-Keyboard AI Physiotherapy System  
> **Audit Date**: October 2026  
> **Target Platform**: Windows 10 / Windows 11 (64-bit)

---

## 1. Verified Working Environment

- **Host Operating System**: Windows 10 Home/Pro/Enterprise (Build 19045 tested) / Windows 11
- **Python Version**: `3.12.10` (64-bit AMD64)
- **Architecture**: `x86_64` (WindowsPE 64-bit)
- **C++ Runtime Dependency**: Microsoft Visual C++ 2015–2022 Redistributable (x64)

---

## 2. Dependency Matrix

| Dependency | Required Version Range | Exact Tested Version | Status | Critical Reason |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | `3.10.x` - `3.12.x` (64-bit) | `3.12.10` | **VERIFIED** | Python 3.13 lacks MediaPipe precompiled wheels on Windows. |
| **NumPy** | `<2.0.0` (1.x series) | `1.26.4` | **VERIFIED** | NumPy 2.x breaks MediaPipe C-API (`_ARRAY_API` binary incompatibility). |
| **MediaPipe** | `0.10.14` - `0.10.21` | `0.10.21` | **VERIFIED** | Hand tracking pipeline (`mp.solutions.hands`). |
| **OpenCV** | `>=4.8.0, <=4.11.x` | `4.11.0.86` | **VERIFIED** | Webcam capture, image preprocessing, and mirroring. |
| **Pygame** | `>=2.5.0` | `2.6.1` | **VERIFIED** | SDL 2 graphics render loop and interactive audio. |
| **SciPy** | `>=1.11.0` | `1.17.1` | **VERIFIED** | Scientific math kernels used by scikit-learn. |
| **Scikit-Learn** | `>=1.3.0` | `1.9.0` | **VERIFIED** | Recovery regression in `clinical_modules.py`. |
| **Matplotlib** | `>=3.8.0` | `3.11.0` | **VERIFIED** | Kinematic progress charts generation (`Agg` backend). |
| **pyttsx3** | `>=2.90` | `2.99` | **VERIFIED** | Offline text-to-speech for voice guidance. |
| **pypiwin32** | `>=223` | `223` | **VERIFIED** | Windows SAPI5 COM bridge for pyttsx3. |
| **ReportLab** | `>=4.0.0` | `5.0.0` | **VERIFIED** | Binary PDF clinical reports export. |
| **Bcrypt** | `>=4.0.0` | `5.0.0` | **VERIFIED** | Password hashing for therapist dashboard credentials. |
| **Cryptography** | `>=41.0.0` | `49.0.0` | **VERIFIED** | AES-256 deterministic encryption for patient identifiers. |
| **Ollama** | Optional (Local Service) | `0.5.x` | **OPTIONAL** | Virtual Sensei phrasing enhancement. Fallback rule engine active by default. |

---

## 3. Hardware Requirements

| Hardware Component | Requirement | Tested Specification | Verification Result |
| :--- | :--- | :--- | :--- |
| **Webcam** | USB 2.0 or Integrated Webcam | Integrated 640x480 @ 30.0 FPS | **PASS** (Frame captured successfully) |
| **Processor (CPU)** | 64-bit Dual-Core 2.0 GHz+ | Intel 64-bit AMD64 Processor | **PASS** |
| **RAM** | Minimum 4 GB | 8.0 GB Physical RAM | **PASS** |
| **Audio Output** | Audio device / speakers | Default Windows Audio (SAPI5) | **PASS** (2 voices initialized) |

---

## 4. Known Compatibility Problems & Exact Solutions

### Issue 1: `pip install mediapipe` Fails with "Could not find a version that satisfies the requirement"
- **Root Cause**: The secondary laptop has Python 3.13 installed. Google MediaPipe does not yet provide Windows wheels for Python 3.13.
- **Solution**: Install Python 3.12 64-bit:
  ```cmd
  winget install Python.Python.3.12
  ```
  Or download `python-3.12.10-amd64.exe` from [python.org](https://www.python.org/downloads/release/python-31210/).

---

### Issue 2: `AttributeError: _ARRAY_API not found` or MediaPipe Crash on Launch
- **Root Cause**: A generic `pip install numpy` installed NumPy 2.x (e.g. 2.1 or 2.2). MediaPipe 0.10.x was compiled against NumPy 1.x and crashes on NumPy 2.x.
- **Solution**: Reinstall NumPy 1.26.4:
  ```cmd
  pip install "numpy==1.26.4"
  ```

---

### Issue 3: 32-bit Architecture Mismatch
- **Root Cause**: User downloaded Python 32-bit (x86) instead of 64-bit (x86_64/AMD64). MediaPipe and OpenCV binary wheels are 64-bit only.
- **Solution**: Uninstall 32-bit Python and install Python 3.12 64-bit.

---

### Issue 4: `ModuleNotFoundError: No module named 'win32com'` on Voice Initialization
- **Root Cause**: `pyttsx3` requires Windows COM components provided by `pypiwin32`.
- **Solution**:
  ```cmd
  pip install pypiwin32==223
  ```

---

### Issue 5: Patient Names Show up as Random Ciphertext or Decryption Errors
- **Root Cause**: The database file `rehab_data.db` was copied to the second laptop, but `secret.key` was not copied. `security_utils.py` generated a new random key, preventing decryption of existing records.
- **Solution**: Always copy **both** `rehab_data.db` **and** `secret.key` together when transferring existing patient records between workstations.

---

### Issue 6: Webcam Not Detected / Black Screen
- **Root Cause**: Windows Camera Privacy settings blocking desktop apps, or another application (Zoom, Teams, Skype) holding an exclusive lock on Camera 0.
- **Solution**:
  1. Open Windows **Settings > Privacy > Camera**.
  2. Enable **Allow desktop apps to access your camera**.
  3. Close background conferencing tools.
  4. Run `python diagnose_environment.py` to verify camera capture.
