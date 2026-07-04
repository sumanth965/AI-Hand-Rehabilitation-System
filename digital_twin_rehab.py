"""
Personalized rehabilitation digital twin.

The twin summarizes a patient's rehabilitation trajectory and simulates
alternative therapy strategies. It is an explainable planning aid, not a
diagnostic or regulated clinical prediction model.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


DB_PATH = "rehab_data.db"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def avg(values: list[float], default: float = 0.0) -> float:
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else default


def trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    recent = values[-5:] if len(values) >= 5 else values
    return recent[-1] - recent[0]


@dataclass
class TwinScenario:
    name: str
    strategy: str
    recovery_timeline_weeks: float
    expected_rom: float
    expected_accuracy: float
    risk_level: str
    fatigue_risk: float
    compensation_risk: float
    adherence_impact: str
    explanation: str


@dataclass
class DigitalTwinProfile:
    patient_id: str
    sessions_count: int
    current_rom: float
    current_accuracy: float
    current_pain: float
    readiness_score: float
    consistency_score: float
    fatigue_index: float
    compensation_score: float
    forearm_quality: float
    recovery_velocity: float
    risks: dict[str, float]
    scenarios: list[TwinScenario] = field(default_factory=list)
    recommendations: dict[str, Any] = field(default_factory=dict)
    milestones: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["scenarios"] = [asdict(item) for item in self.scenarios]
        return data


class DigitalTwinRehabModel:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS digital_twin_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    current_rom REAL DEFAULT 0,
                    current_accuracy REAL DEFAULT 0,
                    readiness_score REAL DEFAULT 0,
                    recovery_velocity REAL DEFAULT 0,
                    stagnation_risk REAL DEFAULT 0,
                    overtraining_risk REAL DEFAULT 0,
                    high_pain_risk REAL DEFAULT 0,
                    compensation_risk REAL DEFAULT 0,
                    dropout_risk REAL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def build(self, patient_id: str, save: bool = True) -> DigitalTwinProfile:
        sessions = self._sessions(patient_id)
        prescriptions = self._adaptive_prescriptions(patient_id)
        overrides = self._overrides(patient_id)
        forearm = self._optional_rows("forearm_assessments", patient_id)
        upper_limb = self._optional_rows("upper_limb_assessments", patient_id)

        rom_values = [number(row["avg_hand_angle"]) for row in sessions]
        acc_values = [number(row["avg_accuracy"]) for row in sessions]
        pain_values = [number(row["pain_level"]) for row in sessions]
        duration_values = [number(row["duration"]) for row in sessions]
        readiness_values = [number(row["readiness_score"]) for row in prescriptions]
        compensation_values = [number(row["compensation_score"]) for row in upper_limb]
        forearm_quality_values = [
            clamp(number(row["smoothness"]) - number(row["compensation_score"]), 0.0, 1.0) * 100.0
            for row in forearm
        ]

        current_rom = rom_values[-1] if rom_values else 0.0
        current_accuracy = acc_values[-1] if acc_values else 0.0
        current_pain = pain_values[-1] if pain_values else 0.0
        readiness = readiness_values[-1] if readiness_values else self._readiness(current_accuracy, current_rom, current_pain)
        consistency = self._consistency(sessions)
        fatigue = self._fatigue(duration_values, pain_values)
        compensation = avg(compensation_values, 0.0)
        forearm_quality = avg(forearm_quality_values, 70.0)
        recovery_velocity = self._weekly_rom_velocity(sessions)
        override_rate = self._override_rate(overrides)

        risks = self._risks(
            sessions=sessions,
            rom_values=rom_values,
            acc_values=acc_values,
            pain_values=pain_values,
            readiness=readiness,
            consistency=consistency,
            fatigue=fatigue,
            compensation=compensation,
            override_rate=override_rate,
        )
        scenarios = self._scenarios(current_rom, current_accuracy, recovery_velocity, risks, readiness, consistency)
        recommendations = self._recommendations(current_rom, current_accuracy, current_pain, readiness, risks, scenarios)
        milestones = self._milestones(current_rom, current_accuracy, scenarios[0])

        profile = DigitalTwinProfile(
            patient_id=patient_id,
            sessions_count=len(sessions),
            current_rom=round(current_rom, 1),
            current_accuracy=round(current_accuracy, 1),
            current_pain=round(current_pain, 1),
            readiness_score=round(readiness, 1),
            consistency_score=round(consistency * 100.0, 1),
            fatigue_index=round(fatigue * 100.0, 1),
            compensation_score=round(compensation * 100.0, 1),
            forearm_quality=round(forearm_quality, 1),
            recovery_velocity=round(recovery_velocity, 2),
            risks=risks,
            scenarios=scenarios,
            recommendations=recommendations,
            milestones=milestones,
            explanation=self._explanation(readiness, recovery_velocity, risks, override_rate),
        )
        if save:
            self.save_snapshot(profile)
        return profile

    def save_snapshot(self, profile: DigitalTwinProfile) -> None:
        risks = profile.risks
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO digital_twin_snapshots (
                    patient_id, snapshot_json, current_rom, current_accuracy,
                    readiness_score, recovery_velocity, stagnation_risk,
                    overtraining_risk, high_pain_risk, compensation_risk, dropout_risk
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.patient_id,
                    json.dumps(profile.to_dict(), sort_keys=True),
                    profile.current_rom,
                    profile.current_accuracy,
                    profile.readiness_score,
                    profile.recovery_velocity,
                    risks.get("recovery_stagnation", 0.0),
                    risks.get("overtraining", 0.0),
                    risks.get("high_pain", 0.0),
                    risks.get("compensation", 0.0),
                    risks.get("dropout", 0.0),
                ),
            )
            conn.commit()

    def snapshot_history(self, patient_id: str, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM digital_twin_snapshots
                WHERE patient_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()

    def _sessions(self, patient_id: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM sessions
                WHERE patient_id = ?
                ORDER BY datetime(timestamp) ASC, id ASC
                LIMIT 80
                """,
                (patient_id,),
            ).fetchall()

    def _adaptive_prescriptions(self, patient_id: str) -> list[sqlite3.Row]:
        try:
            with self.connect() as conn:
                return conn.execute(
                    """
                    SELECT *
                    FROM adaptive_prescriptions
                    WHERE patient_id = ?
                    ORDER BY datetime(created_at) ASC, id ASC
                    LIMIT 80
                    """,
                    (patient_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []

    def _overrides(self, patient_id: str) -> list[sqlite3.Row]:
        try:
            with self.connect() as conn:
                return conn.execute(
                    """
                    SELECT *
                    FROM therapist_overrides
                    WHERE patient_id = ?
                    ORDER BY datetime(created_at) ASC, id ASC
                    LIMIT 80
                    """,
                    (patient_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []

    def _optional_rows(self, table: str, patient_id: str) -> list[sqlite3.Row]:
        try:
            with self.connect() as conn:
                return conn.execute(
                    f"SELECT * FROM {table} WHERE patient_id = ? ORDER BY datetime(created_at) ASC, id ASC LIMIT 80",
                    (patient_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []

    def _readiness(self, accuracy: float, rom: float, pain: float) -> float:
        return clamp(0.38 * accuracy + 0.32 * clamp(rom / 90.0 * 100.0, 0.0, 100.0) + 0.30 * (100.0 - pain * 10.0), 0.0, 100.0)

    def _consistency(self, sessions: list[sqlite3.Row]) -> float:
        stamps = []
        for row in sessions:
            try:
                stamps.append(datetime.fromisoformat(str(row["timestamp"])))
            except ValueError:
                continue
        if len(stamps) < 2:
            return 0.5
        gaps = [(b - a).total_seconds() / 86400.0 for a, b in zip(stamps, stamps[1:])]
        avg_gap = sum(gaps) / len(gaps)
        return clamp(1.0 - avg_gap / 10.0, 0.0, 1.0)

    def _fatigue(self, durations: list[float], pain_values: list[float]) -> float:
        if not durations:
            return 0.0
        recent_duration = avg(durations[-4:], 0.0)
        duration_load = clamp((recent_duration - 45.0) / 90.0, 0.0, 1.0)
        pain_load = clamp(avg(pain_values[-4:], 0.0) / 10.0, 0.0, 1.0)
        return clamp(0.55 * duration_load + 0.45 * pain_load, 0.0, 1.0)

    def _weekly_rom_velocity(self, sessions: list[sqlite3.Row]) -> float:
        if len(sessions) < 2:
            return 0.0
        try:
            start = datetime.fromisoformat(str(sessions[0]["timestamp"]))
            end = datetime.fromisoformat(str(sessions[-1]["timestamp"]))
            days = max((end - start).total_seconds() / 86400.0, 1.0)
        except ValueError:
            days = max(len(sessions) - 1, 1)
        return (number(sessions[-1]["avg_hand_angle"]) - number(sessions[0]["avg_hand_angle"])) / days * 7.0

    def _override_rate(self, overrides: list[sqlite3.Row]) -> float:
        if not overrides:
            return 0.0
        non_accept = sum(1 for row in overrides if str(row["decision"]).lower() != "accept")
        return non_accept / len(overrides)

    def _risks(
        self,
        sessions: list[sqlite3.Row],
        rom_values: list[float],
        acc_values: list[float],
        pain_values: list[float],
        readiness: float,
        consistency: float,
        fatigue: float,
        compensation: float,
        override_rate: float,
    ) -> dict[str, float]:
        rom_trend = trend(rom_values)
        acc_trend = trend(acc_values)
        pain_trend = trend(pain_values)
        stagnation = clamp((1.0 if abs(rom_trend) < 2 and len(sessions) >= 4 else 0.25) + max(0.0, -acc_trend) / 50.0, 0.0, 1.0)
        overtraining = clamp(0.55 * fatigue + 0.30 * max(0.0, pain_trend) / 5.0 + 0.15 * compensation, 0.0, 1.0)
        high_pain = clamp(avg(pain_values[-4:], 0.0) / 10.0 + max(0.0, pain_trend) / 8.0, 0.0, 1.0)
        compensation_risk = clamp(compensation + max(0.0, -acc_trend) / 120.0, 0.0, 1.0)
        dropout = clamp((1.0 - consistency) * 0.55 + high_pain * 0.25 + override_rate * 0.20, 0.0, 1.0)
        return {
            "recovery_stagnation": round(stagnation * 100.0, 1),
            "overtraining": round(overtraining * 100.0, 1),
            "high_pain": round(high_pain * 100.0, 1),
            "compensation": round(compensation_risk * 100.0, 1),
            "dropout": round(dropout * 100.0, 1),
            "overall": round((stagnation + overtraining + high_pain + compensation_risk + dropout) / 5.0 * 100.0, 1),
        }

    def _scenarios(
        self,
        current_rom: float,
        current_accuracy: float,
        velocity: float,
        risks: dict[str, float],
        readiness: float,
        consistency: float,
    ) -> list[TwinScenario]:
        base_velocity = max(velocity, 1.5 if readiness >= 60 else 0.8)
        return [
            self._scenario("A", "Current plan continues", current_rom, current_accuracy, base_velocity, risks, 1.0, consistency),
            self._scenario("B", "Increased rehabilitation intensity", current_rom, current_accuracy, base_velocity, risks, 1.35, consistency),
            self._scenario("C", "Reduced rehabilitation intensity", current_rom, current_accuracy, base_velocity, risks, 0.65, consistency),
        ]

    def _scenario(
        self,
        name: str,
        strategy: str,
        current_rom: float,
        current_accuracy: float,
        base_velocity: float,
        risks: dict[str, float],
        intensity: float,
        consistency: float,
    ) -> TwinScenario:
        target_rom = 90.0
        effective_velocity = max(0.2, base_velocity * intensity * (0.75 + consistency * 0.25))
        weeks = clamp((target_rom - current_rom) / effective_velocity, 1.0, 52.0) if current_rom < target_rom else 1.0
        expected_rom = clamp(current_rom + effective_velocity * 4.0, 0.0, 100.0)
        expected_accuracy = clamp(current_accuracy + (effective_velocity * 0.75) - max(0.0, intensity - 1.0) * 2.0, 0.0, 100.0)
        fatigue_risk = clamp(risks["overtraining"] / 100.0 + max(0.0, intensity - 1.0) * 0.35, 0.0, 1.0)
        compensation_risk = clamp(risks["compensation"] / 100.0 + max(0.0, intensity - 1.0) * 0.22 - max(0.0, 1.0 - intensity) * 0.12, 0.0, 1.0)
        risk_value = (risks["overall"] / 100.0 + fatigue_risk + compensation_risk) / 3.0
        risk_level = "Low" if risk_value < 0.33 else "Moderate" if risk_value < 0.66 else "High"
        if intensity > 1.0:
            adherence = "May reduce adherence if fatigue or pain rises."
            explanation = "Faster ROM gains are possible, but fatigue and compensation risks increase."
        elif intensity < 1.0:
            adherence = "May improve adherence and safety but delay recovery."
            explanation = "Lower load reduces safety risk while slowing expected ROM gains."
        else:
            adherence = "Maintains current adherence pattern."
            explanation = "Forecast follows the current recovery velocity and consistency."
        return TwinScenario(
            name=f"Scenario {name}",
            strategy=strategy,
            recovery_timeline_weeks=round(weeks, 1),
            expected_rom=round(expected_rom, 1),
            expected_accuracy=round(expected_accuracy, 1),
            risk_level=risk_level,
            fatigue_risk=round(fatigue_risk * 100.0, 1),
            compensation_risk=round(compensation_risk * 100.0, 1),
            adherence_impact=adherence,
            explanation=explanation,
        )

    def _recommendations(
        self,
        rom: float,
        accuracy: float,
        pain: float,
        readiness: float,
        risks: dict[str, float],
        scenarios: list[TwinScenario],
    ) -> dict[str, Any]:
        best = min(scenarios, key=lambda item: (0 if item.risk_level == "Low" else 1 if item.risk_level == "Moderate" else 2, item.recovery_timeline_weeks))
        if risks["high_pain"] >= 60 or pain >= 6:
            duration = "15-20 minutes"
            progression = "Regress or support until pain stabilizes"
        elif readiness >= 75 and risks["overtraining"] < 45:
            duration = "30-40 minutes"
            progression = "Advance one tier after two low-pain sessions"
        else:
            duration = "20-30 minutes"
            progression = "Maintain current tier and increase precision"
        exercise_mix = ["ROM calibration", "Rotation Orbit", "Grip release"]
        if accuracy < 65:
            exercise_mix.append("Path tracing")
        if rom >= 55:
            exercise_mix.append("Smart Assembly")
        if risks["compensation"] >= 55:
            exercise_mix.append("Slow controlled forearm holds")
        return {
            "best_strategy": best.name,
            "best_exercise_mix": exercise_mix,
            "optimal_session_duration": duration,
            "weekly_targets": {
                "sessions": 4 if readiness >= 60 else 3,
                "rom_gain_degrees": 4 if readiness >= 60 else 2,
                "pain_ceiling": "Keep pain <= 4/10",
                "accuracy_target": f"{min(95, max(70, accuracy + 5)):.0f}%",
            },
            "difficulty_progression_plan": progression,
        }

    def _milestones(self, rom: float, accuracy: float, scenario: TwinScenario) -> list[str]:
        milestones = []
        for target in [45, 60, 75, 90]:
            if rom < target:
                weeks = max(1.0, (target - rom) / max((scenario.expected_rom - rom) / 4.0, 0.5))
                milestones.append(f"Reach {target} deg ROM in about {weeks:.1f} weeks.")
                break
        if accuracy < 80:
            milestones.append(f"Reach 80% exercise accuracy in about {max(1.0, (80 - accuracy) / 5.0):.1f} weeks.")
        milestones.append(f"Review digital twin forecast after {scenario.recovery_timeline_weeks:.1f} weeks or earlier if pain rises.")
        return milestones

    def _explanation(self, readiness: float, velocity: float, risks: dict[str, float], override_rate: float) -> str:
        return (
            f"The twin estimates readiness at {readiness:.0f}/100 with ROM velocity {velocity:+.1f} deg/week. "
            f"Main risks are stagnation {risks['recovery_stagnation']:.0f}%, pain {risks['high_pain']:.0f}%, "
            f"compensation {risks['compensation']:.0f}%, and dropout {risks['dropout']:.0f}%. "
            f"Therapist override rate is {override_rate * 100:.0f}%."
        )
