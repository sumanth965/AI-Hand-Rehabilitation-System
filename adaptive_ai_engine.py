"""
Adaptive AI Rehabilitation Engine.

This module keeps the adaptive therapy logic separate from the Pygame runtime so
it can be reused by the therapist dashboard, reports, and future research code.
It does not claim clinical diagnosis. It produces explainable, rule-based
personalization from performance history, pain, ROM, movement quality, fatigue,
and forearm rotation classification.
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable

from llm_wrapper import enhance_coaching_message


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


@dataclass
class AdaptivePrescription:
    patient_id: str
    level: int
    difficulty_tier: int = 3
    readiness_score: float = 50.0
    target_scale: float = 1.0
    speed_scale: float = 1.0
    required_rom: float = 45.0
    time_limit: float = 30.0
    repetitions: int = 5
    hold_seconds: float = 1.5
    rotation_tolerance: float = 25.0
    assembly_position_tolerance: float = 50.0
    assembly_angle_tolerance: float = 30.0
    guidance_level: str = "standard"
    progression: str = "maintain"
    risk_level: str = "low"
    recovery_trend: str = "stable"
    override_recommendation: str = "No therapist override suggested."
    ai_confidence_score: float = 75.0
    override_probability: float = 0.25
    recommendation_reliability: float = 75.0
    rationale: str = "Baseline therapeutic difficulty."

    def as_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class AdaptiveRehabEngine:
    """Explainable personalization engine for rehabilitation difficulty."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS adaptive_prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER,
                    level INTEGER NOT NULL,
                    difficulty_tier INTEGER NOT NULL,
                    readiness_score REAL DEFAULT 50,
                    target_scale REAL NOT NULL,
                    speed_scale REAL NOT NULL,
                    required_rom REAL NOT NULL,
                    time_limit REAL NOT NULL,
                    repetitions INTEGER NOT NULL,
                    hold_seconds REAL NOT NULL,
                    rotation_tolerance REAL NOT NULL,
                    assembly_position_tolerance REAL NOT NULL,
                    assembly_angle_tolerance REAL NOT NULL,
                    guidance_level TEXT NOT NULL,
                    progression TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    recovery_trend TEXT DEFAULT 'stable',
                    override_recommendation TEXT DEFAULT 'No therapist override suggested.',
                    ai_confidence_score REAL DEFAULT 75,
                    override_probability REAL DEFAULT 0.25,
                    recommendation_reliability REAL DEFAULT 75,
                    explanation_json TEXT DEFAULT '{}',
                    rationale TEXT NOT NULL,
                    metrics_json TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS forearm_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER,
                    level INTEGER,
                    movement_class TEXT NOT NULL,
                    rotation_angle REAL NOT NULL,
                    smoothness REAL NOT NULL,
                    compensation_score REAL NOT NULL,
                    endurance_seconds REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sensei_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER,
                    level INTEGER,
                    message TEXT NOT NULL,
                    deterministic_message TEXT DEFAULT '',
                    llm_enhanced_message TEXT DEFAULT '',
                    coaching_trigger TEXT DEFAULT '',
                    decision_source TEXT DEFAULT 'Adaptive AI Engine',
                    llm_status TEXT DEFAULT 'not_requested',
                    context_json TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for column, definition in [
                ("deterministic_message", "TEXT DEFAULT ''"),
                ("llm_enhanced_message", "TEXT DEFAULT ''"),
                ("coaching_trigger", "TEXT DEFAULT ''"),
                ("decision_source", "TEXT DEFAULT 'Adaptive AI Engine'"),
                ("llm_status", "TEXT DEFAULT 'not_requested'"),
            ]:
                try:
                    conn.execute(f"SELECT {column} FROM sensei_messages LIMIT 1")
                except sqlite3.OperationalError:
                    conn.execute(f"ALTER TABLE sensei_messages ADD COLUMN {column} {definition}")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS therapist_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prescription_id INTEGER,
                    patient_id TEXT NOT NULL,
                    therapist_id TEXT DEFAULT 'Therapist',
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    therapist_reason TEXT DEFAULT '',
                    ai_recommendation_json TEXT DEFAULT '{}',
                    modified_recommendation_json TEXT DEFAULT '{}',
                    patient_context_json TEXT DEFAULT '{}',
                    session_metrics_json TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for column, definition in [
                ("readiness_score", "REAL DEFAULT 50"),
                ("recovery_trend", "TEXT DEFAULT 'stable'"),
                ("override_recommendation", "TEXT DEFAULT 'No therapist override suggested.'"),
                ("ai_confidence_score", "REAL DEFAULT 75"),
                ("override_probability", "REAL DEFAULT 0.25"),
                ("recommendation_reliability", "REAL DEFAULT 75"),
                ("explanation_json", "TEXT DEFAULT '{}'"),
            ]:
                try:
                    conn.execute(f"SELECT {column} FROM adaptive_prescriptions LIMIT 1")
                except sqlite3.OperationalError:
                    conn.execute(f"ALTER TABLE adaptive_prescriptions ADD COLUMN {column} {definition}")
            conn.commit()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def latest_prescription(self, patient_id: str, level: int) -> AdaptivePrescription:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM adaptive_prescriptions
                WHERE patient_id = ? AND level = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (patient_id, level),
            ).fetchone()
        if not row:
            return AdaptivePrescription(patient_id=patient_id, level=level)
        return AdaptivePrescription(
            patient_id=row["patient_id"],
            level=int(row["level"]),
            difficulty_tier=int(row["difficulty_tier"]),
            readiness_score=number(row["readiness_score"], 50.0),
            target_scale=number(row["target_scale"], 1.0),
            speed_scale=number(row["speed_scale"], 1.0),
            required_rom=number(row["required_rom"], 45.0),
            time_limit=number(row["time_limit"], 30.0),
            repetitions=int(number(row["repetitions"], 5)),
            hold_seconds=number(row["hold_seconds"], 1.5),
            rotation_tolerance=number(row["rotation_tolerance"], 25.0),
            assembly_position_tolerance=number(row["assembly_position_tolerance"], 50.0),
            assembly_angle_tolerance=number(row["assembly_angle_tolerance"], 30.0),
            guidance_level=row["guidance_level"],
            progression=row["progression"],
            risk_level=row["risk_level"],
            recovery_trend=row["recovery_trend"],
            override_recommendation=row["override_recommendation"],
            ai_confidence_score=number(row["ai_confidence_score"], 75.0),
            override_probability=number(row["override_probability"], 0.25),
            recommendation_reliability=number(row["recommendation_reliability"], 75.0),
            rationale=row["rationale"],
        )

    def recommend(
        self,
        patient_id: str,
        level: int,
        accuracy: float,
        rom: float,
        pain_level: int,
        duration: float,
        score: int,
        movement_quality: float = 0.7,
        fatigue_index: float = 0.0,
        rotation_smoothness: float = 0.7,
        recovery_prediction: float | None = None,
        functional_recovery_score: float | None = None,
        session_id: int | None = None,
    ) -> AdaptivePrescription:
        history = self._sessions(patient_id, limit=12)
        rom_trend = self._trend([number(row["avg_hand_angle"]) for row in history])
        acc_trend = self._trend([number(row["avg_accuracy"]) for row in history])
        consistency = self._consistency(history)
        recovery_trend = self._recovery_trend(rom_trend, acc_trend, history)
        pain_trend = self._trend([number(row["pain_level"]) for row in history])

        readiness_score = self.readiness_score(
            accuracy=accuracy,
            rom=rom,
            pain_level=pain_level,
            consistency=consistency,
            smoothness=rotation_smoothness,
            fatigue_index=fatigue_index,
            movement_quality=movement_quality,
        )
        adaptive_score = readiness_score / 100.0

        safety_blocks = []
        if pain_level >= 7:
            safety_blocks.append("pain is high")
        if rom_trend <= -8 and len(history) >= 2:
            safety_blocks.append("ROM decreased significantly")
        if accuracy < 50:
            safety_blocks.append("accuracy is below the safe progression threshold")
        if fatigue_index >= 0.75:
            safety_blocks.append("fatigue indicator is high")

        progression = "maintain"
        if safety_blocks or rom < 30:
            progression = "regress"
        elif readiness_score >= 72 and rom_trend >= -2 and acc_trend >= -5 and pain_trend <= 1:
            progression = "advance"
        elif readiness_score < 42:
            progression = "support"

        tier = 3
        if progression == "advance":
            tier = 4 if adaptive_score < 0.86 else 5
        elif progression in ("support", "regress"):
            tier = 2 if pain_level < 7 else 1

        risk = "low"
        if pain_level >= 7 or fatigue_index >= 0.75 or (rom_trend <= -10 and len(history) >= 2):
            risk = "high"
        elif pain_level >= 5 or rom_trend < -8 or accuracy < 55:
            risk = "moderate"

        target_scale = {1: 1.45, 2: 1.25, 3: 1.0, 4: 0.86, 5: 0.72}[tier]
        speed_scale = {1: 0.60, 2: 0.78, 3: 1.0, 4: 1.15, 5: 1.30}[tier]
        required_rom = clamp(max(25.0, rom * {1: 0.55, 2: 0.70, 3: 0.82, 4: 0.92, 5: 1.0}[tier]), 20.0, 95.0)
        time_limit = {1: 70.0, 2: 55.0, 3: 45.0, 4: 38.0, 5: 32.0}[tier]
        repetitions = {1: 3, 2: 4, 3: 5, 4: 7, 5: 9}[tier]
        hold_seconds = {1: 0.8, 2: 1.1, 3: 1.5, 4: 1.8, 5: 2.1}[tier]
        rotation_tolerance = {1: 40.0, 2: 32.0, 3: 25.0, 4: 20.0, 5: 16.0}[tier]
        assembly_pos_tol = {1: 85.0, 2: 68.0, 3: 50.0, 4: 40.0, 5: 32.0}[tier]
        assembly_ang_tol = {1: 48.0, 2: 38.0, 3: 30.0, 4: 24.0, 5: 18.0}[tier]
        guidance = "high" if tier <= 2 or risk != "low" else "standard" if tier == 3 else "minimal"
        override = self._override_recommendation(
            risk_level=risk,
            progression=progression,
            readiness_score=readiness_score,
            safety_blocks=safety_blocks,
            recovery_trend=recovery_trend,
        )
        learning = self._override_learning_scores(patient_id, level, risk, progression)
        explanation = {
            "decision": progression,
            "readiness_score": readiness_score,
            "safety_blocks": safety_blocks,
            "rom_trend": rom_trend,
            "accuracy_trend": acc_trend,
            "pain_trend": pain_trend,
            "recovery_trend": recovery_trend,
            "why": "",
        }

        rationale_parts = []
        if progression == "advance":
            rationale_parts.append("High control with stable or improving trend.")
            explanation["why"] = (
                f"Difficulty increased because readiness was {readiness_score:.0f}/100, "
                f"ROM trend was {rom_trend:+.1f} deg, accuracy trend was {acc_trend:+.1f}%, "
                f"and pain trend was {pain_trend:+.1f}."
            )
        elif progression == "regress":
            rationale_parts.append(
                "Difficulty reduced because "
                + (", ".join(safety_blocks) if safety_blocks else "ROM is below the minimum therapeutic threshold")
                + "."
            )
            explanation["why"] = (
                "Difficulty decreased because "
                + (", ".join(safety_blocks) if safety_blocks else "ROM was below the minimum therapeutic threshold")
                + f"; readiness was {readiness_score:.0f}/100."
            )
        elif progression == "support":
            rationale_parts.append("Extra support selected because performance is below target.")
            explanation["why"] = (
                f"Difficulty support was selected because readiness was {readiness_score:.0f}/100, "
                f"with accuracy {accuracy:.1f}% and pain {pain_level}/10."
            )
        else:
            rationale_parts.append("Maintain load while trend stabilizes.")
            explanation["why"] = (
                f"Difficulty maintained because readiness was {readiness_score:.0f}/100 and trends were not strong enough for safe progression."
            )
        rationale_parts.append(
            f"Readiness score {readiness_score:.0f}/100 from accuracy {accuracy:.1f}%, "
            f"ROM {rom:.1f} deg, pain {pain_level}/10, consistency {consistency * 100:.0f}%, "
            f"smoothness {rotation_smoothness * 100:.0f}%, fatigue {fatigue_index * 100:.0f}%."
        )
        if len(history) >= 2:
            rationale_parts.append(
                f"Recent ROM trend {rom_trend:+.1f} deg, accuracy trend {acc_trend:+.1f}%, "
                f"pain trend {pain_trend:+.1f}; recovery trend is {recovery_trend}."
            )

        prescription = AdaptivePrescription(
            patient_id=patient_id,
            level=level,
            difficulty_tier=tier,
            readiness_score=readiness_score,
            target_scale=target_scale,
            speed_scale=speed_scale,
            required_rom=required_rom,
            time_limit=time_limit,
            repetitions=repetitions,
            hold_seconds=hold_seconds,
            rotation_tolerance=rotation_tolerance,
            assembly_position_tolerance=assembly_pos_tol,
            assembly_angle_tolerance=assembly_ang_tol,
            guidance_level=guidance,
            progression=progression,
            risk_level=risk,
            recovery_trend=recovery_trend,
            override_recommendation=override,
            ai_confidence_score=learning["ai_confidence_score"],
            override_probability=learning["override_probability"],
            recommendation_reliability=learning["recommendation_reliability"],
            rationale=" ".join(rationale_parts),
        )
        self.save_prescription(prescription, session_id=session_id, metrics={
            "accuracy": accuracy,
            "rom": rom,
            "pain_level": pain_level,
            "duration": duration,
            "score": score,
            "movement_quality": movement_quality,
            "fatigue_index": fatigue_index,
            "rotation_smoothness": rotation_smoothness,
            "consistency": consistency,
            "readiness_score": readiness_score,
            "adaptive_score": adaptive_score,
            "rom_trend": rom_trend,
            "accuracy_trend": acc_trend,
            "pain_trend": pain_trend,
            "recovery_trend": recovery_trend,
            "recovery_prediction": recovery_prediction,
            "functional_recovery_score": functional_recovery_score,
            "safety_blocks": safety_blocks,
        }, explanation=explanation)
        return prescription

    def readiness_score(
        self,
        accuracy: float,
        rom: float,
        pain_level: int,
        consistency: float,
        smoothness: float,
        fatigue_index: float,
        movement_quality: float = 0.7,
    ) -> float:
        """Return a 0-100 rehabilitation readiness score."""
        score = (
            30.0 * clamp(accuracy / 100.0, 0.0, 1.0)
            + 22.0 * clamp(rom / 90.0, 0.0, 1.0)
            + 16.0 * clamp((10.0 - pain_level) / 10.0, 0.0, 1.0)
            + 12.0 * clamp(consistency, 0.0, 1.0)
            + 10.0 * clamp(smoothness, 0.0, 1.0)
            + 6.0 * clamp(1.0 - fatigue_index, 0.0, 1.0)
            + 4.0 * clamp(movement_quality, 0.0, 1.0)
        )
        return round(clamp(score, 0.0, 100.0), 1)

    def save_prescription(
        self,
        prescription: AdaptivePrescription,
        session_id: int | None = None,
        metrics: dict[str, Any] | None = None,
        explanation: dict[str, Any] | None = None,
    ) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO adaptive_prescriptions (
                    patient_id, session_id, level, difficulty_tier, readiness_score, target_scale,
                    speed_scale, required_rom, time_limit, repetitions, hold_seconds,
                    rotation_tolerance, assembly_position_tolerance,
                    assembly_angle_tolerance, guidance_level, progression, risk_level,
                    recovery_trend, override_recommendation, ai_confidence_score,
                    override_probability, recommendation_reliability, explanation_json,
                    rationale, metrics_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prescription.patient_id,
                    session_id,
                    prescription.level,
                    prescription.difficulty_tier,
                    prescription.readiness_score,
                    prescription.target_scale,
                    prescription.speed_scale,
                    prescription.required_rom,
                    prescription.time_limit,
                    prescription.repetitions,
                    prescription.hold_seconds,
                    prescription.rotation_tolerance,
                    prescription.assembly_position_tolerance,
                    prescription.assembly_angle_tolerance,
                    prescription.guidance_level,
                    prescription.progression,
                    prescription.risk_level,
                    prescription.recovery_trend,
                    prescription.override_recommendation,
                    prescription.ai_confidence_score,
                    prescription.override_probability,
                    prescription.recommendation_reliability,
                    json.dumps(explanation or {}, sort_keys=True),
                    prescription.rationale,
                    json.dumps(metrics or {}, sort_keys=True),
                ),
            )
            conn.commit()

    def coaching_message(
        self,
        patient_id: str,
        level: int,
        prescription: AdaptivePrescription,
        accuracy: float,
        rom: float,
        pain_level: int,
        fatigue_index: float = 0.0,
        recovery_prediction: float | None = None,
        session_id: int | None = None,
    ) -> str:
        previous = self._sessions(patient_id, limit=2)
        delta_rom = 0.0
        delta_acc = 0.0
        if len(previous) >= 2:
            delta_rom = rom - number(previous[-2]["avg_hand_angle"])
            delta_acc = accuracy - number(previous[-2]["avg_accuracy"])

        # Fetch Context for RAG
        clinical = None
        therapist_notes = ""
        latest_forearm = None
        
        try:
            from clinical_intelligence import ClinicalIntelligenceLayer
            clinical = ClinicalIntelligenceLayer(self.db_path).get_clinical_profile(patient_id)
        except Exception:
            clinical = None

        with self.connect() as conn:
            try:
                profile_row = conn.execute(
                    "SELECT therapist_notes FROM dashboard_patient_profiles WHERE name = ?",
                    (patient_id,),
                ).fetchone()
                if profile_row and profile_row["therapist_notes"]:
                    therapist_notes = profile_row["therapist_notes"]
            except sqlite3.OperationalError:
                pass

            try:
                forearm_row = conn.execute(
                    """
                    SELECT movement_class, compensation_score
                    FROM forearm_assessments
                    WHERE patient_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (patient_id,),
                ).fetchone()
                if forearm_row:
                    latest_forearm = f"{forearm_row['movement_class']} (Compensation Score: {forearm_row['compensation_score']*100:.0f}%)"
            except sqlite3.OperationalError:
                pass

        metrics = {
            "Patient ID": patient_id,
            "Exercise Level": level,
            "Accuracy": f"{accuracy:.1f}%",
            "ROM": f"{rom:.1f} degrees",
            "Pain Score (0-10)": pain_level,
            "Fatigue Index (0-1)": f"{fatigue_index:.2f}",
            "Recovery Prediction": f"{recovery_prediction:.1f}%" if recovery_prediction else "Unknown",
            "Readiness Score": f"{prescription.readiness_score:.0f}/100",
            "Risk Level": prescription.risk_level,
            "Recovery State": prescription.recovery_trend,
            "Difficulty Tier": prescription.difficulty_tier,
            "Adaptive Prescription": {
                "target_scale": prescription.target_scale,
                "speed_scale": prescription.speed_scale,
                "required_rom": prescription.required_rom,
                "repetitions": prescription.repetitions,
                "hold_seconds": prescription.hold_seconds,
                "rotation_tolerance": prescription.rotation_tolerance,
            },
            "AI Prescription Rationale": f"Progression: {prescription.progression}. {prescription.rationale}"
        }
        
        if len(previous) >= 2:
            metrics["Previous ROM"] = f"{number(previous[-2]['avg_hand_angle']):.1f} degrees"
            metrics["Previous Accuracy"] = f"{number(previous[-2]['avg_accuracy']):.1f}%"
            
        if clinical:
            metrics["Recovery Trend"] = f"{clinical['trend']} ({clinical['recovery_stage']})"
            if clinical["detected_risks"]:
                metrics["Active Risks"] = ", ".join(clinical["detected_risks"])
            else:
                metrics["Active Risks"] = "None detected"
                
        if therapist_notes:
            metrics["Therapist Notes"] = therapist_notes
            
        if latest_forearm:
            metrics["Latest Forearm Assessment"] = latest_forearm

        coaching_trigger = "stable_recovery"
        if pain_level >= 7:
            core_message = "Take the movement slowly. Do not force the rotation. Focus on comfort and control."
            coaching_trigger = "elevated_pain"
        elif fatigue_index >= 0.75:
            core_message = "Movement speed is decreasing. Consider taking a short rest. Let's prioritize quality over speed."
            coaching_trigger = "fatigue"
        elif prescription.progression == "advance" and accuracy >= 80:
            coaching_trigger = "safe_progression"
            if delta_rom > 0:
                core_message = f"Excellent progress. Your wrist rotation improved by {delta_rom:+.1f} degrees compared to your previous session. You are ready for a greater challenge."
            else:
                core_message = f"Excellent work. Your accuracy increased by {delta_acc:+.1f}% this week. Keep maintaining smooth movements."
        elif prescription.progression in ("support", "regress"):
            core_message = "Recovery is progressing slower than expected. Let's focus on movement quality before increasing difficulty."
            coaching_trigger = "support_or_regress"
        else:
            if recovery_prediction is not None:
                if rom > recovery_prediction:
                    core_message = "You are recovering faster than the projected trend."
                    coaching_trigger = "above_recovery_prediction"
                else:
                    core_message = "Recovery remains stable and on target."
            else:
                core_message = "Good controlled work. We will hold this difficulty until the trend is stronger."

        readiness = prescription.readiness_score
        if readiness > 80:
            deterministic_message = f"Readiness is high ({readiness:.0f}/100). {core_message}"
        elif readiness >= 50:
            deterministic_message = f"Readiness is moderate ({readiness:.0f}/100). {core_message}"
        else:
            deterministic_message = f"Readiness is low ({readiness:.0f}/100). {core_message}"

        enhanced_message = enhance_coaching_message(deterministic_message, metrics)
        message = enhanced_message or deterministic_message
        llm_status = "enhanced" if enhanced_message else "deterministic_fallback"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sensei_messages (
                    patient_id, session_id, level, message, deterministic_message,
                    llm_enhanced_message, coaching_trigger, decision_source,
                    llm_status, context_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    session_id,
                    level,
                    message,
                    deterministic_message,
                    enhanced_message or "",
                    coaching_trigger,
                    "Adaptive AI Engine + Rule-Based Logic",
                    llm_status,
                    json.dumps(
                        {
                            "prescription": asdict(prescription),
                            "metrics": metrics,
                            "decision_source": "Adaptive AI Rehabilitation Engine",
                            "communication_layer": "Optional Local LLM Enhancement" if enhanced_message else "Deterministic Coaching",
                        },
                        sort_keys=True,
                    ),
                ),
            )
            conn.commit()
        return message

    def prescription_history(self, patient_id: str, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM adaptive_prescriptions
                WHERE patient_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()
        return rows

    def research_metrics(self, patient_id: str) -> dict[str, float]:
        sessions = self._sessions(patient_id, limit=60)
        prescriptions = self.prescription_history(patient_id, limit=60)
        if not sessions:
            return {
                "weekly_rom_improvement": 0.0,
                "accuracy_improvement": 0.0,
                "pain_adjusted_performance": 0.0,
                "session_adherence": 0.0,
                "difficulty_progression": 0.0,
                "forearm_progress": 0.0,
                "compensation_frequency": 0.0,
                "shoulder_compensation": 0.0,
                "elbow_compensation": 0.0,
                "trunk_compensation": 0.0,
                "movement_efficiency": 0.0,
            }

        rom_values = [number(row["avg_hand_angle"]) for row in sessions]
        acc_values = [number(row["avg_accuracy"]) for row in sessions]
        pain_values = [number(row["pain_level"]) for row in sessions]
        weekly_rom = self._weekly_rom_improvement(sessions)
        pain_adjusted = sum(
            acc * clamp((10.0 - pain) / 10.0, 0.0, 1.0)
            for acc, pain in zip(acc_values, pain_values)
        ) / len(sessions)
        difficulty = 0.0
        if len(prescriptions) >= 2:
            ordered = list(reversed(prescriptions))
            difficulty = number(ordered[-1]["difficulty_tier"]) - number(ordered[0]["difficulty_tier"])
        forearm = self._forearm_progress(patient_id)
        upper_limb = self._upper_limb_metrics(patient_id)

        return {
            "weekly_rom_improvement": round(weekly_rom, 2),
            "accuracy_improvement": round(self._trend(acc_values), 2),
            "pain_adjusted_performance": round(pain_adjusted, 2),
            "session_adherence": round(self._consistency(sessions) * 100.0, 1),
            "difficulty_progression": round(difficulty, 2),
            "forearm_progress": round(forearm, 2),
            **upper_limb,
        }

    def _sessions(self, patient_id: str, limit: int = 12) -> list[sqlite3.Row]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM sessions
                WHERE patient_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (patient_id, limit),
            ).fetchall()
        return list(reversed(rows))

    def _trend(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        recent = values[-4:] if len(values) >= 4 else values
        return recent[-1] - recent[0]

    def _recovery_trend(self, rom_trend: float, acc_trend: float, history: list[sqlite3.Row]) -> str:
        if len(history) < 2:
            return "baseline"
        if rom_trend >= 8 and acc_trend >= -3:
            return "improving"
        if rom_trend <= -8 or acc_trend <= -15:
            return "declining"
        return "stable"

    def _override_recommendation(
        self,
        risk_level: str,
        progression: str,
        readiness_score: float,
        safety_blocks: list[str],
        recovery_trend: str,
    ) -> str:
        if risk_level == "high":
            return "Therapist review recommended before increasing load."
        if safety_blocks:
            return "Keep reduced difficulty until safety triggers resolve."
        if recovery_trend == "declining":
            return "Consider reassessment of pain, fatigue, and compensation."
        if progression == "advance" and readiness_score >= 85:
            return "Advance may proceed unless therapist observes compensatory movement."
        if readiness_score < 45:
            return "Use assisted mode and review exercise selection."
        return "No therapist override suggested."

    def _override_learning_scores(self, patient_id: str, level: int, risk_level: str, progression: str) -> dict[str, float]:
        try:
            with self.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT decision, reason, patient_context_json
                    FROM therapist_overrides
                    WHERE patient_id = ?
                    ORDER BY id DESC
                    LIMIT 40
                    """,
                    (patient_id,),
                ).fetchall()
                level_rows = conn.execute(
                    """
                    SELECT decision
                    FROM therapist_overrides
                    WHERE patient_id = ? AND json_extract(ai_recommendation_json, '$.level') = ?
                    ORDER BY id DESC
                    LIMIT 20
                    """,
                    (patient_id, level),
                ).fetchall()
        except sqlite3.OperationalError:
            rows = []
            level_rows = []

        if not rows:
            base = 78.0
            if risk_level != "low":
                base -= 8.0
            return {
                "ai_confidence_score": round(clamp(base, 0.0, 100.0), 1),
                "override_probability": round(1.0 - clamp(base / 100.0, 0.0, 1.0), 3),
                "recommendation_reliability": round(clamp(base, 0.0, 100.0), 1),
            }

        non_accept = sum(1 for row in rows if str(row["decision"]).lower() != "accept")
        reject = sum(1 for row in rows if str(row["decision"]).lower() == "reject")
        level_non_accept = sum(1 for row in level_rows if str(row["decision"]).lower() != "accept")
        override_rate = non_accept / len(rows)
        reject_rate = reject / len(rows)
        level_penalty = (level_non_accept / len(level_rows)) if level_rows else 0.0
        risk_penalty = 0.10 if risk_level == "moderate" else 0.18 if risk_level == "high" else 0.0
        progression_penalty = 0.08 if progression == "advance" and override_rate > 0.35 else 0.0
        override_probability = clamp(0.12 + 0.48 * override_rate + 0.22 * reject_rate + 0.12 * level_penalty + risk_penalty + progression_penalty, 0.0, 0.95)
        confidence = clamp(100.0 * (1.0 - override_probability), 5.0, 98.0)
        reliability = clamp(100.0 - (override_rate * 55.0) - (reject_rate * 25.0) - (level_penalty * 15.0), 0.0, 100.0)
        return {
            "ai_confidence_score": round(confidence, 1),
            "override_probability": round(override_probability, 3),
            "recommendation_reliability": round(reliability, 1),
        }

    def _weekly_rom_improvement(self, sessions: list[sqlite3.Row]) -> float:
        if len(sessions) < 2:
            return 0.0
        try:
            start = datetime.fromisoformat(str(sessions[0]["timestamp"]))
            end = datetime.fromisoformat(str(sessions[-1]["timestamp"]))
            days = max((end - start).total_seconds() / 86400.0, 1.0)
        except ValueError:
            days = max(len(sessions) - 1, 1)
        rom_delta = number(sessions[-1]["avg_hand_angle"]) - number(sessions[0]["avg_hand_angle"])
        return rom_delta / days * 7.0

    def _forearm_progress(self, patient_id: str) -> float:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT smoothness, compensation_score
                FROM forearm_assessments
                WHERE patient_id = ?
                ORDER BY id ASC
                LIMIT 60
                """,
                (patient_id,),
            ).fetchall()
        if len(rows) < 2:
            return 0.0
        first = number(rows[0]["smoothness"]) - number(rows[0]["compensation_score"])
        last = number(rows[-1]["smoothness"]) - number(rows[-1]["compensation_score"])
        return (last - first) * 100.0

    def _upper_limb_metrics(self, patient_id: str) -> dict[str, float]:
        try:
            with self.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT shoulder_compensation, elbow_compensation, trunk_compensation,
                           compensation_score, movement_efficiency
                    FROM upper_limb_assessments
                    WHERE patient_id = ?
                    ORDER BY id DESC
                    LIMIT 60
                    """,
                    (patient_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        if not rows:
            return {
                "compensation_frequency": 0.0,
                "shoulder_compensation": 0.0,
                "elbow_compensation": 0.0,
                "trunk_compensation": 0.0,
                "movement_efficiency": 0.0,
            }
        return {
            "compensation_frequency": round(sum(1 for row in rows if number(row["compensation_score"]) >= 0.45) / len(rows) * 100.0, 1),
            "shoulder_compensation": round(sum(number(row["shoulder_compensation"]) for row in rows) / len(rows) * 100.0, 1),
            "elbow_compensation": round(sum(number(row["elbow_compensation"]) for row in rows) / len(rows) * 100.0, 1),
            "trunk_compensation": round(sum(number(row["trunk_compensation"]) for row in rows) / len(rows) * 100.0, 1),
            "movement_efficiency": round(sum(number(row["movement_efficiency"]) for row in rows) / len(rows), 1),
        }

    def _consistency(self, sessions: Iterable[sqlite3.Row]) -> float:
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
        return clamp(1.0 - (avg_gap / 10.0), 0.0, 1.0)


class ForearmExerciseClassifier:
    """Classifies forearm rotation patterns from wrist rotation angle history."""

    def __init__(self, neutral_angle: float = 0.0):
        self.neutral_angle = neutral_angle

    def classify(
        self,
        rotation_angle: float,
        history: Iterable[float],
        wrist_deviation_angle: float = 0.0,
        hold_seconds: float = 0.0,
        upper_limb_metrics: dict[str, Any] | None = None,
    ) -> dict[str, float | str]:
        angles = list(history)[-45:]
        normalized = rotation_angle - self.neutral_angle
        abs_angle = abs(normalized)
        velocity = 0.0
        smoothness = 1.0
        if len(angles) >= 3:
            diffs = [angles[i] - angles[i - 1] for i in range(1, len(angles))]
            velocity = sum(abs(v) for v in diffs) / len(diffs)
            mean_v = sum(diffs) / len(diffs)
            variance = sum((v - mean_v) ** 2 for v in diffs) / len(diffs)
            smoothness = clamp(1.0 - math.sqrt(variance) / 25.0, 0.0, 1.0)

        wrist_compensation = clamp(abs(wrist_deviation_angle) / 70.0, 0.0, 1.0)
        upper_limb_compensation = number((upper_limb_metrics or {}).get("compensation_score"), 0.0)
        compensation = clamp(max(wrist_compensation, upper_limb_compensation), 0.0, 1.0)

        if compensation > 0.65:
            movement = "Compensatory Movement Detection"
        elif hold_seconds >= 3.0 and abs_angle >= 25:
            movement = "Rotation Hold"
        elif hold_seconds >= 8.0:
            movement = "Rotation Endurance"
        elif smoothness >= 0.78 and velocity >= 0.8 and abs_angle >= 20:
            movement = "Smooth Rotation"
        elif abs_angle < 12:
            movement = "Neutral Position"
        elif normalized >= 55:
            movement = "Supination"
        elif normalized <= -55:
            movement = "Pronation"
        elif normalized > 0:
            movement = "Partial Supination"
        else:
            movement = "Partial Pronation"

        return {
            "movement_class": movement,
            "rotation_angle": normalized,
            "smoothness": smoothness,
            "compensation_score": compensation,
            "upper_limb_compensation": upper_limb_compensation,
            "movement_efficiency": number((upper_limb_metrics or {}).get("movement_efficiency"), 100.0),
            "endurance_seconds": hold_seconds,
        }

    def save_assessment(
        self,
        db_path: str,
        patient_id: str,
        level: int,
        assessment: dict[str, float | str],
        session_id: int | None = None,
    ) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO forearm_assessments (
                    patient_id, session_id, level, movement_class, rotation_angle,
                    smoothness, compensation_score, endurance_seconds
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    session_id,
                    level,
                    str(assessment["movement_class"]),
                    number(assessment["rotation_angle"]),
                    number(assessment["smoothness"]),
                    number(assessment["compensation_score"]),
                    number(assessment["endurance_seconds"]),
                ),
            )
            conn.commit()
