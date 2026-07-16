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
| 📊 | **Therapist Dashboard** | Web interface for doctors to manage patients and view analytics |
| 🔐 | **Dual Authentication** | Login using Clinical ID or Guest Mode (Name & Age) |
| 🎮 | **Level-Based Progression** | Eight exercise levels from warm-up to complex forearm rotation and smart assembly |
| 🦾 | **Biomechanical Compensation** | Real-time posture tracking (shoulder elevation/abduction, elbow drift, trunk lean) |
| 🧠 | **Clinical Decision & Twin** | Machine learning recovery predictions, health scoring, and digital twin simulation |
| 🗣️ | **Interactive Virtual Sensei** | Context-aware voice guidance powered by rules and optional local LLM polish |

## 🚀 System Architecture

The project is split into two integrated components: the **Rehabilitation Game** (patient runtime) and the **Therapist Dashboard** (clinician portal), supported by modular AI, biomechanics, and clinical analysis layers.

### Adaptive AI Rehabilitation Platform Flow
Patient exercise data flows through session metrics collection into the local SQLite database. Recovery prediction and forearm classification feed the `AdaptiveRehabEngine`, which generates the rehabilitation prescription: difficulty tier, target size, speed scale, ROM requirement, repetition count, hold duration, rotation tolerance, risk level, recovery state, readiness score, and therapist recommendations.

The Virtual Sensei consumes the current session, previous session history, recovery prediction, forearm classification, readiness score, risk level, and adaptive prescription to generate deterministic coaching. Optional Ollama support is limited to rewriting that finished coaching message for clearer communication. The local LLM must not change prescriptions, difficulty, risk scores, safety decisions, diagnosis, medication advice, or progression recommendations.

All adaptive prescriptions and Virtual Sensei audit details are stored in SQLite for therapist review, including decision source, rule-based safety logic, optional LLM enhancement status, rationale, trigger, and timestamp.

### Component Directory Map
* **Patient Application Core**
  * `zero_keyboard_physio.py`: Main Pygame patient game loop, camera thread, voice coaching feedback, ROM calibration, and levels 1-8.
  * `ui_components.py`: Reusable Pygame user interface buttons, dashboard cards, and navigation rings.
  * `hand_rehab_assistant.py`: Auxiliary guidance text helper for interactive patient UI.
* **Clinician Portal Core**
  * `therapist_dashboard.py`: Lightweight HTTP server dashboard rendering patient summaries, trends, notes, twin simulation projections, and PDF export.
  * `dashboard_auth_addon.py`: Session helper library managing dashboard login and authentication states.
* **Adaptive AI & Analytics Core**
  * `adaptive_ai_engine.py`: Adaptive difficulty engine computing real-time prescription configurations and risk classifications.
  * `digital_twin_rehab.py`: Patient digital twin model projecting future recovery windows across custom rehabilitation scenarios (Plans A, B, C).
  * `clinical_intelligence.py`: Diagnostic analytics layer calculating patient health scores, recovery phases, and highlighting clinical alert triggers.
  * `upper_limb_analysis.py`: Biomechanical pose engine parsing joint angles to measure shoulder, elbow, and trunk compensation.
  * `llm_wrapper.py`: Thread-safe interface querying local Ollama LLMs for semantic enhancement of Virtual Sensei feedback.

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
*(This will automatically open the local dashboard URL printed in the terminal, usually http://127.0.0.1:8080. `start_dashboard.bat` launches on http://127.0.0.1:8081.)*

**4. Launch the Rehabilitation Session**
```bash
python zero_keyboard_physio.py
```

> [!WARNING]
> A functioning webcam is required for the Rehabilitation Session. Ensure adequate lighting and camera visibility of both hand and upper torso for optimal landmark tracking.

### 🤖 Optional Local LLM (Ollama) Integration
The Virtual Sensei coaching feedback can optionally be enhanced using a local LLM via [Ollama](https://ollama.com).

1. Install Ollama and pull a supported small model (e.g., Qwen 2.5 0.5B, Smollm2 135M, or Llama 3.2 1B):
   ```bash
   ollama pull qwen2.5:0.5b
   ```
2. Enable local LLM coaching enhancement and specify configuration details by setting environment variables before running the game:
   ```cmd
   :: Enable LLM coaching message polishing (0 = off, 1 = on)
   set OLLAMA_SENSEI_USE_LLM=1
   :: Select model name (options: qwen2.5:0.5b, smollm2:135m, llama3.2:1b, llama3)
   set OLLAMA_SENSEI_MODEL=qwen2.5:0.5b
   :: Set maximum query timeout in seconds
   set OLLAMA_SENSEI_TIMEOUT=8
   ```

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
- **AI-Driven Smart Object Assembly:** As a future enhancement, the system can include an AI-driven rehabilitation game called Smart Object Assembly. In this game, patients perform therapeutic hand, wrist, and forearm movements to assemble virtual objects such as houses, machines, or robotic structures. Different rehabilitation exercises, including wrist flexion, extension, pronation, supination, and pinch movements, are mapped to specific assembly actions. The game difficulty can be automatically adjusted based on the patient's recovery progress and previous performance. This approach can improve patient engagement, support advanced hand and forearm rehabilitation, and provide a novel adaptive rehabilitation framework suitable for future research and potential patent development.


## 🔒 Security Posture

This system is designed as a **local prototype** and is currently rated for non-clinical research and development. 
- **The Good:** The system natively prevents network exposure by binding the web dashboard exclusively to `127.0.0.1`. It also utilizes parameterized database queries to prevent SQL Injection, and sanitizes all HTML outputs to prevent Cross-Site Scripting (XSS).
- **The Bad:** The local SQLite database (`rehab_data.db`) is not encrypted at rest. Furthermore, the Therapist Dashboard currently lacks a login portal (no username/password required). 
- **Compliance:** Due to the lack of at-rest encryption and dashboard authentication, this software is **not yet HIPAA/GDPR compliant** and should not be used to store real Protected Health Information (PHI) outside of an encrypted, access-controlled environment.

## 👨‍💻 Author

<div align="center">

**Varad Script**
*Developed as an MCA Major Project*

[![GitHub](https://img.shields.io/badge/GitHub-VaradScript-181717?style=flat-square&logo=github)](https://github.com/VaradScript)

*Made with 🖐️ for patients on the road to recovery.*

</div>


