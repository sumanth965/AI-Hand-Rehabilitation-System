# DATA QUALITY REPORT & CHECKS

To maintain research integrity, any script analyzing the exported `RESEARCH_DATASET_TEMPLATE.csv` must perform the following automated quality checks before statistical analysis.

## 1. Missing Values (Null Check)
*   **Rule:** Every session MUST have a value for `Participant_ID`, `Session_ID`, `Exercise`, `Pain_Before`, `Pain_After`, `ROM`, and `Accuracy`.
*   **Exception:** `Recovery_Prediction` may be `NULL` for the first 2 sessions of a new participant, as the Digital Twin requires at least 3 sessions to generate a linear regression.

## 2. Invalid Ranges (Bounds Check)
*   **Pain Levels:** Ensure `Pain_Before` and `Pain_After` are strictly between `0` and `10`.
*   **Pain Delta:** Must mathematically equal `Pain_After - Pain_Before`.
*   **Accuracy:** Must be between `0.0` and `100.0`. Values > 100 suggest a target logic bug in `physio/game_parts/`.
*   **ROM:** Expect values generally between `10.0` and `170.0`. A flat `0.0` or exactly `180.0` across a whole session indicates a MediaPipe hand-tracking failure, and that session should be flagged for manual review.
*   **Movement Quality & Readiness:** Must remain between `0.0` and `100.0` (or `0.0 - 1.0` if normalized).

## 3. Duplicate Rows
*   **Rule:** A `Session_ID` must be unique across the entire dataset.
*   **Rule:** A participant cannot have two sessions with the exact same `Timestamp` (down to the second).

## 4. Logical Inconsistencies
*   **Completion Time:** If `Completion_Time` < 5 seconds, flag as an accidentally aborted session. Do NOT delete it automatically, but exclude it from efficacy analysis.
*   **Session Order:** Ensure `Session_Number` increments logically according to `Timestamp` for a given `Participant_ID`.

## 5. Handling Anomalies
*   If a session triggers a quality flag, annotate the row with a `Quality_Flag` column (e.g., `"Tracking_Error"`, `"Aborted_Early"`).
*   **DO NOT DELETE ROWS.** Preserve all recorded data. Use filters during statistical analysis rather than permanent deletion, to allow calculation of software dropout/failure rates.
