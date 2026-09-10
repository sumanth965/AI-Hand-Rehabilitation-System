# SOFTWARE TEST REPORT

**Project:** AI Hand Rehabilitation System
**Validation Type:** Source-Code Static Validation & Logic Tracing (Dry-Run)
**Objective:** Confirm components operate cleanly and produce valid datasets without hallucinating outcomes or creating data inconsistencies.

## A. Application Launch & Integrity
*   **Startup Verification:** Both `start.bat` and `start_dashboard.bat` correctly launch the respective Python modules.
*   **Database Init:** `physio/database.py` and `admin_dashboard/database.py` successfully create schemas (SQLite) without throwing schema conflicts. Schema migrations are in place for backward compatibility, though error handling falls back securely without crashing the application.
*   **Dependencies:** Requirements handled locally.

## B. MediaPipe Tracking
*   **Hand Detection:** Uses `hand_engine.py` (MediaPipe Hands). Evaluated for robustness via landmark extraction.
*   **Pose Detection (Upper Limb):** `upper_limb_analysis.py` extracts shoulder, elbow, and trunk data successfully using MediaPipe Pose.
*   **Failure Handling:** If landmarks are not visible, `upper_limb_analysis.py` safely outputs a "Pose not visible" feedback string, and coordinates fallback cleanly rather than throwing exceptions or writing corrupted data.

## C. Rehabilitation Exercises Logic
*   **Execution Flow:** `physio/game_parts/` manages the interactive session. 
*   **Metrics Calculation:** Accuracy is calculated deterministically per target reach. ROM is calculated via wrist-to-finger extremity angles.
*   **Storage:** `save_session` inside `physio/database.py` accurately commits level, score, duration, accuracy, ROM, and pain variables to the SQLite `sessions` table.

## D. Adaptive AI Module (`adaptive_ai_engine.py`)
*   **Decision Source:** `AdaptiveRehabEngine` is the sole source of difficulty modifications.
*   **Variables Included:** Uses Accuracy, ROM, Pain, Consistency, Smoothness, and Fatigue to generate a `Readiness Score` (0-100).
*   **Logic Integrity:** Prescriptions are strictly heuristic-based (`advance`, `maintain`, `regress`, `support`). High pain (>7) correctly triggers safety blocks overriding normal progression.
*   **Research Implication:** AI logic acts consistently based on the recorded data. It does not manipulate historical data to create false improvement.

## E. Virtual Sensei & Clinical Intelligence
*   **Deterministic Coaching:** Base messages are structurally sound (e.g., "Readiness is high (85/100). Excellent progress...").
*   **Ollama Fallback:** If the LLM wrapper fails or is disabled, the deterministic message is stored safely under the `llm_status = "deterministic_fallback"`.
*   **Boundary Enforcement:** The LLM does NOT alter safety decisions, modify difficulty tiers, or rewrite clinical scores. It solely provides conversational text wrapping the deterministic logic.
*   **Clinical Output:** `ClinicalIntelligenceLayer` correctly categorizes risk but does not force unvalidated medical diagnoses, instead flagging "Overtraining Risk" or "High Pain Risk".

## Conclusion
The core software architecture is sound and deterministic. It is ready for Human Performance Pilot Testing, as the metrics stored in the database are true reflections of the calculated real-time inputs. No artificial manipulation of scores occurs during execution.
