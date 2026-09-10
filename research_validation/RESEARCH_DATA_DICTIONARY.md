# RESEARCH DATA DICTIONARY

This data dictionary defines the columns present in the `RESEARCH_DATASET_TEMPLATE.csv`. It serves as the single source of truth for variables collected during the Human Performance Pilot Testing phase.

| Column Name | Data Type | Range/Format | Description | Database Source |
| :--- | :--- | :--- | :--- | :--- |
| `Participant_ID` | String | `P001`, `P002`... | Anonymized identifier for the research subject. | N/A (Derived from encrypted DB) |
| `Session_ID` | Integer | `1`, `2`... | Unique identifier for the recorded session. | `sessions.id` |
| `Session_Number` | Integer | `1`, `2`... | The sequential session number for this specific participant (e.g., Session 1 is Baseline). | Derived (Count of participant sessions) |
| `Exercise` | String | e.g. "Flexion" | The specific game or exercise mode active. | `sessions.level` (Mapped to string) |
| `Difficulty` | Integer | `1 - 5` | The difficulty tier dictated by the Adaptive Engine. | `adaptive_prescriptions.difficulty_tier` |
| `Pain_Before` | Integer | `0 - 10` | Subjective pain score reported prior to exercise. | `sessions.pain_before_session` |
| `Pain_After` | Integer | `0 - 10` | Subjective pain score reported post-exercise. | `sessions.pain_after_session` |
| `Pain_Delta` | Integer | `-10 to 10` | Calculated difference between `Pain_After` and `Pain_Before`. | `sessions.pain_difference` |
| `ROM` | Float | `0.0 - 180.0` | Average degrees of Hand/Wrist extension calculated via MediaPipe. | `sessions.avg_hand_angle` |
| `Accuracy` | Float | `0.0 - 100.0` | Percentage of game targets successfully reached. | `sessions.avg_accuracy` |
| `Movement_Quality` | Float | `0.0 - 1.0` | Heuristic penalty based on upper limb compensation detection. | `sessions.movement_quality_score` |
| `Completion_Time` | Float | Seconds | Total active time spent completing the session tier. | `sessions.duration` |
| `Compensation_Events` | Integer | `0 - N` | Total count of severe posture deviations flagged during session. | `clinical_summaries.compensation_events` |
| `Readiness_Score` | Float | `0.0 - 100.0` | Adaptive Engine's calculated readiness metric. | `adaptive_prescriptions.readiness_score` |
| `Recovery_Prediction` | Float | `%` | Digital Twin's predicted trajectory value. | `digital_twin_snapshots.recovery_velocity` |
| `Therapist_Override` | Boolean | `0 or 1` | `1` if a therapist rejected or modified the AI's prescription. | `therapist_overrides` |
| `Timestamp` | Datetime | ISO 8601 | The exact date and time the session was completed. | `sessions.timestamp` |
