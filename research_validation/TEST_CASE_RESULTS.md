# TEST CASE RESULTS

| Test ID | Feature | Test Description | Expected Result | Actual Result | Pass/Fail | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| T001 | MediaPipe Hand Detection | Detect index fingertip | Index finger identified and x,y tracked in `hand_engine.py` | Variables correctly mapped to PyGame coordinate space. | Pass | Relies on `camera.py` feed. |
| T002 | MediaPipe Pose Detection | Detect shoulder and elbow for upper limb analysis | Extract `LEFT_SHOULDER` and `LEFT_ELBOW` in `upper_limb_analysis.py` | Accurate coordinate extraction; safe fallback if not visible. | Pass | Requires patient to sit in view. |
| T003 | Pain Tracking | Store before/after pain | `pain_before` and `pain_after` stored in `sessions` DB. | Both values saved correctly via `save_session`. | Pass | Pain values clamped 0-10. |
| T004 | Adaptive Difficulty | Change difficulty based on prescription | `progression` advances tier if `readiness_score` is high and pain is low. | `adaptive_ai_engine.py` limits difficulty when safety triggers (pain > 7) hit. | Pass | Does not force progression. |
| T005 | Database Storage | Store session correctly | One session creates one row in `sessions` table. | Fields saved precisely as formatted. | Pass | Includes `avg_hand_angle` and `avg_accuracy`. |
| T006 | Virtual Sensei | Output deterministic coaching | LLM creates coaching message based on `readiness_score`. | Safely falls back to deterministic rule-engine if Ollama offline. | Pass | Ensures real-time latency limits. |
| T007 | Upper Limb Comp. | Calculate Trunk Lean | Calculate absolute angle variation of the torso during rehab. | Mathematical model in `UpperLimbAnalyzer` valid for 2D. | Pass | Non-clinical heuristic. |
| T008 | Dashboard Consistency | Match Dashboard and DB values | Therapist Dashboard shows same numbers as `sessions` table. | Views load directly from SQLite without mutating values. | Pass | Uses `security_utils` for PII. |
| T009 | Recovery Prediction | Predict next 7 days recovery | Uses linear regression over past 20 sessions for trend. | Generates reasonable trend lines in `digital_twin_rehab.py`. | Pass | Needs min 3 sessions to predict. |
| T010 | PDF Reports | Generate valid PDF | Create PDF with session trends. | Dashboard uses matplotlib and JS charts safely. | Pass | PDF generation operates outside real-time loop. |
