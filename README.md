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
| 🎮 | **Level-Based Progression** | Eight exercise levels from warm-up to complex forearm rotation and smart assembly |
| 🦾 | **Biomechanical Compensation** | Real-time posture tracking (shoulder elevation/abduction, elbow drift, trunk lean) |
| 🧠 | **Clinical Decision & Twin** | Machine learning recovery predictions, health scoring, and digital twin simulation |
| 🗣️ | **Interactive Virtual Sensei** | Context-aware voice guidance powered by rules and optional local LLM polish |

## 🚀 System Architecture

The project is split into two integrated components: the **Rehabilitation Game** (patient runtime) and the **Therapist Dashboard** (clinician portal), supported by modular AI, biomechanics, and clinical analysis layers.

### Adaptive AI Rehabilitation Platform Flow
Patient exercise data flows through session metrics collection into the local SQLite database. Recovery prediction and forearm classification feed the `AdaptiveRehabEngine`, which generates the rehabilitation prescription: difficulty tier, target size, speed scale, ROM requirement, repetition count, hold duration, rotation tolerance, risk level, recovery state, readiness score, and therapist recommendations.

The Virtual Sensei consumes the current session, previous session history, recovery prediction, forearm classification, readiness score, risk level, and adaptive prescription to generate deterministic coaching. Optional Ollama support is limited to rewriting that finished coaching message for clearer communication.

### Component Directory Map
* **Patient Application Core**
  * `zero_keyboard_physio.py`: Main Pygame patient game loop, camera thread, voice coaching feedback, ROM calibration, and levels 1-8.
  * `ui_components.py`: Reusable Pygame user interface buttons, dashboard cards, and navigation rings.
  * `hand_rehab_assistant.py`: Auxiliary guidance text helper for interactive patient UI.
* **Clinician Portal Core**
  * `admin_dashboard/`: Complete modular dashboard backend package containing `server.py`, `renderer.py`, `database.py`, `auth.py`, and organized page components. Includes a custom frontend framework with highly optimized dark mode layout.
  * `therapist_dashboard.py`: Lightweight entry point to launch the modular admin dashboard server.
* **Adaptive AI & Analytics Core**
  * `adaptive_ai_engine.py`: Adaptive difficulty engine computing real-time prescription configurations and risk classifications.
  * `digital_twin_rehab.py`: Patient digital twin model projecting future recovery windows.
  * `clinical_intelligence.py`: Diagnostic analytics layer calculating patient health scores.
  * `upper_limb_analysis.py`: Biomechanical pose engine parsing joint angles to measure compensation.
  * `llm_wrapper.py`: Thread-safe interface querying local Ollama LLMs.

## 📦 Installation

**1. Clone the repository**
```bash
git clone https://github.com/Sumanth965/AI-Hand-Rehabilitation-System.git
cd AI-Hand-Rehabilitation-System
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Launch the Therapist Dashboard**
```bash
python therapist_dashboard.py
```
*(This will automatically open the local dashboard URL printed in the terminal, usually http://127.0.0.1:8080)*

**4. Launch the Rehabilitation Session**
```bash
python zero_keyboard_physio.py
```

> [!WARNING]
> A functioning webcam is required for the Rehabilitation Session. Ensure adequate lighting and camera visibility of both hand and upper torso for optimal landmark tracking.

## ⚙️ How It Works

1. **Capture** — Webcam frames are captured and mirrored in real time.
2. **Detect** — MediaPipe Hands identifies 21 hand landmarks; MediaPipe Pose tracks upper limb joints.
3. **Analyze** — Joint angles and deviation paths are computed. Compensation scores are generated for the upper limb.
4. **Adapt** — The game adjusts difficulty (target size, speed, hold thresholds) based on active AI prescriptions.
5. **Log** — Metrics, prescriptions, notes, and twins are persisted to SQLite.
6. **Review** — Therapists review recovery trends and simulate rehabilitation strategy projections on the web dashboard.

## ⚠️ Limitations & Future Improvements

While this project provides a strong proof-of-concept for AI-powered rehabilitation, it has some limitations to be addressed in future versions:
- **Environmental Dependency:** MediaPipe requires adequate lighting and clear contrast; poor lighting can drop the tracking frame rate.
- **2D Depth Limitations:** Using a standard webcam means depth estimation is inferred. Future improvements could integrate 3D depth cameras (like Intel RealSense) for true spatial accuracy.
- **Data Portability:** Currently, all data is stored locally in SQLite. Future versions aim to implement a secure, cloud-based PostgreSQL or Firebase backend for cross-device syncing.

## 🔬 Clinical Research & Advanced Kinematic Analytics

In this version, we introduced advanced clinical telemetry, research validation metrics, and publication-ready graphs:

### 1. Kinematic Quality Evaluation Model
We evaluate movement quality using four kinematic sub-metrics over the duration of the session:
* **Smoothness Score ($S_m$)**: Calculated using the time-derivative of acceleration (jerk) over the index tip coordinate stream, normalized via exponential decay:
  $$S_m = 100 \times e^{-\lambda_j \cdot \overline{\text{Jerk}}}$$
* **Accuracy Score ($A_c$)**: Ratio of hit attempts to total targets during active gameplay.
* **Range of Motion Achievement ($R_o$)**: Flexion/extension joint angle performance normalized against the patient's calibrated baseline maximum ROM.
* **Hold Stability ($H_s$)**: Calculated by computing the spatial standard deviation of index finger coordinates during static holding periods:
  $$H_s = 100 \times e^{-\lambda_d \cdot \sigma_{\text{hold}}}$$
* **Overall Movement Quality ($Q_m$)**:
  $$Q_m = \frac{S_m + A_c + R_o + H_s}{4}$$

### 2. Patient Clinical Readiness & Difficulty Intelligence
Today's recommended game difficulty is decided adaptively by computing a Patient Readiness Score ($R_p$):
$$R_p = \left( 0.4 \times R_{\text{rom}} + 0.3 \times A_c + 0.3 \times Q_m \right) - P_{\text{pain}} - P_{\text{fatigue}}$$
* Recommended difficulty thresholds:
  * **Easy**: $R_p < 50$
  * **Moderate**: $50 \le R_p < 80$
  * **Hard**: $R_p \ge 80$

## 🔒 Security Posture

This system is designed as a **local prototype** and is currently rated for non-clinical research and development. 
- **The Good:** The system natively prevents network exposure by binding the web dashboard exclusively to `127.0.0.1`. The new dashboard architecture features a fully functional login system with secure session tokens, password verification, and role-based access control. It utilizes parameterized database queries to prevent SQL Injection and sanitizes HTML outputs to prevent Cross-Site Scripting (XSS).
- **The Bad:** The local SQLite database (`rehab_data.db`) is not encrypted at rest. 
- **Compliance:** Due to the lack of at-rest encryption, this software is **not yet HIPAA/GDPR compliant** and should not be used to store real Protected Health Information (PHI) outside of an encrypted, access-controlled environment.

## 👨‍💻 Author

<div align="center">

**Varad Script**
*Developed as an MCA Major Project*

[![GitHub](https://img.shields.io/badge/GitHub-VaradScript-181717?style=flat-square&logo=github)](https://github.com/VaradScript)

*Made with 🖐️ for patients on the road to recovery.*

</div>
