# BUG REPORT & POTENTIAL ISSUES

Based on the static inspection and logic tracing for the research deployment, the following priority issues/bugs were identified that might affect data collection or edge-cases during human pilot testing.

## MEDIUM PRIORITY

### 1. Hardcoded ID Dependency in Dashboard Note Decryption
- **File:** `admin_dashboard/database.py` (Line ~65)
- **Function:** `decrypt_row_fields`
- **Problem:** Deterministic decryption relies on exact key lists (`'patient_name', 'id_number'`). If a database row lacks these specific keys during a left join, it might silently fail to decrypt or crash.
- **Reproduction steps:** Generate a new patient session without an `id_number`, open dashboard.
- **Expected behavior:** Safe parsing of `None` values without throwing a `TypeError`.
- **Actual behavior:** Handled generally well in Python, but edge cases in SQLite `LEFT JOIN` where `id_number` is missing can cause display bugs.
- **Suggested fix:** Ensure `.get()` is strictly used before running decryption functions.

### 2. Digital Twin Prediction Stagnation
- **File:** `physio/database.py` (Line ~450)
- **Function:** `predict_recovery_progress`
- **Problem:** Requires at least 3 sessions to function. If 2 sessions are passed, it returns `-1.0`. The dashboard may not parse `-1.0` gracefully, displaying negative recovery.
- **Reproduction steps:** Complete 2 sessions, view Digital Twin prediction.
- **Expected behavior:** "Insufficient Data" displayed on the frontend.
- **Actual behavior:** Could yield `-1.0%` recovery.
- **Suggested fix:** Add a strict UI constraint in `admin_dashboard` to parse `-1.0` as "Need more data".

## LOW PRIORITY

### 3. Matplotlib Dashboard Generation on Headless Linux
- **File:** `physio/database.py` (Line ~487)
- **Function:** `render_matplotlib_dashboard`
- **Problem:** Relies on `matplotlib.use("Agg")`. If certain C-libraries are missing during a headless research deployment, generating the UI graphs might crash.
- **Reproduction steps:** Run PyGame instance without X-server or missing `libfreetype`.
- **Expected behavior:** Graceful bypass of matplotlib.
- **Actual behavior:** Returns a black Pygame surface with a text warning (handled reasonably well, but logs an exception).
- **Suggested fix:** N/A - Already mitigated by try-except block, but note for researcher environments.

### 4. Overlap in Compensation Heuristics
- **File:** `upper_limb_analysis.py` (Line ~115)
- **Function:** `analyze`
- **Problem:** Shoulder elevation and trunk lean are intertwined in 2D space. The heuristic assigns separate penalty multipliers but they may double-penalize a single bad posture.
- **Reproduction steps:** Lean heavily to the side during exercise.
- **Expected behavior:** Flag trunk lean.
- **Actual behavior:** Flags trunk lean AND shoulder elevation.
- **Suggested fix:** Document in `RESEARCH_METRICS_DOCUMENTATION` that these values are strictly heuristic and may exhibit multicollinearity during statistical analysis. No code change required right now.
