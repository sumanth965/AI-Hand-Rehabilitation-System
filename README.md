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
| 🎮 | **Level-Based Progression** | Three exercise levels from warm-up to fine motor control |

## 🚀 Two-Part Architecture

The project is split into two integrated components:

### 1. The Rehabilitation Game (`zero_keyboard_physio.py`)
A Pygame-based, interactive computer vision game for patients. It features:
- Hand tracking using Google MediaPipe.
- Exercise routines for Range of Motion, Coordination, and Fine Motor skills.
- Local SQLite database logging (`rehab_data.db`).

### 2. The Therapist Dashboard (`therapist_dashboard.py`)
A web-based portal designed for medical professionals. It features:
- Patient management and unique Clinical ID generation (e.g., `HR001`).
- Analytics charts mapping a patient's recovery progress over time.
- Clinical session notes and downloadable PDF reports.

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
*(This will automatically open http://127.0.0.1:8000 in your browser)*

**4. Launch the Rehabilitation Session**
```bash
python zero_keyboard_physio.py
```

> [!WARNING]
> A functioning webcam is required for the Rehabilitation Session. Ensure adequate lighting for optimal hand detection accuracy.

## ⚙️ How It Works

1. **Capture** — Webcam frames are captured and mirrored in real time.
2. **Detect** — MediaPipe identifies 21 hand landmarks per frame.
3. **Analyze** — Flexion angles are computed from joint positions.
4. **Respond** — The game reacts to gestures; progress is recorded to the local database.
5. **Review** — Therapists review the automatically generated data on the web dashboard.

## ⚠️ Limitations & Future Improvements

While this project provides a strong proof-of-concept for AI-powered rehabilitation, it has some limitations to be addressed in future versions:
- **Environmental Dependency:** MediaPipe requires adequate lighting and clear contrast; poor lighting can drop the tracking frame rate.
- **2D Depth Limitations:** Using a standard webcam means depth estimation is inferred. Future improvements could integrate 3D depth cameras (like Intel RealSense) for true spatial accuracy.
- **Data Portability:** Currently, all data is stored locally in SQLite. Future versions aim to implement a secure, cloud-based PostgreSQL or Firebase backend for cross-device syncing.

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
