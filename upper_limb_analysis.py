"""
Upper limb biomechanics and compensation analysis.

This module uses MediaPipe Pose landmarks to estimate shoulder, elbow, trunk,
and forearm compensation during hand rehabilitation. It is intentionally
explainable and conservative: metrics are approximate 2-D webcam estimates, not
clinical goniometer measurements.
"""

from __future__ import annotations

import math
import sqlite3
import security_utils
from dataclasses import asdict, dataclass
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def angle_3pt(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    """Angle ABC in degrees."""
    bax = a[0] - b[0]
    bay = a[1] - b[1]
    bcx = c[0] - b[0]
    bcy = c[1] - b[1]
    denom = math.hypot(bax, bay) * math.hypot(bcx, bcy)
    if denom <= 1e-9:
        return 0.0
    cos_val = clamp((bax * bcx + bay * bcy) / denom, -1.0, 1.0)
    return math.degrees(math.acos(cos_val))


def line_angle(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


@dataclass
class UpperLimbMetrics:
    shoulder_angle: float = 0.0
    elbow_angle: float = 0.0
    forearm_rotation_angle: float = 0.0
    trunk_lean_angle: float = 0.0
    shoulder_compensation: float = 0.0
    elbow_compensation: float = 0.0
    trunk_compensation: float = 0.0
    compensation_score: float = 0.0
    movement_efficiency: float = 100.0
    shoulder_elevation: float = 0.0
    shoulder_abduction: float = 0.0
    elbow_drift: float = 0.0
    trunk_shift: float = 0.0
    feedback: str = "Good forearm rotation."
    side: str = "Unknown"

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


class UpperLimbAnalyzer:
    """Computes upper-limb compensation metrics from MediaPipe Pose landmarks."""

    def __init__(self):
        self.baselines: dict[str, dict[str, float]] = {}

    def analyze(
        self,
        pose_landmarks: Any,
        pose_enum: Any,
        frame_width: int,
        frame_height: int,
        game_width: int,
        game_height: int,
        hand_wrist: tuple[int, int] | None,
        hand_rotation_angle: float,
        hand_label: str = "Unknown",
    ) -> UpperLimbMetrics:
        if pose_landmarks is None:
            return UpperLimbMetrics(feedback="Pose not visible. Keep shoulder, elbow, and torso in view.")

        points = self._extract_points(pose_landmarks, pose_enum, frame_width, frame_height, game_width, game_height)
        side = self._select_side(points, hand_wrist, hand_label)
        prefix = "left" if side == "Left" else "right"
        shoulder = points[f"{prefix}_shoulder"]
        elbow = points[f"{prefix}_elbow"]
        wrist = points[f"{prefix}_wrist"]
        opposite_shoulder = points["right_shoulder"] if side == "Left" else points["left_shoulder"]
        hip_mid = ((points["left_hip"][0] + points["right_hip"][0]) / 2, (points["left_hip"][1] + points["right_hip"][1]) / 2)
        shoulder_mid = ((points["left_shoulder"][0] + points["right_shoulder"][0]) / 2, (points["left_shoulder"][1] + points["right_shoulder"][1]) / 2)

        shoulder_width = max(math.dist(points["left_shoulder"], points["right_shoulder"]), 1.0)
        torso_height = max(math.dist(shoulder_mid, hip_mid), 1.0)
        upper_arm_len = max(math.dist(shoulder, elbow), 1.0)

        baseline = self._baseline(side, points, shoulder, elbow, shoulder_mid, hip_mid)

        shoulder_angle = angle_3pt(opposite_shoulder, shoulder, elbow)
        elbow_angle = angle_3pt(shoulder, elbow, wrist)
        trunk_line = line_angle(hip_mid, shoulder_mid)
        trunk_lean = abs(90.0 - abs(trunk_line))

        shoulder_elevation = max(0.0, (baseline["shoulder_y"] - shoulder[1]) / torso_height)
        shoulder_abduction = max(0.0, abs(elbow[0] - shoulder[0]) / shoulder_width - baseline["abduction"])
        elbow_drift = math.dist(elbow, (baseline["elbow_x"], baseline["elbow_y"])) / upper_arm_len
        trunk_shift = abs(shoulder_mid[0] - baseline["shoulder_mid_x"]) / shoulder_width
        trunk_change = max(0.0, trunk_lean - baseline["trunk_lean"])

        shoulder_comp = clamp(max(shoulder_elevation / 0.18, shoulder_abduction / 0.35), 0.0, 1.0)
        elbow_comp = clamp(max(elbow_drift / 0.35, abs(elbow_angle - baseline["elbow_angle"]) / 45.0), 0.0, 1.0)
        trunk_comp = clamp(max(trunk_shift / 0.20, trunk_change / 18.0), 0.0, 1.0)
        compensation = clamp(0.40 * shoulder_comp + 0.35 * elbow_comp + 0.25 * trunk_comp, 0.0, 1.0)
        efficiency = clamp(100.0 * (1.0 - compensation), 0.0, 100.0)
        feedback = self.feedback(shoulder_comp, elbow_comp, trunk_comp)

        return UpperLimbMetrics(
            shoulder_angle=round(shoulder_angle, 1),
            elbow_angle=round(elbow_angle, 1),
            forearm_rotation_angle=round(hand_rotation_angle, 1),
            trunk_lean_angle=round(trunk_lean, 1),
            shoulder_compensation=round(shoulder_comp, 3),
            elbow_compensation=round(elbow_comp, 3),
            trunk_compensation=round(trunk_comp, 3),
            compensation_score=round(compensation, 3),
            movement_efficiency=round(efficiency, 1),
            shoulder_elevation=round(shoulder_elevation, 3),
            shoulder_abduction=round(shoulder_abduction, 3),
            elbow_drift=round(elbow_drift, 3),
            trunk_shift=round(trunk_shift, 3),
            feedback=feedback,
            side=side,
        )

    def feedback(self, shoulder_comp: float, elbow_comp: float, trunk_comp: float) -> str:
        if shoulder_comp >= 0.55:
            return "Avoid lifting your shoulder."
        if elbow_comp >= 0.55:
            return "Try keeping your elbow stable."
        if trunk_comp >= 0.55:
            return "Reduce trunk movement during exercise."
        return "Good forearm rotation."

    def _extract_points(
        self,
        pose_landmarks: Any,
        pose_enum: Any,
        frame_width: int,
        frame_height: int,
        game_width: int,
        game_height: int,
    ) -> dict[str, tuple[float, float]]:
        def pt(name: str) -> tuple[float, float]:
            landmark = pose_landmarks.landmark[getattr(pose_enum, name).value]
            return (landmark.x * game_width, landmark.y * game_height)

        return {
            "left_shoulder": pt("LEFT_SHOULDER"),
            "right_shoulder": pt("RIGHT_SHOULDER"),
            "left_elbow": pt("LEFT_ELBOW"),
            "right_elbow": pt("RIGHT_ELBOW"),
            "left_wrist": pt("LEFT_WRIST"),
            "right_wrist": pt("RIGHT_WRIST"),
            "left_hip": pt("LEFT_HIP"),
            "right_hip": pt("RIGHT_HIP"),
        }

    def _select_side(
        self,
        points: dict[str, tuple[float, float]],
        hand_wrist: tuple[int, int] | None,
        hand_label: str,
    ) -> str:
        if hand_wrist:
            left_dist = math.dist(hand_wrist, points["left_wrist"])
            right_dist = math.dist(hand_wrist, points["right_wrist"])
            return "Left" if left_dist <= right_dist else "Right"
        return "Left" if hand_label == "Left" else "Right"

    def _baseline(
        self,
        side: str,
        points: dict[str, tuple[float, float]],
        shoulder: tuple[float, float],
        elbow: tuple[float, float],
        shoulder_mid: tuple[float, float],
        hip_mid: tuple[float, float],
    ) -> dict[str, float]:
        if side not in self.baselines:
            opposite_shoulder = points["right_shoulder"] if side == "Left" else points["left_shoulder"]
            wrist = points["left_wrist"] if side == "Left" else points["right_wrist"]
            trunk_line = line_angle(hip_mid, shoulder_mid)
            self.baselines[side] = {
                "shoulder_y": shoulder[1],
                "shoulder_mid_x": shoulder_mid[0],
                "elbow_x": elbow[0],
                "elbow_y": elbow[1],
                "abduction": abs(elbow[0] - shoulder[0]) / max(math.dist(points["left_shoulder"], points["right_shoulder"]), 1.0),
                "elbow_angle": angle_3pt(shoulder, elbow, wrist),
                "trunk_lean": abs(90.0 - abs(trunk_line)),
                "opposite_shoulder_x": opposite_shoulder[0],
            }
        return self.baselines[side]


def ensure_upper_limb_schema(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upper_limb_assessments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                session_id INTEGER,
                level INTEGER,
                shoulder_angle REAL DEFAULT 0,
                elbow_angle REAL DEFAULT 0,
                forearm_rotation_angle REAL DEFAULT 0,
                trunk_lean_angle REAL DEFAULT 0,
                shoulder_compensation REAL DEFAULT 0,
                elbow_compensation REAL DEFAULT 0,
                trunk_compensation REAL DEFAULT 0,
                compensation_score REAL DEFAULT 0,
                movement_efficiency REAL DEFAULT 100,
                feedback TEXT DEFAULT '',
                side TEXT DEFAULT 'Unknown',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for column, definition in [
            ("shoulder_angle", "REAL DEFAULT 0"),
            ("elbow_angle", "REAL DEFAULT 0"),
            ("forearm_rotation_angle", "REAL DEFAULT 0"),
            ("trunk_lean_angle", "REAL DEFAULT 0"),
            ("shoulder_compensation", "REAL DEFAULT 0"),
            ("elbow_compensation", "REAL DEFAULT 0"),
            ("trunk_compensation", "REAL DEFAULT 0"),
            ("compensation_score", "REAL DEFAULT 0"),
            ("movement_efficiency", "REAL DEFAULT 100"),
            ("feedback", "TEXT DEFAULT ''"),
            ("side", "TEXT DEFAULT 'Unknown'"),
        ]:
            try:
                conn.execute(f"SELECT {column} FROM upper_limb_assessments LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(f"ALTER TABLE upper_limb_assessments ADD COLUMN {column} {definition}")
        conn.commit()


def save_upper_limb_assessment(
    db_path: str,
    patient_id: str,
    level: int,
    metrics: dict[str, Any],
    session_id: int | None = None,
) -> None:
    ensure_upper_limb_schema(db_path)
    enc_patient = security_utils.encrypt_deterministic(patient_id)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO upper_limb_assessments (
                patient_id, session_id, level, shoulder_angle, elbow_angle,
                forearm_rotation_angle, trunk_lean_angle, shoulder_compensation,
                elbow_compensation, trunk_compensation, compensation_score,
                movement_efficiency, feedback, side
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                enc_patient,
                session_id,
                level,
                number(metrics.get("shoulder_angle")),
                number(metrics.get("elbow_angle")),
                number(metrics.get("forearm_rotation_angle")),
                number(metrics.get("trunk_lean_angle")),
                number(metrics.get("shoulder_compensation")),
                number(metrics.get("elbow_compensation")),
                number(metrics.get("trunk_compensation")),
                number(metrics.get("compensation_score")),
                number(metrics.get("movement_efficiency"), 100.0),
                str(metrics.get("feedback", "")),
                str(metrics.get("side", "Unknown")),
            ),
        )
        conn.commit()
