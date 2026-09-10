# PILOT TESTING PROTOCOL
**AI Hand Rehabilitation System**

This protocol governs the pilot data collection phase. 
*Note: This does not constitute clinical validation. It is for human performance testing and software usability analysis.*

## 1. Participant Anonymization
*   **Participant ID:** Use format `P001`, `P002`, `P003`...
*   **No PII:** Do not collect names, exact birthdates, or contact information in the dataset.
*   **Basic Demographics:** Collect only `Age Group`, `Gender` (if scientifically justified), `Dominant Hand`, and `Experience/Group`.

## 2. Session Structure

### Phase 1: Baseline Session
*   **Purpose:** Establish the starting parameters for the participant.
*   **Action:** The participant completes the fundamental calibration and the first exercise tier without adaptive difficulty changes.
*   **Recording:** The system must record `Pain Before`, `ROM`, `Accuracy`, `Smoothness`, `Completion Time`, `Compensation Events`, `Readiness`, and `Difficulty`.
*   **Rule:** Do NOT allow the Adaptive AI to alter the difficulty during the baseline session. Label this session explicitly as `Session 1 (Baseline)`.

### Phase 2: Repeated Sessions (Longitudinal Observation)
*   **Purpose:** Observe system stability and participant trends over repeated uses.
*   **Action:** 
    *   Session 2: Adaptive Difficulty Active
    *   Session 3: Adaptive Difficulty Active
    *   Session 4: Adaptive Difficulty Active
    *   Session 5: Adaptive Difficulty Active
*   **Recording:** Record identical metrics. The goal is to observe trend generation in the `digital_twin_rehab.py` algorithms, rather than to make medical claims of treatment effectiveness.

### Phase 3: Controlled Comparisons (Where Feasible)
*   **Purpose:** Validate the effectiveness of the Adaptive Difficulty vs Fixed Difficulty.
*   **Action:**
    *   Group A: 5 Sessions Fixed Difficulty (Tier 3).
    *   Group B: 5 Sessions Adaptive Difficulty (AI Engine active).
*   **Comparison Metrics:** Accuracy, ROM, Compensation, Pain Delta, Session Completion Rates.

## 3. Data Integrity Rules
*   **DO NOT** generate fake clinical results.
*   **DO NOT** modify scores to artificially improve results.
*   **DO NOT** delete poor-performing or failed sessions. Failed sessions are valid research data points indicating software friction or participant fatigue.
*   **DO NOT** present heuristic-based values (e.g., `Functional Recovery Score`) as clinically validated measures in the research paper.
