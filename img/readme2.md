Level 1 (Flexibility / Bubble Reach): Used for range of motion, finger extension, and hand-shoulder coordination.
Level 2 (Strength Coordination / Falling Catch): Used for sustained palm positioning, reaction timing, and coordination.
Level 3 (Fine Motor / Pinch Transfer): Used to practice the thumb-index pinch, fine motor control, and release accuracy.
Level 4 (Path Tracing Control): Used for smooth, controlled continuous motion along a guided path.
Level 5 (Grip Release Cycle): Used to practice repeated hand opening and closing (fist vs. open hand).
Level 6 (Cognitive Finger Taps / Sequence Task): Used to train motor planning and cognition by following memory sequences.


Level 7: Rotation Orbit (Orbital Path)
Clinical Goal: Forearm Pronation and Supination (Wrist/Forearm Rotation).
How it works: You have a central orbital target and a satellite (the white circle). You rotate your forearm to align the satellite with the orbital target along the circular path.
Why it's used: Previous levels mainly focused on pinching, reaching, and finger extension. Level 7 fills a major gap by specifically tracking and training the twisting/rotational movement of the forearm and wrist.
Level 8: Smart Assembly (Stone Builder)
Clinical Goal: Advanced Multi-stage Coordination (Pinch + Drag + Rotate).
How it works: It requires three distinct actions combined into one sequence:
Pinch to grab a piece (like the blue square or red triangle).
Use your Arm to move/drag it to the blueprint (the wireframe outline).
Rotate your wrist to fit it correctly into place.



# AI Hand Rehabilitation System — Complete Workflow Documentation

## 1. Purpose and Scope

The AI Hand Rehabilitation System is a local, webcam-based physiotherapy prototype that lets a patient perform hand rehabilitation exercises through gesture-controlled games while saving session analytics for therapist review. The system has two main entry points:

1. **Patient rehabilitation runtime** — `zero_keyboard_physio.py`, a Pygame and MediaPipe application for zero-keyboard exercise sessions.
2. **Therapist dashboard** — `therapist_dashboard.py`, a local web dashboard that reads the same SQLite database and presents patient, session, analytics, notes, and reporting workflows.

The repository is intended for research, demonstration, and local prototype use. It is not presented as a production medical device or a compliant clinical record system.

## 2. Repository Map

| Path | Responsibility |
| --- | --- |
| `zero_keyboard_physio.py` | Main patient-facing rehabilitation game, webcam capture, hand/pose landmarks processing, exercise levels 1-8, ROM calibration, local data logging, voice/sound coaching feedback, and patient medical sidebar. |
| `therapist_dashboard.py` | Browser-based therapist portal served on localhost; manages patient profiles, session details, notes, clinical intelligence indicators, digital twin simulations, and PDF report downloads. |
| `adaptive_ai_engine.py` | Explainable AI engine computing difficulty prescriptions, managing forearm assessments, auditing Virtual Sensei messages, and handling therapist overrides. |
| `clinical_intelligence.py` | Clinical decision layer that evaluates patient health scores, recovery stages, and flags clinical risk indicators (overtraining, dropout, high pain, etc.). |
| `digital_twin_rehab.py` | Personalized rehabilitation digital twin calculating recovery velocities, forecasting future ROM milestones, and simulating therapeutic plan variations. |
| `upper_limb_analysis.py` | Biomechanical pose analyzer tracking shoulder elevation, abduction, elbow drift, trunk shift, and computing overall upper limb movement efficiency. |
| `llm_wrapper.py` | Thread-safe helper routing Virtual Sensei coaching messages through local Ollama LLMs for semantic polish and phrasing adjustments. |
| `clinical_modules.py` | Legacy clinical-grade support modules including filters, scikit-learn predictors, and emergency pause logic. |
| `ui_components.py` | Reusable Pygame UI components such as modern buttons, level cards, and back buttons. |
| `hand_rehab_assistant.py` | Lightweight assistant module for rehabilitation guidance functionality. |
| `dashboard_auth_addon.py` | Optional authentication/session helper code for dashboard login protection. |
| `FUTURE_RESEARCH_PATENT_ROADMAP.md` | Research roadmap documenting core patent claims, independent/dependent claim themes, and study endpoints. |
| `requirements.txt` | Python package dependencies. |
| `start.bat` | Windows helper for launching the rehabilitation runtime. |
| `start_dashboard.bat` | Windows helper for launching the therapist dashboard. |
| `img/image.png` | Project image asset. |
| `img/readme2.md` | Detailed developer and workflow documentation (this file). |


## 3. Technology Stack

### 3.1 Runtime Dependencies

The project uses the following packages:

- `opencv-python` for webcam access and image frame handling.
- `mediapipe<0.10.30` for 21-point hand landmark detection and pose landmark estimation.
- `numpy` for numerical calculations (geometry operations and audio synthesis).
- `pygame` for patient game rendering, user interaction, sound effects, and frame loop.
- `matplotlib` for generating clinician dashboard graphs and metric charts.
- `pyttsx3` for offline text-to-speech coaching feedback.
- `scikit-learn` for basic patient recovery trajectory predictions.
- `reportlab` for PDF report generation.
- `Ollama` (optional, external) for local LLM-based coaching message polishing.

### 3.2 Storage

The system stores local data in `rehab_data.db`, an SQLite database created automatically when either the game or dashboard initializes its repository/database layer.

### 3.3 User Interfaces

- The **patient UI** is a 1280 × 720 Pygame window with a 75% game area and 25% medical sidebar.
- The **therapist UI** is served by Python's `ThreadingHTTPServer` on `127.0.0.1:8080` by default.

## 4. Installation & Setup Workflow

### 4.1 Basic Installation
1. Clone the repository.
2. Move into the repository directory.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure a functioning webcam is connected and the execution environment supports a graphical window display (Pygame GUI).
5. Set up adequate lighting to optimize hand and body pose detection tracking.

### 4.2 Local LLM Setup (Optional)
To enable the enhanced Virtual Sensei coaching:
1. Download and install [Ollama](https://ollama.com).
2. Pull a compact local LLM:
   ```bash
   ollama pull qwen2.5:0.5b
   ```
3. Set environment variables to configure:
   - On Windows cmd:
     ```cmd
     set OLLAMA_SENSEI_USE_LLM=1
     set OLLAMA_SENSEI_MODEL=qwen2.5:0.5b
     set OLLAMA_SENSEI_TIMEOUT=8
     ```
   - On PowerShell:
     ```powershell
     $env:OLLAMA_SENSEI_USE_LLM="1"
     $env:OLLAMA_SENSEI_MODEL="qwen2.5:0.5b"
     $env:OLLAMA_SENSEI_TIMEOUT="8"
     ```

## 5. Launch Workflows

### 5.1 Launch the Patient Rehabilitation Runtime

```bash
python zero_keyboard_physio.py
```

What happens during startup:

1. Pygame initializes.
2. The main window is created.
3. The hand tracking engine initializes MediaPipe Hands/Pose and webcam streams.
4. The SQLite database schema is migrated/updated automatically.
5. Sound and voice text-to-speech engines initialize.
6. The app starts in the patient registration state (Dual Authentication).

### 5.2 Launch the Therapist Dashboard

```bash
python therapist_dashboard.py
```

What happens during startup:

1. The dashboard ensures the `reports` directory exists.
2. A threaded local HTTP server binds to `127.0.0.1:8080`.
3. The dashboard repository creates or migrates required clinical tables.
4. The browser is opened automatically when possible.
5. Therapists can view patient lists, analytics, session history, notes, and reports.


## 6. End-to-End System Flow

```text
Patient / Therapist setup
        |
        v
Create or select patient identity
        |
        v
Optional range-of-motion calibration
        |
        v
Choose exercise level
        |
        v
Record pain level before session
        |
        v
Start webcam-based hand tracking
        |
        v
MediaPipe detects landmarks each frame
        |
        v
System computes gestures, cursor position, angles, accuracy, and progress
        |
        v
Game level updates score, targets, feedback, and session metrics
        |
        v
Session ends by timer, completion, navigation, or quit gesture
        |
        v
Session data saved in SQLite
        |
        v
Therapist dashboard reads SQLite and renders analytics, notes, and reports
```

## 7. Patient Runtime Architecture

### 7.1 Main Window Layout

The patient runtime uses a split-screen layout:

- **Game area:** 75% of the window width. This contains registration screens, menus, levels, targets, and feedback.
- **Medical sidebar:** 25% of the window width. This shows live exercise guidance, patient/session metrics, safety messaging, and summary information.

### 7.2 Primary Runtime Objects

| Component | Role |
| --- | --- |
| `PhysioSystem` | Main application coordinator; owns UI state, patient data, level state, scoring, calibration, database, sidebar, particles, and game loop. |
| `WebcamStream` | Captures webcam frames on a separate thread so the game can maintain smoother rendering. |
| `HandEngine` | Runs MediaPipe hand detection, derives landmark positions, hand state, cursor position, pinch/fist/open-hand information, and joint/angle data. |
| `DatabaseManager` | Creates/migrates SQLite tables and saves/loads patient and session data. |
| `MedicalSidebarV2` | Renders patient-facing clinical information and live metrics beside the game area. |
| `SoundSystem` | Generates and plays lightweight sound effects without requiring external audio assets. |
| `VoiceEngine` | Provides throttled spoken feedback through `pyttsx3`. |
| `ParticleSystem` and `ScorePopup` | Provide visual reward effects and score feedback. |

## 8. Patient Identity Workflow

The application supports two patient identity paths:

1. **Clinical ID path**
   - A therapist can create or manage a patient through the dashboard.
   - The patient table can store an `id_number` such as a clinical rehabilitation ID.
   - The game can retrieve existing patient data by that identifier.

2. **Guest/manual path**
   - A patient can enter a name and age.
   - The app computes or stores an age group.
   - The patient can continue without dashboard-managed registration.

Patient records include:

- Name.
- Age.
- Age group.
- Optional clinical ID.
- Calibration values for fist threshold, maximum extension, minimum angle, maximum angle, and calibration-active status.

## 9. Age Group and Theme Workflow

The game adapts labels, colors, speed, and target size by age group:

| Age group | Theme | Design intention |
| --- | --- | --- |
| Child | Magic Garden | Larger targets, slower movements, playful icons and wording. |
| Young | Cyber Arena | Faster, more energetic targets and competitive styling. |
| Adult | Zen Garden | Balanced speed and calm visual language. |
| Senior | Memory Lane | Larger targets and gentler pacing. |

Theme data affects:

- Background colors.
- Primary and secondary colors.
- Level names.
- Level icons.
- Speed multipliers.
- Target size multipliers.

## 10. Zero-Keyboard Navigation Workflow

The patient can operate the system without a keyboard or mouse during normal use.

1. The webcam tracks the hand.
2. The hand position is mapped to an on-screen cursor or interaction point.
3. Menu items display hover rings.
4. The user holds the cursor over a button for the configured hover duration.
5. When the hover timer completes, the system activates the selected button.
6. A fist-hold gesture can be used for pause/quit safety actions where configured.

Important interaction timing constants:

- Hover selection duration: about 1.5 seconds.
- Fist hold duration: about 2 seconds.
- The app uses smoothing buffers to reduce cursor jitter.

## 11. Hand Tracking and Gesture Analysis Flow

For every frame:

1. OpenCV obtains a webcam frame.
2. The image is mirrored so movement feels natural.
3. MediaPipe Hands processes the frame.
4. If a hand is detected, 21 hand landmarks are produced.
5. The system converts landmark coordinates into screen/game coordinates.
6. It computes distances, angles, extension, pinch state, fist state, open-hand state, and cursor position.
7. Smoothing is applied to reduce jitter.
8. The active game state consumes the computed `HandData`.
9. Visual overlays, score updates, sidebar metrics, and audio/voice feedback are updated.

If tracking confidence drops or the hand is not visible, the game should avoid recording misleading motion and prompts the user to bring the hand back into view.

## 12. Calibration / ROM Diagnostics Workflow

Calibration gives the system patient-specific movement thresholds.

1. The patient enters the ROM diagnostics/calibration screen.
2. The patient performs a closed-fist pose.
3. The system records a calibrated fist threshold.
4. The patient performs an open-hand/extension pose.
5. The system records maximum extension and angle ranges.
6. Calibration values are saved with the patient profile.
7. Later sessions use these values to interpret gestures and progress more fairly.

Stored calibration fields include:

- `cal_fist_val` — fist detection threshold.
- `cal_max_ext` — maximum measured extension.
- `cal_min_ang` — lower angle bound.
- `cal_max_ang` — upper angle bound.
- `cal_active` — whether calibration has been completed.

## 13. Pain Scale Workflow

Before starting a selected exercise level, the runtime stores a pain score from 0 to 10.

- `0` means no pain.
- `10` means maximum pain.
- The value is saved with the session record.
- Therapists can use pain progression alongside range-of-motion and accuracy trends.

## 14. Exercise Level Workflows

The patient runtime includes eight level slots. The labels are adapted by age theme, while the clinical intent remains consistent.


### 14.1 Level 1 — Flexibility / Bubble Reach

Clinical goal:

- Encourage range of motion, reaching, finger extension, and shoulder/hand coordination.

Flow:

1. Targets appear in reachable areas of the game zone.
2. The patient moves the tracked hand cursor toward each target.
3. A successful reach pops or collects the target.
4. Score increases.
5. Accuracy and reach metrics update.
6. New targets spawn until the level timer or completion condition ends.

Measured signals:

- Score.
- Accuracy hits and attempts.
- Reach distance.
- Maximum extension.
- Average hand angle.

### 14.2 Level 2 — Strength Coordination / Falling Item Catch

Clinical goal:

- Practice sustained hand positioning, palm control, reaction timing, and coordination.

Flow:

1. Items fall from the top of the game area.
2. The patient positions the hand or basket/palm under the item.
3. Catching an item increases score.
4. Missing an item can reduce combo or simply count as an attempt depending on game logic.
5. Falling speed and object size can vary by age theme.

Measured signals:

- Catches.
- Attempts.
- Accuracy percentage.
- Movement smoothness indirectly through hit/miss consistency.

### 14.3 Level 3 — Fine Motor / Pinch Transfer

Clinical goal:

- Practice thumb-index pinch, fine motor control, grip timing, and release accuracy.

Flow:

1. Seeds or small objects appear.
2. The patient pinches to grab an object.
3. The patient transports it toward the target pot/area.
4. The patient releases the pinch to drop it.
5. Correct placement increases score.

Measured signals:

- Pinch success.
- Transfer accuracy.
- Drop accuracy.
- Fine motor control consistency.

### 14.4 Level 4 — Path Tracing Control

Clinical goal:

- Practice smooth controlled motion along a guided path.

Flow:

1. A trace target or path appears.
2. The patient follows the path with the tracked cursor.
3. Staying near the path increases progress or score.
4. Deviation reduces accuracy.
5. The level reinforces controlled, continuous motion rather than quick tapping.

Measured signals:

- Path-following accuracy.
- Control stability.
- Time-on-path.

### 14.5 Level 5 — Grip Release Cycle

Clinical goal:

- Practice repeated hand opening and closing patterns.

Flow:

1. The game prompts an open/close cycle.
2. The system detects fist and open-hand states.
3. A correct cycle advances progress.
4. Timing and consistency affect scoring.
5. Voice/visual feedback guides the patient if movement is incomplete.

Measured signals:

- Completed cycles.
- Gesture consistency.
- Range between closed and open states.

### 14.6 Level 6 — Cognitive Finger Taps / Sequence Task

Clinical goal:

- Combine cognition, memory, attention, and finger movement control.

Flow:

1. The system presents a pattern or sequence.
2. The patient uses controlled hand/finger actions to follow the sequence.
3. Correct inputs advance the sequence.
4. Incorrect inputs can reset or reduce score.
5. The task trains motor planning as well as movement execution.

Measured signals:

- Correct sequence steps.
- Accuracy.
- Response consistency.

### 14.7 Level 7 — Rotation Orbit (Orbital Path)

Clinical goal:

- Train forearm pronation and supination (wrist/forearm rotation).

Flow:

1. A central orbital target and a satellite (white circle) are displayed.
2. The patient rotates their forearm to align the satellite with the orbital target.
3. The movement follows a circular path around the center.
4. Keeping the satellite in the target advances progress.

Measured signals:

- Forearm rotation tracking accuracy.
- Time held in target.
- Pronation/supination range of motion.

### 14.8 Level 8 — Smart Assembly (Stone Builder)

Clinical goal:

- Advanced multi-stage coordination combining pinch grip, arm motion, and wrist rotation.

Flow:

1. The patient pinches to grab a loose piece (e.g., a blue square or red triangle).
2. The patient uses arm movement to drag the piece to the wireframe blueprint outline.
3. The patient rotates their wrist to fit the piece correctly into the blueprint.
4. Correct placement scores points and advances the assembly.
5. This simulates complex real-world functional tasks (e.g., turning a key or building).

Measured signals:

- Pinch success and hold consistency.
- Translation (drag) accuracy.
- Wrist rotation accuracy.

## 15. In-Session Feedback Workflow

The system provides feedback through multiple channels:

- **Visual feedback** — score popups, particles, target animations, progress rings, highlighted buttons, and sidebar panels.
- **Audio feedback** — generated Pygame sound effects for success and interaction events.
- **Voice feedback** — throttled `pyttsx3` coaching to prevent constant speech overlap.
- **Medical sidebar** — live metrics and exercise hints.
- **Post-game summary** — session results after completion.

Voice feedback is deliberately rate-limited so the user is not overwhelmed.

## 16. Session Completion and Data Logging Workflow

At the end of a session:

1. The runtime computes final score.
2. It calculates duration from session start to end.
3. It computes average accuracy from hits and attempts.
4. It stores maximum extension and reach distance.
5. It stores average hand angle where available.
6. It stores the selected pain level.
7. It writes a row to the `sessions` table.
8. It displays a post-game summary.
9. The therapist dashboard can immediately read the new data from SQLite.

## 17. Database Schema Details

### 17.1 `patients`

| Column | Type | Purpose |
| --- | --- | --- |
| `name` | `TEXT PRIMARY KEY` | Patient display name and primary key. |
| `age` | `INTEGER` | Patient age. |
| `age_group` | `TEXT` | Theme/clinical grouping used by the game. |
| `cal_fist_val` | `REAL DEFAULT 0.12` | Calibrated fist threshold. |
| `cal_max_ext` | `REAL DEFAULT 170.0` | Maximum extension calibration value. |
| `cal_min_ang` | `REAL DEFAULT 15.0` | Minimum calibrated angle. |
| `cal_max_ang` | `REAL DEFAULT 90.0` | Maximum calibrated angle. |
| `cal_active` | `INTEGER DEFAULT 0` | Calibration completion flag. |
| `id_number` | `TEXT UNIQUE` | Optional therapist-created clinical ID. |

### 17.2 `sessions`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique session row ID. |
| `patient_id` | `TEXT DEFAULT 'Unknown'` | Patient identifier/name used for linking. |
| `timestamp` | `DATETIME DEFAULT CURRENT_TIMESTAMP` | Session creation time. |
| `level` | `INTEGER` | Exercise level completed. |
| `score` | `INTEGER` | Final score. |
| `duration` | `REAL` | Session duration in seconds. |
| `avg_accuracy` | `REAL` | Average accuracy percentage or score. |
| `max_finger_extension` | `REAL` | Best extension metric recorded. |
| `reach_distance` | `REAL` | Reach distance metric. |
| `avg_hand_angle` | `REAL DEFAULT 0` | Average hand/finger angle metric. |
| `pain_level` | `INTEGER DEFAULT 0` | Pre-session 0–10 pain score. |

### 17.3 `dashboard_patient_profiles`

| Column | Type | Purpose |
| --- | --- | --- |
| `patient_name` | `TEXT PRIMARY KEY` | Dashboard profile key linked to patient name. |
| `gender` | `TEXT DEFAULT ''` | Optional demographic field. |
| `injury_type` | `TEXT DEFAULT ''` | Injury classification entered by therapist. |
| `rehab_stage` | `TEXT DEFAULT ''` | Stage of rehabilitation. |
| `assigned_exercises` | `TEXT DEFAULT ''` | Therapist-assigned plan. |
| `therapist_notes` | `TEXT DEFAULT ''` | Persistent profile notes. |
| `updated_at` | `DATETIME DEFAULT CURRENT_TIMESTAMP` | Last metadata update time. |

### 17.4 `dashboard_notes`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique note ID. |
| `patient_name` | `TEXT NOT NULL` | Patient this note belongs to. |
| `session_id` | `INTEGER` | Optional session link. |
| `note_type` | `TEXT DEFAULT 'Observation'` | Note category. |
| `note` | `TEXT NOT NULL` | Clinical note text. |
| `recommendation` | `TEXT DEFAULT ''` | Follow-up recommendation. |
| `next_plan` | `TEXT DEFAULT ''` | Next treatment plan. |
| `created_at` | `DATETIME DEFAULT CURRENT_TIMESTAMP` | Note creation time. |

### 17.5 `adaptive_prescriptions`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique prescription ID. |
| `patient_id` | `TEXT NOT NULL` | Patient linked to the prescription. |
| `session_id` | `INTEGER` | Session ID that triggered/validated this prescription. |
| `level` | `INTEGER NOT NULL` | Exercise level. |
| `difficulty_tier` | `INTEGER NOT NULL` | Difficulty tier (1 to 5). |
| `readiness_score` | `REAL DEFAULT 50` | Calculated patient physical readiness score. |
| `target_scale` | `REAL NOT NULL` | Target object scaling multiplier. |
| `speed_scale` | `REAL NOT NULL` | Falling object speed scaling multiplier. |
| `required_rom` | `REAL NOT NULL` | Required flexion/extension angle range of motion. |
| `time_limit` | `REAL NOT NULL` | Level time limit in seconds. |
| `repetitions` | `INTEGER NOT NULL` | Target exercise repetition count. |
| `hold_seconds` | `REAL NOT NULL` | Required hold duration for static poses. |
| `rotation_tolerance` | `REAL NOT NULL` | Wrist rotation deviation tolerance in degrees. |
| `assembly_position_tolerance` | `REAL NOT NULL` | Position snapping tolerance for assembly pieces. |
| `assembly_angle_tolerance` | `REAL NOT NULL` | Rotation snapping tolerance for assembly pieces. |
| `guidance_level` | `TEXT NOT NULL` | Level of coaching assistance (e.g., standard, high). |
| `progression` | `TEXT NOT NULL` | Recommendation (maintain, advance, regress). |
| `risk_level` | `TEXT NOT NULL` | Assessed safety risk level (low, moderate, high). |
| `recovery_trend` | `TEXT DEFAULT 'stable'` | Recovery trajectory category. |
| `override_recommendation` | `TEXT` | Prompt alerting therapist of override suggestions. |
| `ai_confidence_score` | `REAL DEFAULT 75` | Confidence index of the generated parameters. |
| `override_probability` | `REAL DEFAULT 0.25` | Estimated likelihood of clinical override being needed. |
| `recommendation_reliability` | `REAL DEFAULT 75` | Calculated reliability score of the prescription. |
| `explanation_json` | `TEXT DEFAULT '{}'` | Detailed rule activations stored in JSON structure. |
| `rationale` | `TEXT NOT NULL` | Human-readable explanation of why these difficulty parameters were set. |
| `metrics_json` | `TEXT DEFAULT '{}'` | Snapshot of session metrics used for calculation. |
| `created_at` | `DATETIME` | Time stamp. |

### 17.6 `forearm_assessments`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique assessment ID. |
| `patient_id` | `TEXT NOT NULL` | Linked patient ID. |
| `session_id` | `INTEGER` | Session ID context. |
| `level` | `INTEGER` | Completed level ID. |
| `movement_class` | `TEXT NOT NULL` | Movement classification (e.g., Supination, Pronation, Smooth Rotation, Compensatory). |
| `rotation_angle` | `REAL NOT NULL` | Measured wrist/forearm rotation angle. |
| `smoothness` | `REAL NOT NULL` | Rotation path smoothness factor (0.0 to 1.0). |
| `compensation_score` | `REAL NOT NULL` | Biomechanical compensation score. |
| `endurance_seconds` | `REAL NOT NULL` | Time rotation angle was maintained. |
| `created_at` | `DATETIME` | Timestamp. |

### 17.7 `sensei_messages`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Message log ID. |
| `patient_id` | `TEXT NOT NULL` | Linked patient ID. |
| `session_id` | `INTEGER` | Session ID context. |
| `level` | `INTEGER` | Level ID context. |
| `message` | `TEXT NOT NULL` | Spoken voice guidance text. |
| `deterministic_message` | `TEXT` | Rule-based baseline message. |
| `llm_enhanced_message` | `TEXT` | Message as edited by Ollama LLM. |
| `coaching_trigger` | `TEXT` | The rule condition that triggered feedback. |
| `decision_source` | `TEXT` | Module generating the feedback (Adaptive AI Engine). |
| `llm_status` | `TEXT` | Integration status (e.g., enhanced, error, not_requested). |
| `context_json` | `TEXT` | Context variables passed during generation. |
| `created_at` | `DATETIME` | Timestamp. |

### 17.8 `therapist_overrides`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Override ID. |
| `prescription_id` | `INTEGER` | Target prescription ID. |
| `patient_id` | `TEXT NOT NULL` | Linked patient ID. |
| `therapist_id` | `TEXT` | Therapist profile identifier. |
| `decision` | `TEXT NOT NULL` | Decision outcome (accept, modify, reject). |
| `reason` | `TEXT NOT NULL` | Clinical justification category. |
| `therapist_reason` | `TEXT` | Free-text clinical comments. |
| `ai_recommendation_json` | `TEXT` | The original AI prescription parameters. |
| `modified_recommendation_json` | `TEXT` | The customized parameters set by the therapist. |
| `patient_context_json` | `TEXT` | Patient history context snapshot. |
| `session_metrics_json` | `TEXT` | Raw metrics snapshot. |
| `created_at` | `DATETIME` | Timestamp. |

### 17.9 `upper_limb_assessments`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Assessment row ID. |
| `patient_id` | `TEXT NOT NULL` | Linked patient ID. |
| `session_id` | `INTEGER` | Associated session ID. |
| `level` | `INTEGER` | Exercise level. |
| `shoulder_angle` | `REAL` | Measured shoulder angle in degrees. |
| `elbow_angle` | `REAL` | Measured elbow angle in degrees. |
| `forearm_rotation_angle` | `REAL` | Forearm rotation angle. |
| `trunk_lean_angle` | `REAL` | Torso lean deviation. |
| `shoulder_compensation` | `REAL` | Calculated shoulder compensation score (0.0 to 1.0). |
| `elbow_compensation` | `REAL` | Calculated elbow compensation score (0.0 to 1.0). |
| `trunk_compensation` | `REAL` | Calculated trunk compensation score (0.0 to 1.0). |
| `compensation_score` | `REAL` | Overall combined compensation metric. |
| `movement_efficiency` | `REAL` | Calculated movement efficiency percentage (100 - compensation%). |
| `feedback` | `TEXT` | Diagnostic posture advice. |
| `side` | `TEXT` | Calibrated active side (Left/Right). |
| `created_at` | `DATETIME` | Timestamp. |

### 17.10 `digital_twin_snapshots`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Snapshot row ID. |
| `patient_id` | `TEXT NOT NULL` | Patient ID. |
| `snapshot_json` | `TEXT NOT NULL` | Full serialized Digital Twin model profile. |
| `current_rom` | `REAL` | Patient ROM at snapshot. |
| `current_accuracy` | `REAL` | Patient accuracy at snapshot. |
| `readiness_score` | `REAL` | Readiness index. |
| `recovery_velocity` | `REAL` | Estimated ROM velocity in degrees/week. |
| `stagnation_risk` | `REAL` | Projected risk of recovery plateau. |
| `overtraining_risk` | `REAL` | Projected risk of physical fatigue/strain. |
| `high_pain_risk` | `REAL` | Pain ceiling threshold alert level. |
| `compensation_risk` | `REAL` | Estimated dependency on posture offsets. |
| `dropout_risk` | `REAL` | Projected likelihood of session abandonment. |
| `created_at` | `DATETIME` | Timestamp. |


## 18. Therapist Dashboard Workflow

### 18.1 Dashboard Startup

1. `DashboardRepository` initializes.
2. It ensures dashboard metadata tables exist.
3. It ensures the core `patients` table exists even if the game has never run.
4. The HTTP server serves pages on localhost.
5. Requests are handled by `DashboardHandler` and rendered by `DashboardRenderer`.

### 18.2 Patient Management

Therapist-facing patient management includes:

- Viewing all patients.
- Seeing age, age group, and optional clinical ID.
- Viewing session counts.
- Viewing average accuracy and average range-of-motion metrics.
- Recording profile metadata such as gender, injury type, rehabilitation stage, assigned exercises, and notes.

### 18.3 Analytics

Dashboard analytics can include:

- Total sessions.
- Average accuracy.
- Average range-of-motion angle.
- Session duration totals.
- Progress trends.
- Tremor/stability-style rating based on recent ROM variability.
- Recovery projection based on recent session angle values.

### 18.4 Notes Workflow

1. Therapist opens a patient/session context.
2. Therapist writes an observation note.
3. Therapist optionally adds a recommendation and next plan.
4. The note is saved to `dashboard_notes`.
5. Notes remain available for later review and reporting.

### 18.5 Report Workflow

1. Therapist selects a patient/report action.
2. Dashboard gathers patient metadata, sessions, notes, and analytics.
3. Charts can be generated with Matplotlib.
4. PDF generation can use ReportLab where implemented and available.
5. Generated reports are stored under `reports`.

## 19. Core Adaptive AI & Clinical Intelligence Modules

The platform relies on a set of five core analytical modules to manage explainable adaptation, biomechanical assessment, recovery forecasting, and clinical decision support.

### 19.1 Adaptive AI Engine (`adaptive_ai_engine.py`)

The `AdaptiveRehabEngine` implements an explainable, closed-loop personalization layer.
- **Adaptive Prescriptions**: Based on the patient's performance history, pain level, range of motion (ROM), consistency, and posture quality, the engine calculates a new prescription for the next session. This modifies parameters including:
  - `difficulty_tier`: Tiers 1–5 adapting the overall game parameters.
  - `target_scale` & `speed_scale`: Target dimensions and object falling speeds.
  - `required_rom`: Flexion/extension angles targeted for level completion.
  - `time_limit`: Seconds allowed for the exercise.
  - `repetitions` & `hold_seconds`: Reps and duration required for pose validation.
  - `rotation_tolerance`, `assembly_position_tolerance`, `assembly_angle_tolerance`: Snapping and deviation margins for Level 7 and Level 8.
- **Forearm Assessment Classifier**: Classifies forearm movements into categories:
  - *Neutral Position*, *Pronation*, *Supination*, *Partial Pronation*, *Partial Supination*, *Rotation Hold*, *Rotation Endurance*, *Smooth Rotation*, and *Compensatory Movement*.
- **Coaching Messages Audit**: Logs every coaching advice generated. The decision logic remains rule-based for safety, but allows optional local LLM rewrites via the `llm_wrapper.py`.

### 19.2 Clinical Intelligence Layer (`clinical_intelligence.py`)

The `ClinicalIntelligenceLayer` provides advanced decision support for therapists.
- **Health Score Calculation**: Computes a single 0-100 metric summarizing the patient's physical state:
  $$\text{Base Score} = (\text{ROM Score} \times 0.5) + (\text{Accuracy Score} \times 0.5)$$
  $$\text{ROM Score} = \min\left(100.0, \frac{\text{Average ROM}}{90.0} \times 100\right)$$
  $$\text{Final Score} = \text{Base Score} - \text{Pain Penalty} - \text{Compensation Penalty}$$
  - *Pain Penalty*: Up to -20 points based on the 0–10 pain index.
  - *Compensation Penalty*: Up to -25 points based on the upper limb posture compensation score.
- **Recovery Stage Classification**:
  - *Early Recovery*: Average ROM $< 45.0^\circ$.
  - *Intermediate Recovery*: Average ROM between $45.0^\circ$ and $75.0^\circ$.
  - *Advanced Recovery*: Average ROM $\ge 75.0^\circ$.
- **Clinical Risk Detection**: Automatically triggers flags for doctor review:
  - *High Pain Risk*: Average pain level $\ge 6.0$.
  - *Overtraining Risk*: Declining exercise accuracy ($\ge 10.0\%$ drop) alongside pain index $\ge 4.0$.
  - *Dropout Risk*: No completed session logged in the last 10 days.
  - *Compensation Dependency*: Average upper limb compensation score $\ge 0.40$.

### 19.3 Personalized Digital Twin (`digital_twin_rehab.py`)

The `DigitalTwinRehabModel` builds a simulation twin of the patient's recovery trajectory.
- **Longitudinal Snapshots**: Periodically saves profile snapshots to trace recovery velocities.
- **Simulation Scenarios**:
  - *Scenario A (Current plan continues)*: Forecasts recovery duration and final ROM/accuracy milestones based on the current session rate and performance consistency.
  - *Scenario B (Increased intensity)*: Simulates a $1.35\times$ velocity boost. Highlights potential risks (elevated fatigue indexes, joint compensation dependency, and lower session adherence).
  - *Scenario C (Reduced intensity)*: Simulates a $0.65\times$ slower velocity. Reduces physical stress/pain limits while extending the projected recovery timeline.
- **Weekly ROM Velocity**: Calculated as:
  $$\text{Velocity (deg/week)} = \frac{\text{Current ROM} - \text{Baseline ROM}}{\text{Days Elapsed}} \times 7.0$$

### 19.4 Upper Limb Biomechanics (`upper_limb_analysis.py`)

The `UpperLimbAnalyzer` uses MediaPipe Pose landmarks to evaluate compensation mechanisms.
- **Pose Landmark Extraction**: Captures 2D webcam coordinates for left/right shoulders, elbows, wrists, and hips.
- **Postural Deviation Tracking**:
  - *Shoulder Elevation*: Measures y-coordinate shift of the shoulder relative to the torso height.
  - *Shoulder Abduction*: Measures lateral elbow offset relative to the shoulder width.
  - *Elbow Drift*: Tracks 2D displacement of the active elbow relative to baseline position.
  - *Trunk Shift & Lean*: Evaluates center-of-gravity offsets and torso angular tilt.
- **Compensation Score**: Translates physical shifts into a 0.0 to 1.0 compensation factor, leading to:
  $$\text{Movement Efficiency (\%)} = 100.0 \times (1.0 - \text{Compensation Score})$$
  Provides contextual feedback alerts (e.g., *"Avoid lifting your shoulder"* or *"Try keeping your elbow stable"*).

### 19.5 LLM Wrapper for Voice Coaching (`llm_wrapper.py`)

This wrapper implements a thread-safe connection to the local Ollama API.
- **Coaching Message Polishing**: It sends the rule-based deterministic advice to Ollama (defaulting to the `qwen2.5:0.5b` model or fallbacks like `smollm2:135m`, `llama3.2:1b`).
- **Semantic Consistency Gating**: A strict clinical system prompt forces the model to only adjust language phrasing for conversational polish. The LLM is explicitly forbidden from modifying clinical prescriptions, difficulty tiers, pain thresholds, safety ratings, or exercises.
- **Graceful Fallbacks**: If the Ollama server is offline, times out (default 8 seconds), or returns garbage, the system silently drops back to the rule-based deterministic text, maintaining patient safety.

### 19.6 Legacy Clinical Modules (`clinical_modules.py`)

This file contains legacy helper classes that are retained for backwards compatibility:
- `ClinicalAccuracyFilter`: Implements a simple moving-average (SMA) filter with a window size of 5 to remove high-frequency coordinate jitter.
- `VirtualSensei`: Provides rule-based comparison between current joint angles and target angles, outputting instructions like "Bend further" or "Hold it there".
- `RecoveryPredictor`: Uses basic scikit-learn linear regression to forecast future session scores.
- `TherapistDashboard`: Handles matplotlib line charts generation for patient sessions.
- `EmergencyPause`: Implements confidence score threshold gating for MediaPipe landmarks to suspend data logging when the webcam feed is obscured.


## 20. Security and Privacy Notes

The system is a local prototype with important limitations:

- The dashboard binds to localhost by default, reducing accidental network exposure.
- SQLite data is not encrypted at rest.
- The core dashboard does not enforce production-grade authentication by default.
- Local files may contain sensitive patient-like information if real names are entered.
- The system should not be used for real protected health information without encryption, access control, audit logging, backups, consent handling, and compliance review.

Recommended safeguards for real deployments:

1. Add authenticated therapist accounts.
2. Encrypt the database at rest.
3. Use HTTPS for any networked dashboard.
4. Separate patient identifiers from direct names.
5. Add consent, retention, and deletion workflows.
6. Add role-based access control.
7. Maintain audit logs for clinical data access.
8. Validate all report exports and data downloads.

## 21. Error Handling and Environmental Considerations

### 21.1 Webcam Issues

Potential causes:

- No webcam attached.
- Webcam already in use by another application.
- Operating system permissions block camera access.
- Poor lighting or hand not visible.

Recommended response:

- Close other camera apps.
- Improve lighting.
- Keep the full hand in frame.
- Restart the runtime after fixing camera access.

### 21.2 Audio or Voice Issues

Potential causes:

- No audio output device.
- `pyttsx3` backend unavailable.
- Pygame mixer cannot initialize.

Recommended response:

- Continue using visual feedback if audio fails.
- Install platform voice packages if required.
- Verify speakers/headphones.

### 21.3 Dashboard Port Conflicts

Default port: `8080`.

If the port is already in use:

- Stop the conflicting process.
- Run the dashboard with an alternate port if supported by command-line argument handling.

### 21.4 Dependency Issues

Potential causes:

- Unsupported Python version.
- MediaPipe wheel unavailable for the platform.
- Missing system GUI libraries for Pygame/OpenCV.

Recommended response:

- Use a mainstream Python 3.x version supported by MediaPipe.
- Reinstall dependencies from `requirements.txt`.
- Use a local desktop environment for the Pygame runtime.

## 22. Data Quality Workflow

To produce useful therapy analytics:

1. Use consistent lighting and camera position.
2. Calibrate the patient's fist and open hand before serious tracking.
3. Ask the patient to keep the hand inside the camera frame.
4. Prefer shorter sessions with clean tracking over long sessions with poor visibility.
5. Review pain scores together with performance metrics.
6. Do not compare patients directly without considering age, injury, calibration, and ability.
7. Treat all automated predictions as supportive indicators, not clinical decisions.

## 23. Development Workflow

A typical developer workflow is:

1. Create or update code.
2. Install dependencies.
3. Run syntax checks.
4. Launch the dashboard for web UI verification.
5. Launch the Pygame runtime on a machine with a webcam for full functional testing.
6. Confirm database migrations on a fresh database.
7. Verify no generated private data is committed.

Useful checks:

```bash
python -m py_compile zero_keyboard_physio.py therapist_dashboard.py clinical_modules.py ui_components.py hand_rehab_assistant.py dashboard_auth_addon.py
```

For full manual verification, also run:

```bash
python therapist_dashboard.py
python zero_keyboard_physio.py
```

## 24. Complete Patient Journey Example

1. Therapist starts `python therapist_dashboard.py`.
2. Therapist creates a patient profile and records injury context.
3. Patient starts `python zero_keyboard_physio.py`.
4. Patient enters clinical ID or guest details.
5. System applies age-appropriate theme.
6. Patient performs ROM diagnostics.
7. Patient chooses Level 1.
8. Patient records pain level.
9. Webcam tracking begins.
10. Patient reaches toward targets using hand movement.
11. The system updates score, accuracy, extension, and angle values.
12. Session ends.
13. The system writes session metrics into SQLite.
14. Therapist refreshes dashboard.
15. Therapist reviews charts, accuracy, ROM, pain, notes, and plan.
16. Therapist optionally exports a report.
17. Patient repeats sessions over time to build trend data.

## 25. Complete Data Flow Summary

```text
Webcam frame
  -> OpenCV capture
  -> Mirror/prepare image
  -> MediaPipe hand landmark detection
  -> Landmark coordinate conversion
  -> Gesture and angle calculations
  -> Smoothing/filtering
  -> Game state update
  -> Score/accuracy/progress update
  -> Sidebar/audio/voice feedback
  -> Session summary metrics
  -> SQLite sessions table
  -> Dashboard repository queries
  -> HTML analytics/charts/notes/reports
```

## 26. Future Improvement Checklist

Recommended technical improvements:

- Add dashboard authentication by default.
- Encrypt `rehab_data.db` or migrate to a secure database.
- Add explicit patient consent and data deletion screens.
- Add automated tests for database migrations and analytics calculations.
- Add hardware calibration guidance with camera distance and lighting prompts.
- Add export/import workflows for therapist-supervised backups.
- Add confidence thresholds directly to every metric-writing path.
- Add per-finger ROM metrics instead of only aggregate values.
- Add configurable exercise prescriptions per patient.
- Add accessibility options for color contrast, font size, and speech rate.
- Add real clinical validation before medical use.

## 27. Key Takeaways

- The system is built around a shared local SQLite database.
- The patient runtime generates movement and performance data.
- The therapist dashboard turns that data into reviewable patient progress information.
- Calibration, lighting, and stable hand tracking are essential for meaningful metrics.
- The project is a strong local prototype, but it requires security, compliance, validation, and clinical review before real-world medical deployment.
