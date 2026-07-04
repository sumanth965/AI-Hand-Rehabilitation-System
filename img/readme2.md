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
| `zero_keyboard_physio.py` | Main patient-facing rehabilitation game, webcam capture, hand analysis, exercise levels, calibration, local data logging, audio/voice feedback, and in-game medical sidebar. |
| `therapist_dashboard.py` | Browser-based therapist portal served on localhost; manages patients, dashboard metadata, session analytics, notes, charts, and reports. |
| `clinical_modules.py` | Optional clinical-grade support modules: smoothing filter, virtual coaching, recovery prediction, chart export, and emergency pause logic. |
| `ui_components.py` | Reusable Pygame UI components such as modern buttons, level cards, and back buttons. |
| `hand_rehab_assistant.py` | Lightweight assistant module for rehabilitation guidance functionality. |
| `dashboard_auth_addon.py` | Optional authentication/session helper code for dashboard login protection. |
| `requirements.txt` | Python package dependencies. |
| `start.bat` | Windows helper for launching the rehabilitation runtime. |
| `start_dashboard.bat` | Windows helper for launching the therapist dashboard. |
| `img/image.png` | Project image asset. |

## 3. Technology Stack

### 3.1 Runtime Dependencies

The project uses the following packages:

- `opencv-python` for webcam access and image frame handling.
- `mediapipe<0.10.30` for 21-point hand landmark detection.
- `numpy` for numerical operations and generated sound wave arrays.
- `pygame` for the patient-facing graphical game, event loop, sounds, and UI rendering.
- `matplotlib` for dashboard charts and non-interactive graph generation.
- `pyttsx3` for offline text-to-speech coaching.
- `scikit-learn` for optional regression-based prediction in `clinical_modules.py`.
- `reportlab` for PDF report generation where report export is available.

### 3.2 Storage

The system stores local data in `rehab_data.db`, an SQLite database created automatically when either the game or dashboard initializes its repository/database layer.

### 3.3 User Interfaces

- The **patient UI** is a 1280 × 720 Pygame window with a 75% game area and 25% medical sidebar.
- The **therapist UI** is served by Python's `ThreadingHTTPServer` on `127.0.0.1:8080` by default.

## 4. Installation Workflow

1. Clone the repository.
2. Move into the repository directory.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Ensure a functioning webcam is available.
5. Ensure the runtime environment can open a GUI window for Pygame.
6. Use good lighting and keep the hand clearly visible to improve MediaPipe tracking.

## 5. Launch Workflows

### 5.1 Launch the Patient Rehabilitation Runtime

```bash
python zero_keyboard_physio.py
```

What happens during startup:

1. Pygame initializes.
2. The main window is created.
3. The hand tracking engine initializes MediaPipe and the webcam stream.
4. The SQLite schema is created or migrated.
5. Sound and voice systems attempt to initialize.
6. The app starts in the patient registration state.

### 5.2 Launch the Therapist Dashboard

```bash
python therapist_dashboard.py
```

What happens during startup:

1. The dashboard ensures the `reports` directory exists.
2. A threaded local HTTP server binds to `127.0.0.1:8080`.
3. The dashboard repository creates or migrates required tables.
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

The patient runtime includes six level slots. The labels are adapted by age theme, while the clinical intent remains consistent.

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

## 19. Optional Clinical Modules

`clinical_modules.py` contains modular building blocks that can be used by the runtime or future integrations.

### 19.1 `ClinicalAccuracyFilter`

- Applies a moving-average filter to angle lists and 2D points.
- Helps reduce MediaPipe landmark jitter.
- Can reset buffers when tracking is lost.

### 19.2 `VirtualSensei`

- Compares a live angle against a target angle.
- Uses tolerance and hold-duration rules.
- Returns events such as success, hold, bend further, or too far.
- Provides rate-limited voice coaching.

### 19.3 `RecoveryPredictor`

- Uses linear regression when scikit-learn is available.
- Falls back to manual regression if scikit-learn is missing.
- Predicts a future recovery/angle trend from session history.

### 19.4 `TherapistDashboard`

- Generates progress graphs with Matplotlib.
- Exports visual progress summaries.

### 19.5 `EmergencyPause`

- Monitors confidence and tracking quality.
- Helps prevent bad data capture when landmarks are unreliable.

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
