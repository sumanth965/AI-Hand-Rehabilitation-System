<div align="center">

<svg width="100" height="100" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="40" cy="40" r="38" stroke="#0f9d82" stroke-width="2" fill="none" opacity=".3"/>
  <circle cx="40" cy="40" r="32" fill="#e0f5f0"/>
  <circle cx="40" cy="8" r="2.5" fill="#0f9d82" opacity=".6"/>
  <circle cx="72" cy="40" r="2.5" fill="#0f9d82" opacity=".6"/>
  <circle cx="40" cy="72" r="2.5" fill="#0f9d82" opacity=".6"/>
  <circle cx="8" cy="40" r="2.5" fill="#0f9d82" opacity=".6"/>
  <line x1="40" y1="8" x2="40" y2="15" stroke="#0f9d82" stroke-width="1.5" opacity=".4"/>
  <line x1="72" y1="40" x2="65" y2="40" stroke="#0f9d82" stroke-width="1.5" opacity=".4"/>
  <line x1="40" y1="72" x2="40" y2="65" stroke="#0f9d82" stroke-width="1.5" opacity=".4"/>
  <line x1="8" y1="40" x2="15" y2="40" stroke="#0f9d82" stroke-width="1.5" opacity=".4"/>
  <rect x="28" y="42" width="24" height="18" rx="5" fill="#0f9d82"/>
  <rect x="29" y="26" width="6" height="20" rx="3" fill="#0f9d82"/>
  <rect x="37" y="22" width="6" height="24" rx="3" fill="#0f9d82"/>
  <rect x="45" y="26" width="6" height="20" rx="3" fill="#0f9d82"/>
  <rect x="52" y="30" width="5" height="15" rx="2.5" fill="#1bc9a4" opacity=".85"/>
  <rect x="18" y="30" width="6" height="13" rx="3" fill="#1bc9a4" opacity=".85"/>
  <rect x="20" y="36" width="12" height="6" rx="3" fill="#1bc9a4" opacity=".85"/>
  <line x1="28" y1="52" x2="52" y2="52" stroke="#7ee8d3" stroke-width="1" stroke-dasharray="2,2" opacity=".8"/>
  <circle cx="32" cy="44" r="1.5" fill="#7ee8d3" opacity=".9"/>
  <circle cx="40" cy="43" r="1.5" fill="#7ee8d3" opacity=".9"/>
  <circle cx="48" cy="44" r="1.5" fill="#7ee8d3" opacity=".9"/>
</svg>

# AI Hand Rehabilitation System

> *Healing through play — gesture-powered physiotherapy, zero keyboards required.*

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-CV-0097A7?style=for-the-badge&logo=google&logoColor=white)](https://mediapipe.dev)
[![Pygame](https://img.shields.io/badge/Pygame-UI-1C1C1C?style=for-the-badge&logo=pygame&logoColor=white)](https://pygame.org)
[![OpenCV](https://img.shields.io/badge/OpenCV-Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)

A gesture-controlled physiotherapy application built for patients recovering from hand injuries.
Navigate menus, play games, and track your recovery — **using only your hands.**

</div>

## ✨ Key Features

| | Feature | Description |
|---|---|---|
| 🖱️ | **Zero Keyboard Navigation** | Hover-to-Select menus powered entirely by hand gestures |
| 📡 | **Real-Time Feedback** | Mirrored webcam feed with MediaPipe landmarks overlaid |
| 🎨 | **Premium Dynamic Dashboard UI** | Beautiful, responsive web portal with StudyFlow-inspired dark blue aesthetics, sidebar animations, and seamless dark/light mode toggling |
| 📊 | **Therapist Dashboard** | Comprehensive web interface featuring Patient Management, Session Analytics, Digital Twin simulation, and Role-Based Access Control |
| 🔐 | **Secure Authentication** | Full login system with session tokens and secure password verification for Clinicians |
| 🎮 | **14-Level Progressive Exercises** | Fourteen clinical exercise levels ranging from gross motor warm-ups to fine-motor pinch, forearm rotation, precision pathway tracing, in-hand manipulation (coin vault and card shift challenge), finger isolation, and wrist flexion-extension control |
| 🦾 | **Biomechanical Compensation** | Real-time posture tracking (shoulder elevation/abduction, elbow drift, trunk lean) |
| 🧠 | **Clinical Decision & Twin** | Machine learning recovery predictions, health scoring, and digital twin simulation |
| 🗣️ | **Interactive Virtual Sensei** | Context-aware voice guidance powered by rules and optional local LLM polish |

## 📚 Research Documentation

For the complete scientific methodology, mathematical formulations, master variable dictionary, experimental protocol, statistical analysis plan, and research paper blueprint:

👉 **See [`RESEARCH_ANALYSIS.md`](RESEARCH_ANALYSIS.md)**

---

## 🚀 System Architecture

The project is split into two integrated components: the **Rehabilitation Game** (patient runtime) and the **Therapist Dashboard** (clinician portal), supported by modular AI, biomechanics, and clinical analysis layers.

### Adaptive AI Rehabilitation Platform Flow
Patient exercise data flows through session metrics collection into the local SQLite database. Recovery prediction and forearm classification feed the `AdaptiveRehabEngine`, which generates the rehabilitation prescription: difficulty tier (1–5), target scale, speed scale, ROM requirement, repetition count, hold duration, rotation tolerance, risk level, recovery state, readiness score, and therapist recommendations.

The Virtual Sensei consumes the current session, previous session history, recovery prediction, forearm classification, readiness score, risk level, and adaptive prescription to generate deterministic coaching. Optional Ollama support is strictly limited to rewriting that finished coaching message for clearer spoken communication.

### Component Directory Map
* **Patient Application Core**
  * `zero_keyboard_physio.py`: Main Pygame patient game loop, camera thread, voice coaching feedback, ROM calibration, and 10 clinical exercise levels.
  * `ui_components.py`: Reusable Pygame user interface buttons, dashboard cards, and navigation rings.
  * `hand_rehab_assistant.py`: Auxiliary guidance text helper for interactive patient UI.
* **Clinician Portal Core**
  * `admin_dashboard/`: Complete modular dashboard backend package containing `server.py`, `renderer.py`, `database.py`, `auth.py`, and organized page components. Includes a custom frontend framework with dark mode layout.
  * `therapist_dashboard.py`: Lightweight entry point to launch the modular admin dashboard server.
* **Adaptive AI & Analytics Core**
  * `adaptive_ai_engine.py`: Explainable rule-based difficulty engine computing real-time prescription configurations and risk classifications across Tiers 1–5.
  * `digital_twin_rehab.py`: Patient digital twin model projecting future recovery windows.
  * `clinical_intelligence.py`: Diagnostic analytics layer calculating patient health scores.
  * `upper_limb_analysis.py`: Biomechanical pose engine parsing joint angles to measure compensation.
  * `llm_wrapper.py`: Thread-safe interface querying optional local Ollama LLMs for coaching message phrasing.
* **Research & Data Validation Core (V1 Upgrade)**
  * `research_export.py`: CLI and automated tool extracting authentic SQLite sessions into pseudonymized (`P001`), quality-flagged `research_dataset.csv`.
  * `tests/test_accuracy.py`: Unit test suite verifying mathematical edge cases, zero-attempt handling (`NULL`), and tracking quality thresholds.
  * `research_validation/`: Protocols, data dictionaries, software test reports, and clinician evaluation templates.

## 📦 Installation on Another Windows Laptop

To deploy and execute this project on another Windows computer with full environment parity and scientific reproducibility, follow the guide below.

### 📋 Prerequisites & Hardware Requirements
* **Operating System**: Windows 10 or Windows 11 (64-bit strictly required).
* **Python**: Python **3.12** 64-bit recommended (Supported range: Python **3.10.x to 3.12.x**).
  > [!IMPORTANT]
  > **Do NOT install Python 3.13**. Google MediaPipe does not provide Windows precompiled binary wheels for Python 3.13+.
  > **Do NOT install 32-bit Python**. MediaPipe and OpenCV binary wheels are 64-bit only.
* **Webcam**: Standard USB or integrated webcam (minimum 640x480 @ 30 FPS).
* **Visual C++ Runtime**: [Microsoft Visual C++ 2015-2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe) installed.

---

### ⚡ Quick Automated Setup (Recommended)

1. **Clone or copy the project folder**:
   ```cmd
   git clone https://github.com/Sumanth965/AI-Hand-Rehabilitation-System.git
   cd AI-Hand-Rehabilitation-System
   ```

2. **Run the automated setup script**:
   ```cmd
   setup_windows.bat
   ```
   *This script verifies your Python version, creates an isolated `.venv`, upgrades pip, installs pinned dependencies from `requirements.txt`, and verifies all computer vision pipelines.*

3. **Launch the application**:
   ```cmd
   run_project.bat
   ```
   *To launch the Therapist Admin Dashboard instead:*
   ```cmd
   run_project.bat --dashboard
   ```

---

### 🛠️ Manual Setup Procedure

If you prefer to configure the virtual environment manually:

```cmd
:: 1. Create a 64-bit virtual environment
python -m venv .venv

:: 2. Activate the virtual environment
call .venv\Scripts\activate.bat

:: 3. Upgrade pip and wheel
python -m pip install --upgrade pip setuptools wheel

:: 4. Install exact pinned dependencies
pip install -r requirements.txt

:: 5. Run full environment diagnostics
python diagnose_environment.py

:: 6. Launch the Patient Application
python main.py

:: 7. Launch the Therapist Dashboard (Port 8081)
python main.py --dashboard
```

---

### 🩺 System Diagnostics

Run the non-destructive environment diagnostic script at any time to verify hardware, vision pipelines, and database integrity:
```cmd
python diagnose_environment.py
```
This script checks:
* Windows build and architecture (64-bit validation)
* Python version gate (3.10–3.12)
* Pinned dependency status (including strict NumPy 1.x validation)
* MediaPipe Hands pipeline operational test
* Webcam hardware detection, frame capture, resolution, and FPS
* Database integrity (`rehab_data.db`) and cryptographic key validation (`secret.key`)
* Optional Ollama LLM service reachability (with offline rule-based fallback verification)

---

### 🗄️ Database & Research Data Portability

* **Clean New Installation**: A fresh `rehab_data.db` and AES `secret.key` are generated automatically on first launch.
* **Transferring Existing Research Data**: If copying patient history from a primary laptop, you must copy **both**:
  1. `rehab_data.db` (SQLite relational database)
  2. `secret.key` (256-bit AES encryption key)
  *If `secret.key` is omitted, patient identifiers will not decrypt correctly.*
* **Exporting Research Data**:
  ```cmd
  python research_export.py --db rehab_data.db --output research_dataset.csv
  ```

---

### 🔍 Troubleshooting

| Issue / Error Message | Cause | Exact Solution |
| :--- | :--- | :--- |
| `ERROR: Could not find a version that satisfies the requirement mediapipe` | Python 3.13 installed, or 32-bit Python installed. | Install [Python 3.12.10 (64-bit)](https://www.python.org/downloads/release/python-31210/) and check "Add python.exe to PATH". |
| `AttributeError: _ARRAY_API not found` or MediaPipe crash on import | NumPy 2.x was installed by an unpinned dependency. | Run: `pip install "numpy==1.26.4"`. NumPy 1.x is strictly required for MediaPipe compatibility. |
| `Camera opened but frame capture failed` or black screen | Windows Camera privacy blocked or another app (Zoom/Teams) is using the webcam. | Open Windows **Settings > Privacy > Camera**, enable "Allow desktop apps to access your camera", and close conferencing apps. |
| `ModuleNotFoundError: No module named 'win32com'` | `pyttsx3` requires Windows COM components. | Run: `pip install pypiwin32==223`. |
| `ImportError: DLL load failed while importing _sqlite3` or C runtime error | Missing Microsoft Visual C++ runtime. | Download and install the [x64 VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe). |
| Patient names appear as ciphertext or decryption error | `rehab_data.db` copied without its companion `secret.key`. | Copy the matching `secret.key` from the source machine into the project root folder. |
| `pygame.error: DirectSoundCreate: No audio device found` | No speakers/headphones connected or audio service disabled. | Plug in headphones or enable Windows Audio in Services (`services.msc`). |
| `Ollama Service: NOT DETECTED` | Ollama is not installed or not running locally. | **No action required.** The system automatically uses the built-in deterministic clinical rule engine for voice coaching. |

---

## ⚙️ How It Works

1. **Capture** — Webcam frames are captured and mirrored in real time (30/60 FPS).
2. **Detect** — MediaPipe Hands identifies 21 hand landmarks; MediaPipe Pose tracks upper limb joints.
3. **Analyze** — Knuckle angles, wrist rotation/deviation, jerk-derived smoothness, and compensation metrics are computed.
4. **Adapt** — The game adjusts 10 difficulty parameters (target size, speed, hold thresholds, tolerances) based on active AI prescriptions.
5. **Log** — Metrics, prescriptions, notes, and twins are persisted to SQLite with data quality flags (`VALID`, `NO_VALID_ATTEMPTS`, `TRACKING_ERROR`).
6. **Review** — Therapists review recovery trends, inspect explainable AI rationales, and simulate rehabilitation strategy projections on the web dashboard.

## ⚠️ Limitations & Scientific Notice

While this project provides a strong proof-of-concept for AI-powered rehabilitation, it has limitations:
- **Environmental Dependency:** MediaPipe requires adequate lighting and clear contrast; poor lighting can drop the tracking frame rate below 50% (flagged as `TRACKING_ERROR`).
- **2D Depth Limitations:** Using a standard monocular webcam means depth estimation is inferred; measurements are software-derived heuristic estimates, not gold-standard goniometric data.
- **Data Portability & Encryption:** Data is stored locally in SQLite (`rehab_data.db`). While patient names are deterministically encrypted, the database is not encrypted at rest.

## 🔬 Research-Grade Telemetry & Kinematics

In the **Research-Grade Accuracy & Data Collection V1** upgrade, the telemetry and validation pipelines were standardized:

### 1. Kinematic Quality Evaluation Model
We evaluate movement quality using four kinematic sub-metrics over the duration of the session:
* **Smoothness Score ($S_m$)**: Calculated using the time-derivative of acceleration (jerk) over the index tip coordinate stream, normalized via exponential decay:
  $$S_m = 100 \times e^{-0.08 \cdot \overline{\text{Jerk}}}$$
* **Accuracy Score ($A_c$)**: Ratio of hit attempts to total targets during active gameplay ($A_c = \frac{\text{Hits}}{\text{Attempts}} \times 100$). Stored as `NULL` if 0 attempts occur.
* **Range of Motion Achievement ($R_o$)**: Flexion/extension joint angle performance normalized against the patient's calibrated baseline maximum ROM.
* **Hold Stability ($H_s$)**: Calculated by computing the spatial standard deviation of index finger coordinates during static holding periods:
  $$H_s = 100 \times e^{-0.04 \cdot \sigma_{\text{hold}}}$$
* **Overall Movement Quality ($Q_m$)**:
  $$Q_m = \frac{S_m + A_c + R_o + H_s}{4}$$

### 2. Patient Readiness & Closed-Loop Adaptation
Today's recommended game difficulty is decided adaptively by computing a Patient Readiness Score ($R_p \in [0, 100]$):
$$R_p = 30 \left(\frac{A_c}{100}\right) + 22 \left(\frac{\text{ROM}}{90}\right) + 16 \left(\frac{10 - \text{Pain}}{10}\right) + 12 \times \text{Consistency} + 10 \times S_m + 6 \times (1 - \text{Fatigue}) + 4 \times Q_m$$

* **Progression Actions:**
  * **Advance (Tiers 4–5)**: $R_p \ge 72$ with stable/improving ROM and accuracy trends.
  * **Maintain (Tier 3)**: $42 \le R_p < 72$ to consolidate motor control.
  * **Support (Tier 2)**: $R_p < 42$ providing assisted target scaling.
  * **Regress (Tier 1)**: Triggered immediately by safety blocks (Pain $\ge 7$, Fatigue $\ge 0.75$, or acute ROM drop $\le -8^\circ$).

## 🔒 Security Posture

This system is designed as a **local prototype** and is currently rated for non-clinical research and development. 
- **The Good:** The system natively prevents network exposure by binding the web dashboard exclusively to `127.0.0.1`. The dashboard architecture features a fully functional login system with secure session tokens, password verification, and role-based access control. It utilizes parameterized database queries to prevent SQL Injection and sanitizes HTML outputs to prevent Cross-Site Scripting (XSS).
- **The Bad:** The local SQLite database (`rehab_data.db`) is not encrypted at rest. 
- **Compliance:** Due to the lack of at-rest encryption, this software is **not yet HIPAA/GDPR compliant** and should not be used to store real Protected Health Information (PHI) outside of an encrypted, access-controlled environment.

## 👨‍💻 Author

<div align="center">

**Varad Script**
*Developed as an MCA Major Project*

[![GitHub](https://img.shields.io/badge/GitHub-VaradScript-181717?style=flat-square&logo=github)](https://github.com/VaradScript)

*Made with 🖐️ for patients on the road to recovery.*

</div>
