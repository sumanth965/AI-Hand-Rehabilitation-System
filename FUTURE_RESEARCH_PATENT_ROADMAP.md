# Adaptive AI Rehabilitation Platform Roadmap

## Core Novelty

The project's patent-oriented novelty is not generic webcam hand tracking. The
core invention is a system and method that automatically personalizes
rehabilitation exercises, coaching, game difficulty, and level progression using:

- Real-time biomechanical measurements from hand and forearm motion.
- Patient-specific rehabilitation history.
- Recovery prediction trends.
- Session performance metrics such as accuracy, ROM, pain, fatigue, consistency,
  movement quality, and rotation smoothness.
- Exercise classification for forearm pronation, supination, rotation holds,
  endurance, smooth rotation, and compensatory movement.

## Implemented Adaptive Engine

`adaptive_ai_engine.py` introduces an explainable personalization layer with
three durable data streams:

- `adaptive_prescriptions`: next-session difficulty tier, target scale, speed
  scale, ROM requirement, time limit, repetitions, hold time, tolerance, risk,
  and rationale.
- `forearm_assessments`: latest forearm movement class, rotation angle,
  smoothness, compensation score, and endurance.
- `sensei_messages`: context-aware coaching messages linked to session and
  prescription context.

The runtime now applies the latest prescription at level start and saves a new
prescription at level completion. This creates a closed-loop rehabilitation
cycle:

1. Measure patient performance.
2. Classify movement quality and safety risk.
3. Generate a transparent next-session prescription.
4. Adapt the next exercise without therapist intervention.
5. Expose rationale to the therapist dashboard.

## Adaptive Difficulty Variables

The current implementation adapts:

- Target size through `target_scale`.
- Movement speed through `speed_scale`.
- Session time limit.
- Rotation tolerance and hold duration in Rotation Orbit.
- Grab radius, placement tolerance, and angle tolerance in Smart Assembly.
- Guidance intensity and Sensei coaching messages.
- Level progression support through difficulty tiers 1-5.

## Forearm Classification

The classifier supports:

- Neutral Position
- Pronation
- Supination
- Partial Pronation
- Partial Supination
- Rotation Hold
- Rotation Endurance
- Smooth Rotation
- Compensatory Movement Detection

Current inputs use MediaPipe Hands wrist rotation and wrist deviation. Future
MediaPipe Pose integration should add elbow and shoulder landmarks to separate
true forearm rotation from shoulder abduction, trunk lean, and elbow drift.

## Research Objectives

Recommended study questions:

- Does adaptive difficulty improve ROM and accuracy compared with fixed
  difficulty rehabilitation games?
- Does personalized progression improve session adherence and completion rate?
- Does contextual coaching reduce missed sessions or increase correct movement
  repetitions?
- Does forearm classification improve therapeutic specificity for pronation and
  supination rehabilitation?

Suggested measurable endpoints:

- ROM improvement per week.
- Average accuracy and movement smoothness.
- Pain-adjusted performance score.
- Session consistency and dropout rate.
- Number of therapist overrides required.
- Compensatory movement frequency.

## Patent Claim Direction

Potential independent claim theme:

A computer-implemented rehabilitation method that receives real-time
biomechanical motion measurements, retrieves patient-specific rehabilitation
history, computes a recovery and safety state, classifies therapeutic movement
quality, and automatically modifies exercise difficulty, feedback, and
progression parameters for a subsequent rehabilitation task.

Potential dependent claim themes:

- Difficulty adjustment using pain, ROM, accuracy, fatigue, and consistency.
- Forearm exercise classification from hand landmarks and future pose landmarks.
- Context-aware coaching generated from current and previous sessions.
- Therapist dashboard presenting adaptive rationale and risk state.
- Adaptive game mechanics that map clinical prescriptions onto target size,
  time limits, repetition count, hold duration, and rotation tolerance.

## Clinical Safety Notes

This software remains a research prototype. It should not be presented as a
regulated medical device without validation, clinician review, data protection,
risk management, and regulatory documentation. The adaptive engine is designed
to be explainable and conservative: high pain, low ROM, or low accuracy reduces
challenge before increasing difficulty.
