# Scientific Reproducibility Protocol & Environment Specification

> **AI Hand Rehabilitation System / Zero-Keyboard AI Physiotherapy System**  
> *Documentation for Exact Experimental & Clinical Replication*

This document provides the definitive specifications required to reproduce the experimental setup, kinematic calculations, machine learning predictions, and clinical telemetry on any secondary Windows workstation.

---

## 1. Software Environment Specification

All research findings, kinematic evaluations, and latency benchmarks were recorded on the following verified software stack:

| Component | Verified Version | Purpose | Compatibility Constraints |
| :--- | :--- | :--- | :--- |
| **Operating System** | Windows 10 / 11 (64-bit) | Host OS | Tested on Windows 10 Build 19045 |
| **Python Runtime** | **3.12.10 (64-bit AMD64)** | Application Runtime | Must be Python 3.10–3.12 (64-bit). **Python 3.13 is NOT supported** by MediaPipe. |
| **NumPy** | **1.26.4** | Array & Matrix Math | **NumPy 1.x is strictly required.** NumPy >= 2.0.0 breaks MediaPipe C-extensions. |
| **MediaPipe** | **0.10.21** | 21 3D Hand Landmarks | Official Google MediaPipe binary wheel (`cp312-win_amd64`). |
| **OpenCV** | **4.11.0.86** | Camera capture & Vision | Direct camera capture via MSMF backend @ 640x480. |
| **Pygame** | **2.6.1** | UI & Game Render Loop | SDL 2.28.4 backend for zero-keyboard interaction. |
| **Scikit-Learn** | **1.9.0** | Recovery Regression | Linear regression models in `clinical_modules.py`. |
| **SciPy** | **1.17.1** | Numerical Kernels | Underlying scikit-learn dependency. |
| **Matplotlib** | **3.11.0** | Clinical Charts | `Agg` headless rendering for dashboard & export. |
| **pyttsx3** | **2.99** | Speech Synthesis (TTS) | Offline Windows SAPI5 voice engine. |
| **pypiwin32** | **223** | Windows COM Bridge | Required by pyttsx3 on Windows. |
| **ReportLab** | **5.0.0** | PDF Clinical Reports | Generation of authentic clinical session reports. |
| **Bcrypt** | **5.0.0** | Clinician Auth | Password hashing for therapist dashboard access. |
| **Cryptography** | **49.0.0** | Deterministic AES | HIPAA-compliant deterministic encryption of PII. |

---

## 2. Hardware Environment Specification

| Component | Minimum Specification | Recommended Specification | Verified Test Machine |
| :--- | :--- | :--- | :--- |
| **Processor (CPU)** | Intel Core i3 (7th Gen+) or AMD Ryzen 3 | Intel Core i5/i7 (8th Gen+) or AMD Ryzen 5/7 | Intel Core 64-bit AMD64 |
| **Architecture** | x86_64 / AMD64 (64-bit) | x86_64 / AMD64 (64-bit) | 64-bit WindowsPE |
| **System Memory (RAM)**| 4 GB physical RAM | 8 GB or 16 GB DDR4/DDR5 | 8.0 GB RAM |
| **Webcam / Sensor** | Integrated or USB 2.0 webcam | USB 3.0 HD Webcam | 640x480 @ 30.0 FPS |
| **Audio Output** | Standard speakers or headphones | Stereo audio output | Windows default audio device |
| **Disk Storage** | 2.5 GB free space | 10 GB free space | SSD storage |

---

## 3. Artificial Intelligence & Biomechanical Pipeline

### A. Computer Vision (Hand Tracking)
- **Framework**: Google MediaPipe Hands (v0.10.21).
- **Landmarks**: 21 three-dimensional coordinate vectors $(x, y, z)$ tracked at 30–60 FPS.
- **Tracking Confidence**: Detection threshold $= 0.5$, Tracking threshold $= 0.5$.
- **Coordinate Space**: Normalized coordinates mapped to the $1280 \times 720$ display buffer.

### B. Adaptive AI Engine
- **Engine**: Rule-based explainable inference engine (`adaptive_ai_engine.py`).
- **Difficulty Tiers**: 5 tiers adjusting target scale ($0.7 \times$ to $1.3 \times$), speed scale ($0.8 \times$ to $1.4 \times$), and hold durations ($1.0\text{s}$ to $2.5\text{s}$).
- **Prescription Generation**: Deterministic mathematical formulation incorporating previous accuracy, Range of Motion (ROM), fatigue index, and compensation score.

### C. Virtual Sensei Voice Guidance
- **Deterministic Core**: Fully offline clinical rule engine (`generate_rule_based_coaching()`).
- **Optional Local LLM**: Local Ollama service (`qwen2.5:0.5b` or `smollm2:135m`) communicating over `http://127.0.0.1:11434`.
- **Fail-Safe Mechanism**: If Ollama is offline or uninstalled, the system automatically falls back to deterministic rule coaching without user interruption.

---

## 4. Data Environment & Cryptography

### A. Database Storage
- **File**: `rehab_data.db` (SQLite 3 relational database).
- **Tables**: 18 tables tracking patients, sessions, compensation events, clinical summaries, and adaptive prescriptions.
- **Portability Protocol**: To migrate existing research history to another laptop, copy **both** `rehab_data.db` **and** `secret.key`.

### B. Deterministic Encryption
- **Standard**: AES-256 in CBC mode with SHA-256 derived Initialization Vectors.
- **Key File**: `secret.key` (32 bytes).
- **Purpose**: Enables deterministic SQL `JOIN` and `WHERE` queries on patient identifiers while protecting patient privacy according to HIPAA guidelines.

### C. Dataset Export
- **Script**: `python research_export.py`
- **Output**: `research_dataset.csv`
- **Pseudonymization**: Deterministic patient mapping (`P001`, `P002`, ...) with quality flags (`VALID`, `MOTOR_FAILURE`, `TRACKING_ERROR`, `ABORTED_SESSION`).

---

## 5. Execution Commands for Replication

### Quick Automated Replication:
```cmd
setup_windows.bat
run_project.bat
```

### Manual Replication:
```cmd
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python diagnose_environment.py
python -m unittest discover tests
python main.py
```

### Research Dataset Generation:
```cmd
python research_export.py --input rehab_data.db --output research_dataset.csv
```
