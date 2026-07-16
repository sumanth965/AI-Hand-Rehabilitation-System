"""
Therapist Dashboard for the AI Hand Rehabilitation System.

This module is intentionally separate from the real-time MediaPipe/Pygame
rehabilitation runtime. It reads the existing SQLite database, adds optional
dashboard-only metadata tables, and serves a professional browser dashboard.
"""

from __future__ import annotations

import base64
import html
import io
import json
import math
import os
import sqlite3
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, unquote, urlparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from digital_twin_rehab import DigitalTwinRehabModel
from clinical_intelligence import ClinicalIntelligenceLayer


DB_PATH = "rehab_data.db"
REPORT_DIR = "reports"
HOST = "127.0.0.1"
PORT = 8080


LEVEL_NAMES = {
    1: "Flexibility - Bubble Reach",
    2: "Strength - Palm Catch",
    3: "Fine Motor - Pinch Transfer",
    4: "Coordination - Path Tracing",
    5: "Grip Release - Open/Close Cycle",
    6: "Cognitive Motor - Sequence Tap",
    7: "Forearm Rotation - Rotation Orbit",
    8: "Functional Motor - Smart Assembly",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def row_value(row: sqlite3.Row, key: str, default: Any = "") -> Any:
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def short_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "")).strftime("%d %b %Y")
    except ValueError:
        return value[:16]


def minutes(seconds: Any) -> float:
    return number(seconds) / 60.0


def format_duration(seconds: Any) -> str:
    total = int(number(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def exercise_for_level(level: Any) -> str:
    return LEVEL_NAMES.get(int(number(level)), "Therapeutic Exercise")


def trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return values[-1] - values[0]


def recovery_prediction(sessions: list[sqlite3.Row]) -> float:
    values = [number(row["avg_hand_angle"]) for row in sessions if row["avg_hand_angle"] is not None]
    if len(values) < 3:
        return -1.0
    xs = list(range(len(values)))
    x_mean = sum(xs) / len(xs)
    y_mean = sum(values) / len(values)
    denom = sum((x - x_mean) ** 2 for x in xs) or 1.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denom
    predicted = y_mean + slope * (len(values) + 3)
    current = max(y_mean, 1.0)
    return max(0.0, min(100.0, (predicted / current) * 100.0))


def tremor_rating_for_sessions(sessions: list[sqlite3.Row]) -> str:
    if len(sessions) < 3:
        return "Not recorded"
    rom_values = [number(row["avg_hand_angle"]) for row in sessions[-6:]]
    mean = sum(rom_values) / len(rom_values)
    variance = sum((value - mean) ** 2 for value in rom_values) / len(rom_values)
    stdev = math.sqrt(variance)
    if stdev < 5:
        return "Low"
    if stdev < 12:
        return "Moderate"
    return "High"


def fatigue_score(row: sqlite3.Row) -> float:
    """Derive a 0-10 fatigue indicator from stored session metrics."""
    pain = number(row["pain_level"])
    accuracy_load = max(0.0, (70.0 - number(row["avg_accuracy"])) / 70.0) * 4.0
    duration_load = min(3.0, minutes(row["duration"]) / 8.0 * 3.0)
    pain_load = pain * 0.35
    return max(0.0, min(10.0, accuracy_load + duration_load + pain_load))


def recovery_status_from_metrics(avg_accuracy: float, avg_rom: float, risk_level: str, sessions_count: int) -> str:
    if sessions_count == 0:
        return "Not started"
    if str(risk_level).lower() == "high":
        return "At risk"
    if avg_accuracy >= 75 and avg_rom >= 75:
        return "Progressing well"
    if avg_accuracy >= 55 and avg_rom >= 45:
        return "Active recovery"
    return "Needs review"


def recovery_category(score: float) -> str:
    if score <= 25:
        return "Poor"
    if score <= 50:
        return "Fair"
    if score <= 75:
        return "Good"
    return "Excellent"


def calculated_functional_recovery_score(row: sqlite3.Row, consistency: float = 1.0) -> float:
    try:
        stored = number(row["functional_recovery_score"], -1)
        if stored > 0:
            return round(stored, 1)
    except (IndexError, KeyError):
        pass
    pain_after = row_value(row, "pain_after_session", row_value(row, "pain_level", 0))
    smoothness = row_value(row, "movement_smoothness", 0.7)
    score = (
        0.30 * max(0.0, min(1.0, number(row["avg_hand_angle"]) / 90.0))
        + 0.25 * max(0.0, min(1.0, number(row["avg_accuracy"]) / 100.0))
        + 0.20 * max(0.0, min(1.0, (10.0 - number(pain_after)) / 10.0))
        + 0.15 * max(0.0, min(1.0, consistency))
        + 0.10 * max(0.0, min(1.0, number(smoothness, 0.7)))
    ) * 100.0
    return round(max(0.0, min(100.0, score)), 1)


@dataclass
class Page:
    title: str
    body: str
    active: str = "home"
    scripts: str = ""


class DashboardRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.digital_twin = DigitalTwinRehabModel(db_path)
        self.clinical_intel = ClinicalIntelligenceLayer(db_path)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_patient_profiles (
                    patient_name TEXT PRIMARY KEY,
                    gender TEXT DEFAULT '',
                    injury_type TEXT DEFAULT '',
                    rehab_stage TEXT DEFAULT '',
                    assigned_exercises TEXT DEFAULT '',
                    therapist_notes TEXT DEFAULT '',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT NOT NULL,
                    session_id INTEGER,
                    note_type TEXT DEFAULT 'Observation',
                    note TEXT NOT NULL,
                    recommendation TEXT DEFAULT '',
                    next_plan TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS therapist_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER,
                    therapist_name TEXT DEFAULT 'Therapist',
                    note_text TEXT NOT NULL,
                    recommendation TEXT DEFAULT '',
                    clinical_observation TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    modified_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exercise_compliance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    assigned_sessions INTEGER DEFAULT 0,
                    completed_sessions INTEGER DEFAULT 0,
                    missed_sessions INTEGER DEFAULT 0,
                    compliance_percentage REAL DEFAULT 0,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compensation_analysis_placeholders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER,
                    shoulder_lifting REAL DEFAULT 0,
                    elbow_drift REAL DEFAULT 0,
                    trunk_leaning REAL DEFAULT 0,
                    compensatory_movement_score REAL DEFAULT 0,
                    status TEXT DEFAULT 'Coming Soon',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for column, definition in [
                ("pain_before_session", "INTEGER DEFAULT 0"),
                ("pain_after_session", "INTEGER DEFAULT 0"),
                ("pain_difference", "INTEGER DEFAULT 0"),
                ("functional_recovery_score", "REAL DEFAULT 0"),
                ("recovery_category", "TEXT DEFAULT 'Not recorded'"),
                ("movement_smoothness", "REAL DEFAULT 0"),
            ]:
                try:
                    conn.execute(f"SELECT {column} FROM sessions LIMIT 1")
                except sqlite3.OperationalError:
                    try:
                        conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} {definition}")
                    except sqlite3.OperationalError:
                        pass
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
            # Ensure patients table exists and has id_number in case dashboard is run before the game
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    name TEXT PRIMARY KEY,
                    age INTEGER,
                    age_group TEXT,
                    cal_fist_val REAL DEFAULT 0.12,
                    cal_max_ext REAL DEFAULT 170.0,
                    cal_min_ang REAL DEFAULT 15.0,
                    cal_max_ang REAL DEFAULT 90.0,
                    cal_active INTEGER DEFAULT 0,
                    id_number TEXT UNIQUE
                )
            """)
            try:
                conn.execute(f"SELECT id_number FROM patients LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    conn.execute(f"ALTER TABLE patients ADD COLUMN id_number TEXT")
                    conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_id_number ON patients(id_number)")
                except Exception:
                    pass
            conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, tuple(params))
            conn.commit()

    def scalar(self, sql: str, params: Iterable[Any] = (), default: Any = 0) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return default
        value = rows[0][0]
        return default if value is None else value

    def patients(self) -> list[sqlite3.Row]:
        rows = self.query(
            """
            SELECT
                p.name,
                p.age,
                p.age_group,
                COALESCE(p.id_number, '') AS id_number,
                COALESCE(d.gender, '') AS gender,
                COALESCE(d.injury_type, '') AS injury_type,
                COALESCE(d.rehab_stage, '') AS rehab_stage,
                COALESCE(d.assigned_exercises, '') AS assigned_exercises,
                COALESCE(d.therapist_notes, '') AS therapist_notes,
                COALESCE(MIN(s.timestamp), d.updated_at, '') AS registration_date,
                COUNT(s.id) AS sessions_count,
                COALESCE(AVG(s.avg_accuracy), 0) AS avg_accuracy,
                COALESCE(AVG(s.avg_hand_angle), 0) AS avg_rom,
                COALESCE(MAX(s.avg_hand_angle), 0) AS max_rom,
                COALESCE(AVG(s.pain_level), 0) AS avg_pain,
                MAX(s.timestamp) AS last_session
            FROM patients p
            LEFT JOIN dashboard_patient_profiles d ON d.patient_name = p.name
            LEFT JOIN sessions s ON s.patient_id = p.name
            GROUP BY p.name
            UNION
            SELECT
                s.patient_id AS name,
                NULL AS age,
                '' AS age_group,
                '' AS id_number,
                COALESCE(d.gender, '') AS gender,
                COALESCE(d.injury_type, '') AS injury_type,
                COALESCE(d.rehab_stage, '') AS rehab_stage,
                COALESCE(d.assigned_exercises, '') AS assigned_exercises,
                COALESCE(d.therapist_notes, '') AS therapist_notes,
                COALESCE(MIN(s.timestamp), d.updated_at, '') AS registration_date,
                COUNT(s.id) AS sessions_count,
                COALESCE(AVG(s.avg_accuracy), 0) AS avg_accuracy,
                COALESCE(AVG(s.avg_hand_angle), 0) AS avg_rom,
                COALESCE(MAX(s.avg_hand_angle), 0) AS max_rom,
                COALESCE(AVG(s.pain_level), 0) AS avg_pain,
                MAX(s.timestamp) AS last_session
            FROM sessions s
            LEFT JOIN patients p ON p.name = s.patient_id
            LEFT JOIN dashboard_patient_profiles d ON d.patient_name = s.patient_id
            WHERE p.name IS NULL
            GROUP BY s.patient_id
            """
        )
        return sorted(rows, key=lambda row: str(row["name"] or "").lower())

    def patient(self, name: str) -> sqlite3.Row | None:
        rows = [row for row in self.patients() if row["name"] == name]
        return rows[0] if rows else None

    def save_patient(self, form: dict[str, str]) -> None:
        name = form.get("name", "").strip()
        if not name:
            return
        age = form.get("age", "").strip()
        age_value = int(age) if age.isdigit() else None
        age_group = form.get("age_group", "").strip()
        id_number = form.get("id_number", "").strip() or None
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO patients (name, age, age_group, id_number)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET age = excluded.age, age_group = excluded.age_group, id_number = excluded.id_number
                """,
                (name, age_value, age_group, id_number),
            )
            conn.execute(
                """
                INSERT INTO dashboard_patient_profiles
                    (patient_name, gender, injury_type, rehab_stage, assigned_exercises,
                     therapist_notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(patient_name) DO UPDATE SET
                    gender = excluded.gender,
                    injury_type = excluded.injury_type,
                    rehab_stage = excluded.rehab_stage,
                    assigned_exercises = excluded.assigned_exercises,
                    therapist_notes = excluded.therapist_notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    name,
                    form.get("gender", "").strip(),
                    form.get("injury_type", "").strip(),
                    form.get("rehab_stage", "").strip(),
                    form.get("assigned_exercises", "").strip(),
                    form.get("therapist_notes", "").strip(),
                ),
            )
            conn.commit()

    def delete_patient(self, name: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM patients WHERE name = ?", (name,))
            conn.execute("DELETE FROM dashboard_patient_profiles WHERE patient_name = ?", (name,))
            conn.execute("DELETE FROM dashboard_notes WHERE patient_name = ?", (name,))
            conn.commit()

    def sessions(self, patient: str = "", limit: int | None = None) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        sql = f"SELECT * FROM sessions {where} ORDER BY datetime(timestamp) DESC, id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return self.query(sql, params)

    def sessions_chrono(self, patient: str = "") -> list[sqlite3.Row]:
        rows = self.sessions(patient)
        return list(reversed(rows))

    def latest_adaptive_prescription(self, patient: str, level: int | None = None) -> sqlite3.Row | None:
        where = "WHERE patient_id = ?"
        params: list[Any] = [patient]
        if level is not None:
            where += " AND level = ?"
            params.append(level)
        rows = self.query(
            f"""
            SELECT *
            FROM adaptive_prescriptions
            {where}
            ORDER BY id DESC
            LIMIT 1
            """,
            params,
        )
        return rows[0] if rows else None

    def latest_forearm_assessment(self, patient: str) -> sqlite3.Row | None:
        rows = self.query(
            """
            SELECT *
            FROM forearm_assessments
            WHERE patient_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (patient,),
        )
        return rows[0] if rows else None

    def adaptive_history(self, patient: str = "", limit: int = 30) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        params.append(limit)
        return self.query(
            f"""
            SELECT *
            FROM adaptive_prescriptions
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )

    def adaptive_prescription(self, prescription_id: int) -> sqlite3.Row | None:
        rows = self.query("SELECT * FROM adaptive_prescriptions WHERE id = ?", (prescription_id,))
        return rows[0] if rows else None

    def save_override(self, form: dict[str, str]) -> None:
        prescription_id = int(number(form.get("prescription_id"), 0))
        row = self.adaptive_prescription(prescription_id)
        if not row:
            return
        ai_recommendation = {
            "id": row["id"],
            "patient_id": row["patient_id"],
            "level": row["level"],
            "difficulty_tier": row["difficulty_tier"],
            "required_rom": row["required_rom"],
            "repetitions": row["repetitions"],
            "hold_seconds": row["hold_seconds"],
            "progression": row["progression"],
            "readiness_score": row["readiness_score"],
            "risk_level": row["risk_level"],
            "rationale": row["rationale"],
        }
        modified = {
            "difficulty_tier": form.get("difficulty_tier", "").strip(),
            "required_rom": form.get("required_rom", "").strip(),
            "repetitions": form.get("repetitions", "").strip(),
            "hold_seconds": form.get("hold_seconds", "").strip(),
            "progression": form.get("progression", "").strip(),
        }
        patient_context = {
            "patient_id": row["patient_id"],
            "level": row["level"],
            "risk_level": row["risk_level"],
            "readiness_score": row["readiness_score"],
            "recovery_trend": row["recovery_trend"],
        }
        self.execute(
            """
            INSERT INTO therapist_overrides (
                prescription_id, patient_id, therapist_id, decision, reason,
                therapist_reason, ai_recommendation_json, modified_recommendation_json,
                patient_context_json, session_metrics_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prescription_id,
                row["patient_id"],
                form.get("therapist_id", "Therapist").strip() or "Therapist",
                form.get("decision", "accept").strip(),
                form.get("reason", "Clinical judgement").strip(),
                form.get("therapist_reason", "").strip(),
                json.dumps(ai_recommendation, sort_keys=True),
                json.dumps(modified, sort_keys=True),
                json.dumps(patient_context, sort_keys=True),
                row["metrics_json"] or "{}",
            ),
        )

    def override_history(self, patient: str = "", limit: int = 50) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        params.append(limit)
        return self.query(
            f"""
            SELECT *
            FROM therapist_overrides
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )

    def override_stats(self, patient: str = "") -> dict[str, Any]:
        rows = self.override_history(patient, limit=200)
        total = len(rows)
        if total == 0:
            return {
                "total": 0,
                "agreement_rate": 100.0,
                "override_rate": 0.0,
                "ai_confidence": 78.0,
                "override_probability": 0.22,
                "recommendation_reliability": 78.0,
                "common_reasons": [],
            }
        accepted = sum(1 for row in rows if str(row["decision"]).lower() == "accept")
        modified = sum(1 for row in rows if str(row["decision"]).lower() == "modify")
        rejected = sum(1 for row in rows if str(row["decision"]).lower() == "reject")
        agreement_rate = accepted / total * 100.0
        override_rate = (modified + rejected) / total * 100.0
        reason_counts: dict[str, int] = {}
        for row in rows:
            reason = row["reason"] or "Clinical judgement"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        common_reasons = sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)[:5]
        override_probability = min(0.95, max(0.02, override_rate / 100.0))
        reliability = max(0.0, 100.0 - override_rate * 0.65 - (rejected / total * 100.0) * 0.25)
        confidence = max(5.0, 100.0 * (1.0 - override_probability))
        return {
            "total": total,
            "agreement_rate": agreement_rate,
            "override_rate": override_rate,
            "ai_confidence": confidence,
            "override_probability": override_probability,
            "recommendation_reliability": reliability,
            "common_reasons": common_reasons,
        }

    def forearm_history(self, patient: str = "", limit: int = 30) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        params.append(limit)
        return self.query(
            f"""
            SELECT *
            FROM forearm_assessments
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )

    def upper_limb_history(self, patient: str = "", limit: int = 60) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        params.append(limit)
        return self.query(
            f"""
            SELECT *
            FROM upper_limb_assessments
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )

    def sensei_history(self, patient: str = "", limit: int = 30) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        params.append(limit)
        return self.query(
            f"""
            SELECT *
            FROM sensei_messages
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        )

    def latest_upper_limb_assessment(self, patient: str) -> sqlite3.Row | None:
        rows = self.upper_limb_history(patient, limit=1)
        return rows[0] if rows else None

    def research_metrics(self, patient: str = "") -> dict[str, float]:
        sessions = self.sessions_chrono(patient)
        prescriptions = list(reversed(self.adaptive_history(patient, limit=60)))
        forearm = list(reversed(self.forearm_history(patient, limit=60)))
        upper_limb = list(reversed(self.upper_limb_history(patient, limit=60)))
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
        pain_adjusted = sum(
            acc * max(0.0, min(1.0, (10.0 - pain) / 10.0))
            for acc, pain in zip(acc_values, pain_values)
        ) / len(sessions)
        weekly_rom = self._weekly_rom_improvement(sessions)
        adherence = self._session_adherence(sessions) * 100.0
        difficulty_progression = 0.0
        if len(prescriptions) >= 2:
            difficulty_progression = number(prescriptions[-1]["difficulty_tier"]) - number(prescriptions[0]["difficulty_tier"])
        forearm_progress = 0.0
        if len(forearm) >= 2:
            first = number(forearm[0]["smoothness"]) - number(forearm[0]["compensation_score"])
            last = number(forearm[-1]["smoothness"]) - number(forearm[-1]["compensation_score"])
            forearm_progress = (last - first) * 100.0
        compensation_frequency = 0.0
        shoulder_comp = 0.0
        elbow_comp = 0.0
        trunk_comp = 0.0
        movement_efficiency = 0.0
        if upper_limb:
            compensation_frequency = sum(1 for row in upper_limb if number(row["compensation_score"]) >= 0.45) / len(upper_limb) * 100.0
            shoulder_comp = sum(number(row["shoulder_compensation"]) for row in upper_limb) / len(upper_limb) * 100.0
            elbow_comp = sum(number(row["elbow_compensation"]) for row in upper_limb) / len(upper_limb) * 100.0
            trunk_comp = sum(number(row["trunk_compensation"]) for row in upper_limb) / len(upper_limb) * 100.0
            movement_efficiency = sum(number(row["movement_efficiency"]) for row in upper_limb) / len(upper_limb)

        return {
            "weekly_rom_improvement": weekly_rom,
            "accuracy_improvement": trend(acc_values),
            "pain_adjusted_performance": pain_adjusted,
            "session_adherence": adherence,
            "difficulty_progression": difficulty_progression,
            "forearm_progress": forearm_progress,
            "compensation_frequency": compensation_frequency,
            "shoulder_compensation": shoulder_comp,
            "elbow_compensation": elbow_comp,
            "trunk_compensation": trunk_comp,
            "movement_efficiency": movement_efficiency,
        }

    def digital_twin_profile(self, patient: str):
        if not patient:
            return None
        return self.digital_twin.build(patient, save=True)

    def digital_twin_snapshots(self, patient: str, limit: int = 12) -> list[sqlite3.Row]:
        if not patient:
            return []
        return self.digital_twin.snapshot_history(patient, limit=limit)

    def _weekly_rom_improvement(self, sessions: list[sqlite3.Row]) -> float:
        if len(sessions) < 2:
            return 0.0
        try:
            start = datetime.fromisoformat(str(sessions[0]["timestamp"]))
            end = datetime.fromisoformat(str(sessions[-1]["timestamp"]))
            days = max((end - start).total_seconds() / 86400.0, 1.0)
        except ValueError:
            days = max(len(sessions) - 1, 1)
        return (number(sessions[-1]["avg_hand_angle"]) - number(sessions[0]["avg_hand_angle"])) / days * 7.0

    def _session_adherence(self, sessions: list[sqlite3.Row]) -> float:
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
        return max(0.0, min(1.0, 1.0 - avg_gap / 10.0))

    def notes(self, patient: str = "", session_id: str = "", date_filter: str = "") -> list[sqlite3.Row]:
        params: list[Any] = []
        clauses: list[str] = []
        if patient:
            clauses.append("n.patient_id = ?")
            params.append(patient)
        if session_id:
            clauses.append("n.session_id = ?")
            params.append(int(number(session_id)))
        if date_filter:
            clauses.append("date(n.created_at) = date(?)")
            params.append(date_filter)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        return self.query(
            f"""
            SELECT
                n.id, n.patient_id AS patient_name, n.patient_id, n.session_id,
                'Clinical Note' AS note_type, n.note_text AS note,
                n.recommendation, '' AS next_plan, n.clinical_observation,
                n.therapist_name, n.created_at, n.modified_at, s.timestamp, s.level
            FROM therapist_notes n
            LEFT JOIN sessions s ON s.id = n.session_id
            {where}
            ORDER BY datetime(n.created_at) DESC, n.id DESC
            """,
            params,
        )

    def save_note(self, form: dict[str, str]) -> None:
        patient = form.get("patient_name", "").strip()
        note = form.get("note", "").strip()
        if not patient or not note:
            return
        session_id = form.get("session_id", "").strip()
        note_id = form.get("note_id", "").strip()
        values = (
            patient,
            int(session_id) if session_id.isdigit() else None,
            form.get("therapist_name", "Therapist").strip() or "Therapist",
            note,
            form.get("recommendation", "").strip(),
            form.get("clinical_observation", form.get("next_plan", "")).strip(),
        )
        if note_id.isdigit():
            self.execute(
                """
                UPDATE therapist_notes
                SET patient_id = ?, session_id = ?, therapist_name = ?,
                    note_text = ?, recommendation = ?, clinical_observation = ?,
                    modified_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*values, int(note_id)),
            )
            return
        self.execute(
            """
            INSERT INTO therapist_notes
                (patient_id, session_id, therapist_name, note_text, recommendation, clinical_observation)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            values,
        )

    def dashboard_stats(self) -> dict[str, Any]:
        patients = self.patients()
        sessions = self.sessions()
        total_seconds = sum(number(row["duration"]) for row in sessions)
        patient_predictions = [
            recovery_prediction(self.sessions_chrono(row["name"]))
            for row in patients
        ]
        predictions = [p for p in patient_predictions if p >= 0]
        seven_days_ago = datetime.now() - timedelta(days=7)
        active_sessions = 0
        active_patient_names: set[str] = set()
        for row in sessions:
            try:
                if datetime.fromisoformat(str(row["timestamp"])) >= seven_days_ago:
                    active_sessions += 1
                    active_patient_names.add(str(row["patient_id"]))
            except ValueError:
                pass
        patients_at_risk = 0
        for row in patients:
            clinical = self.clinical_intel.get_clinical_profile(row["name"])
            adaptive = self.latest_adaptive_prescription(row["name"])
            high_adaptive = adaptive and str(adaptive["risk_level"]).lower() == "high"
            if clinical["risk_level"] == "High" or high_adaptive or number(row["avg_pain"]) >= 6:
                patients_at_risk += 1
        return {
            "patients": len(patients),
            "active_patients": len(active_patient_names),
            "active_sessions": active_sessions,
            "completed_sessions": len(sessions),
            "avg_recovery": sum(predictions) / len(predictions) if predictions else 0,
            "overall_accuracy": sum(number(r["avg_accuracy"]) for r in sessions) / len(sessions) if sessions else 0,
            "avg_rom": sum(number(r["avg_hand_angle"]) for r in sessions) / len(sessions) if sessions else 0,
            "patients_at_risk": patients_at_risk,
            "avg_pain": sum(number(r["pain_level"]) for r in sessions) / len(sessions) if sessions else 0,
            "therapy_hours": total_seconds / 3600.0,
        }


class DashboardRenderer:
    def __init__(self, repo: DashboardRepository):
        self.repo = repo

    def layout(self, page: Page, params: dict[str, str] | None = None) -> bytes:
        params = params or {}
        theme = params.get("theme", "light")
        nav = [
            ("home", "/", "Overview", "D"),
            ("patients", "/patients", "Patients", "P"),
            ("sessions", "/sessions", "Sessions", "S"),
            ("analytics", "/analytics", "Analytics", "A"),
            ("adaptive", "/adaptive", "AI Insights", "AI"),
            ("sensei", "/sensei", "Sensei Review", "V"),
            ("risks", "/risks", "Risk Detection", "R"),
            ("reports", "/reports", "Reports", "PDF"),
            ("digital_twin", "/digital-twin", "Digital Twin", "DT"),
            ("performance", "/performance", "Performance", "E"),
            ("notes", "/notes", "Notes", "N"),
        ]
        nav_html = "".join(
            f'<a class="nav-item {"active" if key == page.active else ""}" href="{href}"><span class="nav-icon">{icon}</span> {label}</a>'
            for key, href, label, icon in nav
        )
        toggled_theme = "dark" if theme != "dark" else "light"
        html_doc = f"""<!doctype html>
<html lang="en" data-theme="{esc(theme)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(page.title)} - Therapist Dashboard</title>
  <style>{self.css()}</style>
</head>
<body>
  <aside class="sidebar glass-panel">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <div>
        <strong>Hand Rehab</strong>
        <span>Therapist Console</span>
      </div>
    </div>
    <nav class="nav-menu">
      {nav_html}
      <div class="nav-divider"></div>
      <a class="nav-item" href="#"><span class="nav-icon">⚙️</span> Settings</a>
      <a class="nav-item text-danger" href="#"><span class="nav-icon">🚪</span> Logout</a>
    </nav>
  </aside>
  <main class="main">
    <header class="topbar glass-panel">
      <div class="search-bar">
        <span class="search-icon">🔍</span>
        <input type="text" placeholder="Search patients, sessions..." class="search-input">
      </div>
      <div class="topbar-actions">
        <a class="icon-btn" href="/notifications" title="Notifications">🔔</a>
        <a class="icon-btn theme-toggle-btn" href="?theme={toggled_theme}" title="Toggle Theme">
          {'🌙' if theme == 'light' else '☀️'}
        </a>
        <div class="therapist-profile">
          <div class="avatar">Dr</div>
          <div class="profile-info">
            <strong>Therapist Profile</strong>
            <span>Admin</span>
          </div>
        </div>
      </div>
    </header>
    <div class="page-header">
      <div>
        <h1>{esc(page.title)}</h1>
        <p>Centralized rehabilitation monitoring for clinical review and decision support.</p>
      </div>
      <div class="date-chip">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</div>
    </div>
    {page.body}
  </main>
  <script>{self.js()}</script>
  {page.scripts}
</body>
</html>"""
        return html_doc.encode("utf-8")

    def css(self) -> str:
        return """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
  --bg: #f8fafc;
  --panel: rgba(255, 255, 255, 0.85);
  --panel-2: rgba(241, 245, 249, 0.8);
  --text: #0f172a;
  --muted: #64748b;
  --line: rgba(226, 232, 240, 0.8);
  --primary: #2563EB;
  --primary-2: #06B6D4;
  --success: #22C55E;
  --warning: #F59E0B;
  --danger: #EF4444;
  --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
  --shadow-hover: 0 20px 25px -5px rgba(37, 99, 235, 0.1), 0 10px 10px -5px rgba(37, 99, 235, 0.04);
  --glass-border: rgba(255, 255, 255, 0.5);
}
[data-theme="dark"] {
  --bg: #0f172a;
  --panel: rgba(30, 41, 59, 0.85);
  --panel-2: rgba(51, 65, 85, 0.8);
  --text: #f8fafc;
  --muted: #94a3b8;
  --line: rgba(51, 65, 85, 0.8);
  --primary: #3b82f6;
  --primary-2: #22d3ee;
  --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
  --shadow-hover: 0 20px 25px -5px rgba(59, 130, 246, 0.2);
  --glass-border: rgba(255, 255, 255, 0.05);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  transition: background-color 0.3s ease, color 0.3s ease;
}
a { color: inherit; text-decoration: none; }

/* Layout Elements */
.glass-panel {
  background: var(--panel);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
}
.sidebar {
  position: fixed; inset: 0 auto 0 0; width: 280px; padding: 24px 20px;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--line);
  z-index: 100;
  box-shadow: 4px 0 24px rgba(0,0,0,0.02);
}
.brand { display: flex; gap: 14px; align-items: center; margin-bottom: 36px; padding: 0 8px; }
.brand-mark {
  width: 46px; height: 46px; border-radius: 8px;
  display: grid; place-items: center;
  color: white; background: linear-gradient(135deg, var(--primary), var(--primary-2));
  font-weight: 800; font-size: 18px;
  box-shadow: 0 8px 16px rgba(37, 99, 235, 0.25);
}
.brand strong { display: block; font-size: 18px; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
.brand span, .topbar p, .muted { color: var(--muted); font-size: 13px; font-weight: 500; }

.nav-menu { display: flex; flex-direction: column; gap: 4px; flex-grow: 1; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border-radius: 8px;
  color: var(--muted); font-weight: 600; font-size: 14px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.nav-icon { font-size: 18px; opacity: 0.8; }
.nav-item.active, .nav-item:hover {
  background: var(--panel-2); color: var(--primary);
  transform: translateX(4px);
}
.nav-item.active .nav-icon { opacity: 1; }
.nav-divider { height: 1px; background: var(--line); margin: 16px 0; }
.text-danger:hover { color: var(--danger) !important; background: rgba(239, 68, 68, 0.1) !important; }

.main { margin-left: 280px; padding: 0; min-height: 100vh; display: flex; flex-direction: column; }
.topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 24px;
  padding: 16px 40px; border-bottom: 1px solid var(--line);
  position: sticky; top: 0; z-index: 90;
}
.search-bar {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg); border: 1px solid var(--line);
  padding: 8px 16px; border-radius: 8px;
  width: 100%; max-width: 400px; transition: all 0.2s ease;
}
.search-bar:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
.search-input { border: none; background: transparent; width: 100%; outline: none; padding: 0; color: var(--text); font-family: 'Inter', sans-serif;}
.search-input:focus { box-shadow: none; }

.topbar-actions { display: flex; align-items: center; gap: 16px; }
.icon-btn {
  display: grid; place-items: center;
  width: 40px; height: 40px; border-radius: 8px;
  background: var(--bg); color: var(--text); border: 1px solid var(--line);
  font-size: 16px; transition: all 0.2s ease;
}
.icon-btn:hover { background: var(--panel-2); transform: translateY(-2px); }

.therapist-profile { display: flex; align-items: center; gap: 12px; margin-left: 12px; padding-left: 16px; border-left: 1px solid var(--line); cursor: pointer; }
.avatar {
  width: 42px; height: 42px; border-radius: 8px;
  background: linear-gradient(135deg, var(--primary-2), var(--primary));
  color: white; display: grid; place-items: center; font-weight: 700;
}
.profile-info { display: flex; flex-direction: column; }
.profile-info strong { font-size: 14px; font-weight: 600; color: var(--text); }
.profile-info span { font-size: 12px; color: var(--muted); }

.page-header { padding: 32px 40px 16px; display: flex; align-items: center; justify-content: space-between; }
h1 { margin: 0 0 8px; font-size: 32px; font-weight: 800; letter-spacing: -0.03em; }
h2 { margin: 0 0 16px; font-size: 18px; font-weight: 700; letter-spacing: -0.01em; }
.date-chip, .pill {
  padding: 8px 16px; border: 1px solid var(--line);
  background: var(--panel); border-radius: 8px;
  color: var(--primary); font-size: 13px; font-weight: 600;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

/* Sections */
.main > section { padding: 0 40px 32px; }
.grid { display: grid; gap: 24px; }
.stats { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.two { grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.8fr); }
.three { grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }

.card {
  background: var(--panel);
  border: 1px solid var(--glass-border);
  border-radius: 8px;
  padding: 24px;
  box-shadow: var(--shadow);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.card:hover { transform: translateY(-4px); box-shadow: var(--shadow-hover); }

.stat-label { color: var(--muted); font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; display: flex; align-items: center; gap: 8px; }
.stat-value { margin-top: 12px; font-size: 36px; font-weight: 800; color: var(--text); line-height: 1; letter-spacing: -0.02em; }
.stat-sub { margin-top: 8px; color: var(--muted); font-size: 13px; font-weight: 500; }

.toolbar { display: flex; gap: 12px; align-items: center; justify-content: space-between; margin-bottom: 24px; flex-wrap: wrap; }
input:not(.search-input), select, textarea {
  width: 100%; border: 1px solid var(--line);
  background: var(--bg); color: var(--text);
  border-radius: 8px; padding: 12px 16px;
  font: inherit; font-size: 14px;
  transition: all 0.2s ease; outline: none;
}
input:focus:not(.search-input), select:focus, textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15); }
textarea { min-height: 120px; resize: vertical; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; }
.full { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; gap: 8px; font-size: 13px; font-weight: 600; color: var(--text); }

button, .button {
  display: inline-flex; align-items: center; justify-content: center;
  border: 0; border-radius: 8px; padding: 12px 24px;
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  color: white; font-weight: 600; font-size: 14px; cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
}
button:hover, .button:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(37, 99, 235, 0.3); }
button:active, .button:active { transform: translateY(0); }
.button.secondary { background: var(--bg); color: var(--text); border: 1px solid var(--line); box-shadow: none; }
.button.secondary:hover { background: var(--panel-2); border-color: var(--primary); box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
.button.danger, button.danger { background: linear-gradient(135deg, var(--danger), #b91c1c); box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2); }

table { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 8px; }
th, td { padding: 16px 16px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }
th { color: var(--muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; border-bottom-width: 2px; }
tr:last-child td { border-bottom: none; }
tr { transition: background-color 0.15s ease; }
tr:hover td { background: var(--bg); }

.progress { height: 8px; border-radius: 8px; background: var(--bg); overflow: hidden; margin-top: 8px; border: 1px solid var(--line); }
.progress span { display: block; height: 100%; background: linear-gradient(90deg, var(--primary), var(--success)); border-radius: 8px; }
.badge { padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; background: rgba(37, 99, 235, 0.1); color: var(--primary); display: inline-block; }

.alert { border-left: 5px solid var(--primary); padding-left: 20px; border-radius: 8px; background: rgba(37, 99, 235, 0.03); }
.alert.warning { border-left-color: var(--warning); background: rgba(245, 158, 11, 0.03); }
.alert.warning .badge { color: var(--warning); background: rgba(245, 158, 11, 0.1); }
.alert.danger { border-left-color: var(--danger); background: rgba(239, 68, 68, 0.03); }
.alert.danger .badge { color: var(--danger); background: rgba(239, 68, 68, 0.1); }

.chart { width: 100%; border-radius: 8px; border: 1px solid var(--line); background: #ffffff; mix-blend-mode: normal; box-shadow: 0 4px 12px rgba(0,0,0,0.02); }
[data-theme="dark"] .chart { filter: brightness(0.9) contrast(1.1); }
.tabs { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
.pagination { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }

@media (max-width: 1024px) {
  .sidebar { width: 240px; }
  .main { margin-left: 240px; }
  .topbar, .page-header, .main > section { padding-left: 24px; padding-right: 24px; }
}
@media (max-width: 768px) {
  .sidebar { position: static; width: 100%; border-right: none; border-bottom: 1px solid var(--line); padding: 20px; }
  .nav-menu { flex-direction: row; flex-wrap: wrap; gap: 8px; }
  .nav-item { padding: 10px 14px; flex: 1; min-width: 140px; justify-content: center; }
  .nav-divider { display: none; }
  .main { margin-left: 0; }
  .topbar { flex-direction: column; align-items: stretch; gap: 16px; }
  .search-bar { max-width: none; }
  .therapist-profile { border-left: none; padding-left: 0; margin-left: auto; }
  .stats, .two, .three, .form-grid { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; align-items: flex-start; gap: 16px; }
}
"""

    def js(self) -> str:
        return """
function filterTable(inputId, tableId) {
  const q = document.getElementById(inputId)?.value.toLowerCase() || "";
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none";
  });
}
function sortTable(tableId, column) {
  const table = document.getElementById(tableId);
  const body = table.querySelector("tbody");
  const rows = Array.from(body.querySelectorAll("tr"));
  const asc = table.dataset.sort !== String(column);
  rows.sort((a, b) => {
    const av = a.children[column].innerText.trim();
    const bv = b.children[column].innerText.trim();
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!Number.isNaN(an) && !Number.isNaN(bn)) return asc ? an - bn : bn - an;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  table.dataset.sort = asc ? String(column) : "";
  rows.forEach(row => body.appendChild(row));
}
"""

    def chart(self, title: str, series: dict[str, list[float]], labels: list[str], ylabel: str = "") -> str:
        fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=130)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")
        colors = ["#0077b6", "#1da365", "#dc8f14", "#cc404a", "#5d5fef"]
        for index, (name, values) in enumerate(series.items()):
            ax.plot(labels, values, marker="o", linewidth=2.4, color=colors[index % len(colors)], label=name)
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color="#1c2735")
        ax.set_ylabel(ylabel, color="#66778a")
        ax.grid(True, color="#dbe7f0", linewidth=.8)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8, colors="#66778a")
        ax.tick_params(axis="y", colors="#66778a")
        for spine in ax.spines.values():
            spine.set_color("#d2e0ec")
        if len(series) > 1:
            ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f'<img class="chart" alt="{esc(title)}" src="data:image/png;base64,{encoded}">'

    def stat_card(self, label: str, value: str, sub: str = "") -> str:
        return f"""
        <section class="card">
          <div class="stat-label">{esc(label)}</div>
          <div class="stat-value">{esc(value)}</div>
          <div class="stat-sub">{esc(sub)}</div>
        </section>
        """

    def home(self) -> Page:
        stats = self.repo.dashboard_stats()
        recent = self.repo.sessions(limit=8)
        patients = self.repo.patients()
        recent_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['timestamp']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_hand_angle']):.1f} deg</td>
              <td>{esc(format_duration(row['duration']))}</td>
            </tr>
            """
            for row in recent
        ) or '<tr><td colspan="6" class="muted">No session data yet.</td></tr>'
        alert_cards = self.alert_cards()
        body = f"""
        <section class="grid stats">
          {self.stat_card('Total Patients', str(stats['patients']), 'Registered or session-linked patients')}
          {self.stat_card('Active Patients', str(stats['active_patients']), 'Patients seen in the last 7 days')}
          {self.stat_card('Total Rehabilitation Sessions', str(stats['completed_sessions']), f"{stats['active_sessions']} sessions this week")}
          {self.stat_card('Average Recovery Progress', f"{stats['avg_recovery']:.1f}%", 'Linear trend projection where available')}
          {self.stat_card('Average Accuracy', f"{stats['overall_accuracy']:.1f}%", 'Average exercise success rate')}
          {self.stat_card('Average ROM', f"{stats['avg_rom']:.1f} deg", 'Mean recorded hand angle')}
          {self.stat_card('Patients At Risk', str(stats['patients_at_risk']), 'High pain, high risk, or flagged trend')}
          {self.stat_card('Average Pain Score', f"{stats['avg_pain']:.1f}/10", 'Mean recorded pre-session NRS')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">
            <div class="toolbar"><h2>Recent Patient Activity</h2><a class="button secondary" href="/sessions">View all</a></div>
            <table>
              <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead>
              <tbody>{recent_rows}</tbody>
            </table>
          </div>
          <div class="grid">{alert_cards}</div>
        </section>
        """
        return Page("Dashboard Home", body, "home")

    def patients(self, params: dict[str, str]) -> Page:
        q = params.get("q", "").lower()
        stage = params.get("stage", "")
        selected = params.get("patient", "")
        rows = self.repo.patients()
        if q:
            rows = [row for row in rows if q in " ".join(str(row[k] or "") for k in row.keys()).lower()]
        if stage:
            rows = [row for row in rows if row["rehab_stage"] == stage]
        selected_row = self.repo.patient(selected) if selected else None
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(row['id_number'] or '-')}</td>
              <td><a href="/patients?patient={quote(row['name'])}"><strong>{esc(row['name'])}</strong></a><div class="muted">{esc(row['gender'] or 'Gender not set')}</div></td>
              <td>{esc(row['age'] or '-')}</td>
              <td>{esc(row['injury_type'] or row['age_group'] or 'Not specified')}</td>
              <td>{esc(short_date(row['registration_date']))}</td>
              <td>{esc(short_date(row['last_session']))}</td>
              <td><span class="badge">{esc(self.recovery_status(row))}</span></td>
              <td>{int(row['sessions_count'])}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_rom']):.1f} deg</td>
              <td><a class="button secondary" href="/patients?patient={quote(row['name'])}">View Profile</a></td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="11" class="muted">No matching patients.</td></tr>'
        profile = self.patient_profile(selected_row) if selected_row else self.patient_form(None)
        body = f"""
        <section class="grid two">
          <div class="card">
            <div class="toolbar">
              <h2>Patient Management</h2>
              <form method="get" class="toolbar">
                <input name="q" value="{esc(params.get('q',''))}" placeholder="Search patients">
                <select name="stage">
                  {self.option('', 'All stages', stage)}
                  {self.option('Acute', 'Acute', stage)}
                  {self.option('Subacute', 'Subacute', stage)}
                  {self.option('Chronic', 'Chronic', stage)}
                  {self.option('Maintenance', 'Maintenance', stage)}
                </select>
                <button>Filter</button>
              </form>
            </div>
            <table id="patientsTable">
              <thead><tr><th onclick="sortTable('patientsTable',0)">Patient ID</th><th onclick="sortTable('patientsTable',1)">Patient Name</th><th>Age</th><th>Condition / Injury</th><th>Registration Date</th><th>Last Session Date</th><th>Recovery Status</th><th>Sessions</th><th>Accuracy</th><th>ROM</th><th></th></tr></thead>
              <tbody>{table_rows}</tbody>
            </table>
          </div>
          {profile}
        </section>
        """
        return Page("Patient Management", body, "patients")

    def patient_form(self, row: sqlite3.Row | None) -> str:
        name = row["name"] if row else ""
        return f"""
        <div class="card">
          <h2>{'Edit Patient Profile' if row else 'Register Patient'}</h2>
          <form method="post" action="/patients/save" class="form-grid">
            <label>Name<input name="name" value="{esc(name)}" {'readonly' if row else ''} required></label>
            <label>ID Number (Login)<input name="id_number" value="{esc(row['id_number'] if row else '')}" placeholder="Optional custom ID"></label>
            <label>Age<input name="age" type="number" min="0" max="120" value="{esc(row['age'] if row else '')}"></label>
            <label>Gender<input name="gender" value="{esc(row['gender'] if row else '')}" placeholder="Female, Male, Other"></label>
            <label>Age group<input name="age_group" value="{esc(row['age_group'] if row else '')}" placeholder="adult, senior"></label>
            <label>Injury type<input name="injury_type" value="{esc(row['injury_type'] if row else '')}" placeholder="Stroke, fracture, tendon injury"></label>
            <label>Rehabilitation stage
              <select name="rehab_stage">
                {self.option('', 'Select stage', row['rehab_stage'] if row else '')}
                {self.option('Acute', 'Acute', row['rehab_stage'] if row else '')}
                {self.option('Subacute', 'Subacute', row['rehab_stage'] if row else '')}
                {self.option('Chronic', 'Chronic', row['rehab_stage'] if row else '')}
                {self.option('Maintenance', 'Maintenance', row['rehab_stage'] if row else '')}
              </select>
            </label>
            <label class="full">Assigned exercises<textarea name="assigned_exercises">{esc(row['assigned_exercises'] if row else '')}</textarea></label>
            <label class="full">Therapist notes<textarea name="therapist_notes">{esc(row['therapist_notes'] if row else '')}</textarea></label>
            <div class="full toolbar">
              <button>Save Patient</button>
              {f'<a class="button secondary" href="/patients?patient={quote(name)}">View History</a>' if row else ''}
            </div>
          </form>
        </div>
        """

    def patient_profile(self, row: sqlite3.Row) -> str:
        sessions = self.repo.sessions(row["name"], limit=12)
        sessions_chrono = self.repo.sessions_chrono(row["name"])
        adaptive = self.repo.latest_adaptive_prescription(row["name"])
        forearm = self.repo.latest_forearm_assessment(row["name"])
        upper_limb = self.repo.latest_upper_limb_assessment(row["name"])
        coaching = self.repo.sensei_history(row["name"], limit=10)
        clinical = self.repo.clinical_intel.get_clinical_profile(row["name"])
        pred = recovery_prediction(sessions_chrono)
        readiness = number(adaptive["readiness_score"]) if adaptive else clinical["health_score"]
        latest_session = sessions_chrono[-1] if sessions_chrono else None
        recovery_score_value = calculated_functional_recovery_score(latest_session) if latest_session else 0.0
        recovery_category_value = recovery_category(recovery_score_value) if latest_session else "Not started"
        pain_before = number(row_value(latest_session, "pain_before_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_after = number(row_value(latest_session, "pain_after_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_delta = number(row_value(latest_session, "pain_difference", 0)) if latest_session else 0
        recent_notes = self.repo.notes(row["name"])[:5]
        notes_rows = "".join(
            f"<tr><td>{esc(short_date(note['created_at']))}</td><td>{esc(note['therapist_name'])}</td><td>{esc(note['note'])}</td><td>{esc(note['recommendation'])}</td></tr>"
            for note in recent_notes
        ) or '<tr><td colspan="4" class="muted">No therapist notes recorded.</td></tr>'
        history = "".join(
            f"<tr><td>{esc(short_date(s['timestamp']))}</td><td>{esc(exercise_for_level(s['level']))}</td><td>{number(s['avg_accuracy']):.1f}%</td><td>{number(s['avg_hand_angle']):.1f} deg</td><td>{esc(format_duration(s['duration']))}</td></tr>"
            for s in sessions
        ) or '<tr><td colspan="5" class="muted">No rehabilitation history yet.</td></tr>'
        if adaptive:
            adaptive_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>AI Prescription Panel</h2>
              <div class="grid three">
                {self.stat_card('Difficulty Tier', str(int(number(adaptive['difficulty_tier']))), f"{adaptive['progression'].title()} progression")}
                {self.stat_card('Readiness Score', f"{number(adaptive['readiness_score']):.0f}/100", 'Adaptive AI Engine')}
                {self.stat_card('Risk Level', adaptive['risk_level'].title(), f"Recovery: {adaptive['recovery_trend']}")}
                {self.stat_card('Target / Speed', f"{number(adaptive['target_scale']):.2f}x / {number(adaptive['speed_scale']):.2f}x", 'Exercise adaptation')}
                {self.stat_card('ROM / Reps', f"{number(adaptive['required_rom']):.0f} deg / {int(number(adaptive['repetitions']))}", f"{number(adaptive['hold_seconds']):.1f}s hold")}
                {self.stat_card('Rotation Tolerance', f"{number(adaptive['rotation_tolerance']):.0f} deg", f"{number(adaptive['time_limit']):.0f}s time limit")}
              </div>
              <p class="muted" style="margin-top:12px">{esc(adaptive['rationale'])}</p>
              <p><strong>Override recommendation:</strong> {esc(adaptive['override_recommendation'])}</p>
              <p><strong>Decision source:</strong> Adaptive AI Engine; <strong>Safety logic:</strong> Rule-Based Logic; <strong>LLM:</strong> Optional communication enhancement only.</p>
            </div>
            """
        else:
            adaptive_panel = '<div class="card muted" style="margin-top:16px">No adaptive AI recommendation has been generated yet.</div>'

        if forearm:
            forearm_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Forearm Classification</h2>
              <table>
                <tbody>
                  <tr><th>Latest Class</th><td>{esc(forearm['movement_class'])}</td></tr>
                  <tr><th>Rotation Angle</th><td>{number(forearm['rotation_angle']):.1f} deg</td></tr>
                  <tr><th>Smoothness</th><td>{number(forearm['smoothness']) * 100:.0f}%</td></tr>
                  <tr><th>Compensation</th><td>{number(forearm['compensation_score']) * 100:.0f}%</td></tr>
                </tbody>
              </table>
            </div>
            """
        else:
            forearm_panel = '<div class="card muted" style="margin-top:16px">No forearm classification recorded yet.</div>'
        if upper_limb:
            upper_limb_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Upper Limb Compensation</h2>
              <div class="grid three">
                {self.stat_card('Compensation', f"{number(upper_limb['compensation_score']) * 100:.0f}%", esc(upper_limb['feedback']))}
                {self.stat_card('Efficiency', f"{number(upper_limb['movement_efficiency']):.0f}%", f"{esc(upper_limb['side'])} side")}
                {self.stat_card('Trunk Lean', f"{number(upper_limb['trunk_lean_angle']):.1f} deg", 'Pose estimate')}
              </div>
              <table style="margin-top:12px">
                <tbody>
                  <tr><th>Shoulder Angle</th><td>{number(upper_limb['shoulder_angle']):.1f} deg</td></tr>
                  <tr><th>Elbow Angle</th><td>{number(upper_limb['elbow_angle']):.1f} deg</td></tr>
                  <tr><th>Shoulder / Elbow / Trunk Compensation</th><td>{number(upper_limb['shoulder_compensation']) * 100:.0f}% / {number(upper_limb['elbow_compensation']) * 100:.0f}% / {number(upper_limb['trunk_compensation']) * 100:.0f}%</td></tr>
                </tbody>
              </table>
            </div>
            """
        else:
            upper_limb_panel = '<div class="card muted" style="margin-top:16px">No upper limb compensation assessment recorded yet.</div>'

        if coaching:
            coaching_rows = "".join(
                f"<tr><td>{esc(short_date(c['created_at']))}</td><td>{esc(exercise_for_level(c['level']))}</td><td>{esc(row_value(c, 'deterministic_message', c['message']))}</td><td>{esc(row_value(c, 'llm_enhanced_message', ''))}</td><td>{esc(row_value(c, 'coaching_trigger', self.sensei_trigger(c)))}</td></tr>"
                for c in coaching
            )
            coaching_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Virtual Sensei Panel</h2>
              <table><thead><tr><th>Date</th><th>Exercise</th><th>Generated Coaching Message</th><th>LLM Enhanced Message</th><th>Coaching Trigger</th></tr></thead><tbody>{coaching_rows}</tbody></table>
            </div>
            """
        else:
            coaching_panel = '<div class="card muted" style="margin-top:16px">No coaching history generated yet.</div>'

        insights_html = "".join(f"<li>{esc(i)}</li>" for i in clinical["insights"])
        recs_html = "".join(f"<li>{esc(r)}</li>" for r in clinical["recommendations"])
        risks_html = "".join(f'<span class="badge" style="color:var(--danger)">{esc(r)}</span>' for r in clinical["detected_risks"]) or '<span class="muted">No immediate risks detected.</span>'
        
        clinical_panel = f"""
        <div class="card" style="margin-top:16px; border-left: 4px solid var(--primary)">
          <h2>Clinical Health & Decision Support</h2>
          <div class="grid three">
            {self.stat_card('Health Score', f"{clinical['health_score']}/100", f"Trend: {clinical['trend']}")}
            {self.stat_card('Recovery Stage', clinical['recovery_stage'], 'Based on ROM progression')}
            {self.stat_card('Risk Level', clinical['risk_level'], 'Clinical risk assessment')}
          </div>
          <div style="margin-top:16px">
            <h3>Detected Risks</h3>
            <div style="display:flex; gap:8px; flex-wrap:wrap">{risks_html}</div>
          </div>
          <div class="grid two" style="margin-top:16px">
            <div>
              <h3>Rehabilitation Insights</h3>
              <ul style="margin:0; padding-left:20px">{insights_html}</ul>
            </div>
            <div>
              <h3>Therapist Recommendations</h3>
              <ul style="margin:0; padding-left:20px">{recs_html}</ul>
            </div>
          </div>
        </div>
        """

        return f"""
        <div>
          <div class="card" style="margin-bottom:16px">
            <div class="toolbar">
              <h2>Patient Profile</h2>
              <a class="button" href="/report.pdf?patient={quote(row['name'])}">Download PDF Report</a>
            </div>
            <table>
              <tbody>
                <tr><th>Patient ID</th><td>{esc(row['id_number'] or row['name'])}</td><th>Name</th><td>{esc(row['name'])}</td></tr>
                <tr><th>Age</th><td>{esc(row['age'] or '-')}</td><th>Gender</th><td>{esc(row['gender'] or '-')}</td></tr>
                <tr><th>Condition</th><td>{esc(row['injury_type'] or '-')}</td><th>Registration Date</th><td>{esc(short_date(row['registration_date']))}</td></tr>
              </tbody>
            </table>
          </div>
          <div class="grid three" style="margin-bottom:16px">
            {self.stat_card('Total Sessions', str(int(number(row['sessions_count']))), 'Stored rehabilitation sessions')}
            {self.stat_card('Recovery Prediction', f"{pred:.1f}%" if pred >= 0 else 'Need more data', 'Projected ROM trend')}
            {self.stat_card('Current Recovery Stage', clinical['recovery_stage'], f"Status: {self.recovery_status(row)}")}
            {self.stat_card('Readiness Score', f"{readiness:.0f}/100", 'Adaptive or clinical readiness')}
            {self.stat_card('Overall Accuracy', f"{number(row['avg_accuracy']):.1f}%", 'Average across sessions')}
            {self.stat_card('Maximum ROM Achieved', f"{number(row['max_rom']):.1f} deg", 'Best recorded hand angle')}
            {self.stat_card('Recovery Score', f"{recovery_score_value:.0f}/100", recovery_category_value)}
            {self.stat_card('Pain Summary', f"{pain_before:.0f}/10 to {pain_after:.0f}/10", f"Difference {pain_delta:+.0f}")}
            {self.stat_card('Exercise Compliance', 'Future Feature', 'Assigned vs completed sessions')}
          </div>
          <div class="card" style="margin-top:16px">
            <h2>Therapist Notes Panel</h2>
            <table><thead><tr><th>Date</th><th>Therapist</th><th>Clinical Observations</th><th>Latest Recommendations</th></tr></thead><tbody>{notes_rows}</tbody></table>
          </div>
          <div class="card muted" style="margin-top:16px">
            <h2>Compensation Analysis (Coming Soon)</h2>
            <p>Future MediaPipe Hands + MediaPipe Pose integration for shoulder lifting, elbow drift, trunk leaning, and compensatory movement score.</p>
          </div>
          {self.patient_form(row)}
          {clinical_panel}
          <div class="card" style="margin-top:16px">
            <div class="toolbar">
              <h2>Complete Rehabilitation History</h2>
              <form method="post" action="/patients/delete" onsubmit="return confirm('Delete this patient profile and notes? Session records are preserved.');">
                <input type="hidden" name="name" value="{esc(row['name'])}">
                <button class="danger">Delete Patient</button>
              </form>
            </div>
            <table><thead><tr><th>Date</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead><tbody>{history}</tbody></table>
          </div>
          {adaptive_panel}
          {coaching_panel}
          {forearm_panel}
          {upper_limb_panel}
        </div>
        """

    def option(self, value: str, label: str, selected: str) -> str:
        return f'<option value="{esc(value)}" {"selected" if value == selected else ""}>{esc(label)}</option>'

    def recovery_status(self, row: sqlite3.Row) -> str:
        clinical = self.repo.clinical_intel.get_clinical_profile(row["name"])
        return recovery_status_from_metrics(
            number(row["avg_accuracy"]),
            number(row["avg_rom"]),
            clinical["risk_level"],
            int(number(row["sessions_count"])),
        )

    def short_text(self, value: Any, max_words: int = 18) -> str:
        words = str(value or "").split()
        if len(words) <= max_words:
            return " ".join(words) if words else "-"
        return " ".join(words[:max_words]) + "..."

    def sessions_page(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        exercise_filter = params.get("exercise", "")
        min_pain = number(params.get("min_pain"), -1)
        rows = self.repo.sessions(patient)
        if exercise_filter:
            rows = [row for row in rows if str(int(number(row["level"]))) == exercise_filter]
        if min_pain >= 0:
            rows = [row for row in rows if number(row["pain_level"]) >= min_pain]
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        exercise_options = "".join(self.option(str(level), name, exercise_filter) for level, name in LEVEL_NAMES.items())
        comparison_rows = rows[:2]
        comparison = ""
        if len(comparison_rows) == 2:
            a, b = comparison_rows[1], comparison_rows[0]
            comparison = f"""
            <div class="grid three" style="margin-top:16px">
              {self.stat_card('Accuracy Change', f"{number(b['avg_accuracy']) - number(a['avg_accuracy']):+.1f}%", 'Latest vs previous filtered session')}
              {self.stat_card('ROM Change', f"{number(b['avg_hand_angle']) - number(a['avg_hand_angle']):+.1f} deg", 'Latest vs previous filtered session')}
              {self.stat_card('Pain Change', f"{number(b['pain_level']) - number(a['pain_level']):+.0f}/10", 'Latest vs previous filtered session')}
            </div>
            """
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['timestamp']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{esc(format_duration(row['duration']))}</td>
              <td>{number(row['max_finger_extension']):.1f}px</td>
              <td>{number(row['avg_hand_angle']):.1f} deg</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{int(number(row_value(row, 'pain_before_session', row['pain_level'])))}/10</td>
              <td>{int(number(row_value(row, 'pain_after_session', row['pain_level'])))}/10</td>
              <td>{int(number(row_value(row, 'pain_difference', 0))):+d}</td>
              <td>{calculated_functional_recovery_score(row):.1f}/100</td>
              <td>{fatigue_score(row):.1f}/10</td>
              <td>{esc(tremor_rating_for_sessions(self.repo.sessions_chrono(row['patient_id'])))}</td>
              <td>{int(number(row['score']))}</td>
              <td>{self.prediction_badge(row['patient_id'])}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="15" class="muted">No sessions found.</td></tr>'
        body = f"""
        <section class="card">
          <div class="toolbar">
            <h2>Session History</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <select name="exercise"><option value="">All exercises</option>{exercise_options}</select>
              <select name="min_pain">
                {self.option('-1', 'Any pain score', params.get('min_pain', '-1'))}
                {self.option('4', 'Pain 4+', params.get('min_pain', '-1'))}
                {self.option('7', 'Pain 7+', params.get('min_pain', '-1'))}
              </select>
              <button>Filter</button>
            </form>
          </div>
          <input id="sessionSearch" oninput="filterTable('sessionSearch','sessionsTable')" placeholder="Search session table">
          {comparison}
          <table id="sessionsTable" style="margin-top:12px">
            <thead><tr>
              <th onclick="sortTable('sessionsTable',0)">Session Date</th><th>Patient</th><th>Exercise Name</th><th>Duration</th><th>Max Extension</th><th>ROM</th><th>Accuracy</th><th>Pain Before</th><th>Pain After</th><th>Pain Difference</th><th>Recovery Score</th><th>Fatigue Score</th><th>Tremor</th><th>Score</th><th>Recovery Prediction</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
          <div class="pagination"><span class="pill">Client-side sorting, filtering, and table search enabled</span></div>
        </section>
        """
        return Page("Session History", body, "sessions")

    def prediction_badge(self, patient: str) -> str:
        pred = recovery_prediction(self.repo.sessions_chrono(patient))
        if pred < 0:
            return '<span class="badge">Need data</span>'
        return f'<span class="badge">{pred:.1f}%</span>'

    def analytics(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        sessions = self.repo.sessions_chrono(patient)
        labels = [short_date(row["timestamp"]) for row in sessions[-16:]]
        acc = [number(row["avg_accuracy"]) for row in sessions[-16:]]
        rom = [number(row["avg_hand_angle"]) for row in sessions[-16:]]
        pain = [number(row["pain_level"]) for row in sessions[-16:]]
        pain_before = [number(row_value(row, "pain_before_session", row["pain_level"])) for row in sessions[-16:]]
        pain_after = [number(row_value(row, "pain_after_session", row["pain_level"])) for row in sessions[-16:]]
        pain_difference = [number(row_value(row, "pain_difference", 0)) for row in sessions[-16:]]
        recovery_scores = [calculated_functional_recovery_score(row) for row in sessions[-16:]]
        latest = sessions[-1] if sessions else None
        latest_recovery = calculated_functional_recovery_score(latest) if latest else 0.0
        latest_category = recovery_category(latest_recovery) if latest else "Not started"
        avg_pain_delta = sum(pain_difference) / len(pain_difference) if pain_difference else 0.0
        actual_recovery = [min(100.0, number(row["avg_hand_angle"]) / 90.0 * 100.0) for row in sessions[-16:]]
        predicted_recovery = []
        for index in range(len(sessions[-16:])):
            pred = recovery_prediction(sessions[: max(0, len(sessions) - len(sessions[-16:])) + index + 1])
            predicted_recovery.append(pred if pred >= 0 else actual_recovery[index] if index < len(actual_recovery) else 0)
        prescriptions = list(reversed(self.repo.adaptive_history(patient, limit=16)))
        readiness_labels = [short_date(row["created_at"]) for row in prescriptions]
        readiness = [number(row["readiness_score"]) for row in prescriptions]
        daily_rom = self.bucket_metric(sessions, "%d %b", "avg_hand_angle")
        weekly_rom = self.bucket_metric(sessions, "%Y-W%W", "avg_hand_angle")
        monthly_rom = self.bucket_metric(sessions, "%Y-%m", "avg_hand_angle")
        weekly = self.bucket_progress(sessions, "%Y-W%W")
        monthly = self.bucket_progress(sessions, "%Y-%m")
        daily_pain = self.bucket_derived(sessions, "%d %b", lambda row: number(row_value(row, "pain_difference", 0)))
        weekly_pain = self.bucket_derived(sessions, "%Y-W%W", lambda row: number(row_value(row, "pain_difference", 0)))
        monthly_pain = self.bucket_derived(sessions, "%Y-%m", lambda row: number(row_value(row, "pain_difference", 0)))
        daily_recovery = self.bucket_derived(sessions, "%d %b", calculated_functional_recovery_score)
        weekly_recovery = self.bucket_derived(sessions, "%Y-W%W", calculated_functional_recovery_score)
        monthly_recovery = self.bucket_derived(sessions, "%Y-%m", calculated_functional_recovery_score)
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Progress Analytics</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid three" style="margin-top:16px">
          {self.stat_card('Recovery Score', f"{latest_recovery:.0f}/100", latest_category)}
          {self.stat_card('Pain Improvement', f"{avg_pain_delta:+.1f}", 'Average after-before change')}
          {self.stat_card('Latest Pain Summary', f"{pain_before[-1]:.0f}/10 to {pain_after[-1]:.0f}/10" if pain_before else '-', f"Difference {pain_difference[-1]:+.0f}" if pain_difference else 'No pain data')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('ROM Progress - Daily', {'Daily ROM': daily_rom[1]}, daily_rom[0], 'degrees')}</div>
          <div class="card">{self.chart('ROM Progress - Weekly', {'Weekly ROM': weekly_rom[1]}, weekly_rom[0], 'degrees')}</div>
          <div class="card">{self.chart('ROM Progress - Monthly', {'Monthly ROM': monthly_rom[1]}, monthly_rom[0], 'degrees')}</div>
          <div class="card">{self.chart('Accuracy Trends', {'Session Accuracy': acc}, labels, '%')}</div>
          <div class="card">{self.chart('Weekly Improvement', {'Weekly Accuracy': weekly[1]}, weekly[0], '%')}</div>
          <div class="card">{self.chart('Monthly Accuracy', {'Monthly Accuracy': monthly[1]}, monthly[0], '%')}</div>
          <div class="card">{self.chart('Pain Reduction Over Time', {'Pain Score': pain}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Pain Before vs Pain After', {'Before': pain_before, 'After': pain_after}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Daily Pain Trend', {'Pain Difference': daily_pain[1]}, daily_pain[0], 'after-before')}</div>
          <div class="card">{self.chart('Weekly Pain Trend', {'Pain Difference': weekly_pain[1]}, weekly_pain[0], 'after-before')}</div>
          <div class="card">{self.chart('Monthly Pain Trend', {'Pain Difference': monthly_pain[1]}, monthly_pain[0], 'after-before')}</div>
          <div class="card">{self.chart('Functional Recovery Score', {'Recovery Score': recovery_scores}, labels, 'score')}</div>
          <div class="card">{self.chart('Daily Recovery Score', {'Recovery Score': daily_recovery[1]}, daily_recovery[0], 'score')}</div>
          <div class="card">{self.chart('Weekly Recovery Score', {'Recovery Score': weekly_recovery[1]}, weekly_recovery[0], 'score')}</div>
          <div class="card">{self.chart('Monthly Recovery Score', {'Recovery Score': monthly_recovery[1]}, monthly_recovery[0], 'score')}</div>
          <div class="card">{self.chart('Recovery Prediction Trends', {'Predicted Recovery': predicted_recovery, 'Actual Recovery': actual_recovery}, labels, '%')}</div>
          <div class="card">{self.chart('Readiness Score Trends', {'Readiness Score': readiness}, readiness_labels, 'score')}</div>
          <div class="card">{self.chart('Session ROM and Accuracy', {'ROM': rom, 'Accuracy': acc}, labels, 'value')}</div>
        </section>
        """
        return Page("Progress Analytics", body, "analytics")

    def adaptive_ai(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        prescriptions = self.repo.adaptive_history(patient, limit=40)
        metrics = self.repo.research_metrics(patient)
        override_stats = self.repo.override_stats(patient)
        overrides = self.repo.override_history(patient, limit=20)
        upper_rows = list(reversed(self.repo.upper_limb_history(patient, limit=16)))
        upper_labels = [short_date(row["created_at"]) for row in upper_rows]
        compensation_series = [number(row["compensation_score"]) * 100.0 for row in upper_rows]
        efficiency_series = [number(row["movement_efficiency"]) for row in upper_rows]
        current = prescriptions[0] if prescriptions else None
        current_panel = ""
        if current:
            current_panel = f"""
            <section class="card" style="margin-top:16px">
              <h2>AI Prescription Panel</h2>
              <p class="muted">Decision Source: Adaptive AI Rehabilitation Engine</p>
            </section>
            <section class="grid three" style="margin-top:16px">
              {self.stat_card('Current Difficulty Tier', str(int(number(current['difficulty_tier']))), esc(exercise_for_level(current['level'])))}
              {self.stat_card('Readiness Score', f"{number(current['readiness_score']):.0f}/100", f"Recovery: {esc(current['recovery_trend'])}")}
              {self.stat_card('Risk Level', str(current['risk_level']).title(), 'Safety decision from engine')}
              {self.stat_card('Target Size', f"{number(current['target_scale']):.2f}x", f"Speed {number(current['speed_scale']):.2f}x")}
              {self.stat_card('ROM Requirement', f"{number(current['required_rom']):.0f} deg", f"Tolerance {number(current['rotation_tolerance']):.0f} deg")}
              {self.stat_card('Repetitions / Hold', f"{int(number(current['repetitions']))} reps", f"{number(current['hold_seconds']):.1f}s holds")}
              {self.stat_card('Progression Recommendation', str(current['progression']).title(), esc(current['override_recommendation']))}
              {self.stat_card('Guidance Level', str(current['guidance_level']).title(), f"{number(current['time_limit']):.0f}s time limit")}
              {self.stat_card('Adaptive Rationale', self.short_text(current['rationale'], 32), 'Explainable AI decision')}
            </section>
            """

        rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['created_at']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{number(row['readiness_score']):.0f}/100</td>
              <td>{int(number(row['difficulty_tier']))}</td>
              <td>{esc(str(row['progression']).title())}</td>
              <td>{esc(str(row['risk_level']).title())}</td>
              <td>{esc(row['recovery_trend'])}</td>
              <td>{number(row['ai_confidence_score']):.0f}%</td>
              <td>{number(row['recommendation_reliability']):.0f}%</td>
            </tr>
            """
            for row in prescriptions
        ) or '<tr><td colspan="10" class="muted">No adaptive prescriptions recorded.</td></tr>'

        decision_cards = "".join(
            f"""
            <div class="card alert {'danger' if row['risk_level'] == 'high' else 'warning' if row['risk_level'] == 'moderate' else ''}">
              <div class="toolbar"><h2>{esc(row['patient_id'])} · L{int(number(row['level']))}</h2><span class="badge">{number(row['readiness_score']):.0f}/100</span></div>
              <p class="muted">{esc(row['rationale'])}</p>
              <p><strong>Explainable AI:</strong> {esc(self.explainable_why(row))}</p>
              <p><strong>Override:</strong> {esc(row['override_recommendation'])}</p>
              {self.override_form(row)}
            </div>
            """
            for row in prescriptions[:6]
        ) or '<div class="card muted">Adaptive decisions will appear after completed sessions.</div>'
        override_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['created_at']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(row['therapist_id'])}</td>
              <td>{esc(str(row['decision']).title())}</td>
              <td>{esc(row['reason'])}</td>
              <td>{esc(row['therapist_reason'])}</td>
            </tr>
            """
            for row in overrides
        ) or '<tr><td colspan="6" class="muted">No therapist overrides recorded.</td></tr>'
        common_reasons = "".join(
            f'<span class="pill">{esc(reason)} · {count}</span>'
            for reason, count in override_stats["common_reasons"]
        ) or '<span class="pill">No override patterns yet</span>'

        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Adaptive AI Rehabilitation Engine</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        {current_panel}
        <section class="card" style="margin-top:16px">
          <h2>System Transparency</h2>
          <div class="toolbar" style="justify-content:flex-start">
            <span class="pill">Decision Source: Adaptive AI Engine</span>
            <span class="pill">Safety Logic: Rule-Based Logic</span>
            <span class="pill">Communication: Optional LLM Enhancement</span>
          </div>
        </section>
        <section class="grid three" style="margin-top:16px">
          {self.stat_card('Weekly ROM Gain', f"{metrics['weekly_rom_improvement']:+.1f} deg", 'Research endpoint')}
          {self.stat_card('Accuracy Change', f"{metrics['accuracy_improvement']:+.1f}%", 'Recent performance delta')}
          {self.stat_card('Pain-Adjusted Score', f"{metrics['pain_adjusted_performance']:.1f}", 'Accuracy weighted by pain')}
          {self.stat_card('Session Adherence', f"{metrics['session_adherence']:.0f}%", 'Consistency estimate')}
          {self.stat_card('Difficulty Progression', f"{metrics['difficulty_progression']:+.1f}", 'Tier movement')}
          {self.stat_card('Forearm Progress', f"{metrics['forearm_progress']:+.1f}", 'Smoothness minus compensation')}
          {self.stat_card('Compensation Frequency', f"{metrics['compensation_frequency']:.0f}%", 'Frames/sessions above threshold')}
          {self.stat_card('Shoulder / Elbow / Trunk', f"{metrics['shoulder_compensation']:.0f}% / {metrics['elbow_compensation']:.0f}% / {metrics['trunk_compensation']:.0f}%", 'Average compensation')}
          {self.stat_card('Movement Efficiency', f"{metrics['movement_efficiency']:.0f}%", 'Upper limb quality')}
        </section>
        <section class="grid three" style="margin-top:16px">
          {self.stat_card('AI Confidence', f"{override_stats['ai_confidence']:.0f}%", 'Learned from therapist decisions')}
          {self.stat_card('Override Probability', f"{override_stats['override_probability'] * 100:.0f}%", 'Human-in-the-loop estimate')}
          {self.stat_card('Recommendation Reliability', f"{override_stats['recommendation_reliability']:.0f}%", f"{override_stats['agreement_rate']:.0f}% agreement")}
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Most Common Override Reasons</h2>
          <div class="toolbar" style="justify-content:flex-start">{common_reasons}</div>
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('Biomechanical Compensation Trend', {'Compensation': compensation_series, 'Efficiency': efficiency_series}, upper_labels, '%')}</div>
          <div class="card">{self.chart('Adaptive Readiness Trend', {'Readiness': [number(row['readiness_score']) for row in reversed(prescriptions[-16:])]}, [short_date(row['created_at']) for row in reversed(prescriptions[-16:])], 'score')}</div>
        </section>
        <section class="grid two" style="margin-top:16px">{decision_cards}</section>
        <section class="card" style="margin-top:16px">
          <h2>Prescription History</h2>
          <table>
            <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Readiness</th><th>Tier</th><th>Decision</th><th>Risk</th><th>Recovery</th><th>AI Confidence</th><th>Reliability</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Override History</h2>
          <table>
            <thead><tr><th>Date</th><th>Patient</th><th>Therapist</th><th>Decision</th><th>Reason</th><th>Notes</th></tr></thead>
            <tbody>{override_rows}</tbody>
          </table>
        </section>
        """
        return Page("Adaptive AI", body, "adaptive")

    def explainable_why(self, row: sqlite3.Row) -> str:
        try:
            data = json.loads(row["explanation_json"] or "{}")
            if data.get("why"):
                return str(data["why"])
        except Exception:
            pass
        return row["rationale"]

    def override_form(self, row: sqlite3.Row) -> str:
        reasons = [
            "Patient Pain Too High",
            "Fatigue Detected",
            "Therapist Observed Compensation",
            "Patient Motivation Issues",
            "Clinical Safety Concern",
            "Progression Too Conservative",
            "Clinical judgement",
        ]
        reason_options = "".join(f"<option>{esc(reason)}</option>" for reason in reasons)
        return f"""
        <form method="post" action="/adaptive/override" class="form-grid">
          <input type="hidden" name="prescription_id" value="{int(number(row['id']))}">
          <label>Therapist<input name="therapist_id" value="Therapist"></label>
          <label>Decision<select name="decision"><option value="accept">Accept</option><option value="modify">Modify</option><option value="reject">Reject</option></select></label>
          <label>Reason<select name="reason">{reason_options}</select></label>
          <label>Difficulty Tier<input name="difficulty_tier" type="number" min="1" max="5" value="{int(number(row['difficulty_tier']))}"></label>
          <label>ROM Requirement<input name="required_rom" type="number" step="0.1" value="{number(row['required_rom']):.1f}"></label>
          <label>Repetitions<input name="repetitions" type="number" min="1" value="{int(number(row['repetitions']))}"></label>
          <label>Hold Duration<input name="hold_seconds" type="number" step="0.1" value="{number(row['hold_seconds']):.1f}"></label>
          <label>Progression<select name="progression">
            {self.option('advance', 'Advance', row['progression'])}
            {self.option('maintain', 'Maintain', row['progression'])}
            {self.option('support', 'Support', row['progression'])}
            {self.option('regress', 'Regress', row['progression'])}
          </select></label>
          <label class="full">Therapist Reason<textarea name="therapist_reason" placeholder="Clinical reasoning, observation, or safety note"></textarea></label>
          <button class="full">Store Therapist Decision</button>
        </form>
        """

    def digital_twin_page(self, params: dict[str, str]) -> Page:
        patients = self.repo.patients()
        selected = params.get("patient", "")
        if not selected and patients:
            selected = patients[0]["name"]
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in patients)
        if not selected:
            body = """
            <section class="card">
              <h2>Personalized Rehabilitation Digital Twin</h2>
              <p class="muted">Register a patient and complete sessions to generate a digital twin.</p>
            </section>
            """
            return Page("Digital Twin", body, "digital_twin")

        twin = self.repo.digital_twin_profile(selected)
        snapshots = list(reversed(self.repo.digital_twin_snapshots(selected, limit=16)))
        snap_labels = [short_date(row["created_at"]) for row in snapshots]
        readiness_series = [number(row["readiness_score"]) for row in snapshots]
        rom_series = [number(row["current_rom"]) for row in snapshots]
        risk_series = [number(row["stagnation_risk"]) for row in snapshots]

        scenario_cards = "".join(
            f"""
            <div class="card alert {'danger' if item.risk_level == 'High' else 'warning' if item.risk_level == 'Moderate' else ''}">
              <h2>{esc(item.name)} · {esc(item.strategy)}</h2>
              <div class="grid three">
                {self.stat_card('Timeline', f"{item.recovery_timeline_weeks:.1f} wk", 'To functional ROM target')}
                {self.stat_card('Expected ROM', f"{item.expected_rom:.1f} deg", '4-week forecast')}
                {self.stat_card('Expected Accuracy', f"{item.expected_accuracy:.1f}%", '4-week forecast')}
                {self.stat_card('Risk Level', item.risk_level, 'Scenario risk')}
                {self.stat_card('Fatigue Risk', f"{item.fatigue_risk:.0f}%", 'Load tolerance')}
                {self.stat_card('Compensation Risk', f"{item.compensation_risk:.0f}%", 'Movement quality')}
              </div>
              <p class="muted" style="margin-top:12px">{esc(item.explanation)}</p>
              <p><strong>Adherence:</strong> {esc(item.adherence_impact)}</p>
            </div>
            """
            for item in twin.scenarios
        )
        risk_cards = "".join(
            self.stat_card(label.replace("_", " ").title(), f"{value:.0f}%", "Predicted risk")
            for label, value in twin.risks.items()
        )
        milestones = "".join(f"<li>{esc(item)}</li>" for item in twin.milestones)
        exercise_mix = ", ".join(twin.recommendations.get("best_exercise_mix", []))
        weekly = twin.recommendations.get("weekly_targets", {})
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Personalized Rehabilitation Digital Twin</h2>
            <select name="patient">{patient_options}</select>
            <button>Build Twin</button>
          </form>
          <p class="muted">{esc(twin.explanation)}</p>
        </section>
        <section class="grid three" style="margin-top:16px">
          {self.stat_card('Current ROM', f"{twin.current_rom:.1f} deg", f"Velocity {twin.recovery_velocity:+.1f} deg/wk")}
          {self.stat_card('Current Accuracy', f"{twin.current_accuracy:.1f}%", f"Pain {twin.current_pain:.0f}/10")}
          {self.stat_card('Readiness', f"{twin.readiness_score:.0f}/100", f"Consistency {twin.consistency_score:.0f}%")}
          {self.stat_card('Fatigue', f"{twin.fatigue_index:.0f}%", 'Recent load estimate')}
          {self.stat_card('Compensation', f"{twin.compensation_score:.0f}%", 'Historical movement quality')}
          {self.stat_card('Forearm Quality', f"{twin.forearm_quality:.0f}%", 'Smoothness minus compensation')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('Digital Twin Snapshot Trend', {'Readiness': readiness_series, 'ROM': rom_series, 'Stagnation Risk': risk_series}, snap_labels, 'score')}</div>
          <div class="card">
            <h2>Personalized Recommendations</h2>
            <table>
              <tbody>
                <tr><th>Best Strategy</th><td>{esc(twin.recommendations.get('best_strategy', '-'))}</td></tr>
                <tr><th>Exercise Mix</th><td>{esc(exercise_mix)}</td></tr>
                <tr><th>Optimal Duration</th><td>{esc(twin.recommendations.get('optimal_session_duration', '-'))}</td></tr>
                <tr><th>Weekly Targets</th><td>{esc(json.dumps(weekly, sort_keys=True))}</td></tr>
                <tr><th>Progression Plan</th><td>{esc(twin.recommendations.get('difficulty_progression_plan', '-'))}</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="grid three" style="margin-top:16px">{risk_cards}</section>
        <section class="grid" style="margin-top:16px">{scenario_cards}</section>
        <section class="card" style="margin-top:16px">
          <h2>Milestone Predictions</h2>
          <ul>{milestones}</ul>
        </section>
        """
        return Page("Digital Twin", body, "digital_twin")

    def bucket_progress(self, sessions: list[sqlite3.Row], fmt: str) -> tuple[list[str], list[float]]:
        return self.bucket_metric(sessions, fmt, "avg_accuracy")

    def bucket_metric(self, sessions: list[sqlite3.Row], fmt: str, column: str) -> tuple[list[str], list[float]]:
        buckets: dict[str, list[float]] = {}
        for row in sessions:
            try:
                key = datetime.fromisoformat(str(row["timestamp"])).strftime(fmt)
            except ValueError:
                key = str(row["timestamp"])[:7]
            buckets.setdefault(key, []).append(number(row[column]))
        labels = list(buckets.keys())[-12:]
        values = [sum(buckets[label]) / len(buckets[label]) for label in labels]
        return labels, values

    def bucket_derived(self, sessions: list[sqlite3.Row], fmt: str, value_fn) -> tuple[list[str], list[float]]:
        buckets: dict[str, list[float]] = {}
        for row in sessions:
            try:
                key = datetime.fromisoformat(str(row["timestamp"])).strftime(fmt)
            except ValueError:
                key = str(row["timestamp"])[:7]
            buckets.setdefault(key, []).append(number(value_fn(row)))
        labels = list(buckets.keys())[-12:]
        values = [sum(buckets[label]) / len(buckets[label]) for label in labels]
        return labels, values

    def sensei_review(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        rows = self.repo.sensei_history(patient, limit=120)
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['created_at']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{esc(row_value(row, 'deterministic_message', row['message']))}</td>
              <td>{esc(row_value(row, 'llm_enhanced_message', ''))}</td>
              <td>{esc(row_value(row, 'coaching_trigger', self.sensei_trigger(row)))}</td>
              <td>{esc(row_value(row, 'decision_source', 'Adaptive AI Engine'))}</td>
              <td>{esc(row_value(row, 'llm_status', 'not_requested'))}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="8" class="muted">No Virtual Sensei messages recorded yet.</td></tr>'
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Virtual Sensei Review Panel</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
          <input id="senseiSearch" oninput="filterTable('senseiSearch','senseiTable')" placeholder="Search coaching messages">
          <table id="senseiTable" style="margin-top:12px">
            <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Generated Coaching Message</th><th>LLM Enhanced Message</th><th>Coaching Trigger</th><th>Decision Source</th><th>LLM Status</th></tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
        </section>
        """
        return Page("Virtual Sensei Review", body, "sensei")

    def sensei_trigger(self, row: sqlite3.Row) -> str:
        stored_trigger = row_value(row, "coaching_trigger", "")
        if stored_trigger:
            return str(stored_trigger)
        try:
            data = json.loads(row["context_json"] or "{}")
            for key in ("trigger", "reason", "why", "event"):
                if data.get(key):
                    return str(data[key])
            if data:
                return ", ".join(f"{k}: {v}" for k, v in list(data.items())[:2])
        except Exception:
            pass
        message = str(row["message"] or "").lower()
        if "improved" in message:
            return "Performance improvement detected"
        if "pain" in message:
            return "Pain score safety cue"
        if "smooth" in message or "rotation" in message:
            return "Movement quality coaching"
        return "Session performance feedback"

    def risks_page(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patients = [self.repo.patient(patient)] if patient and self.repo.patient(patient) else self.repo.patients()
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        cards: list[str] = []
        rows: list[str] = []
        for row in patients:
            if not row:
                continue
            risk_items = self.patient_risks(row)
            for label, severity, detail in risk_items:
                level_class = "danger" if severity == "High" else "warning" if severity == "Moderate" else ""
                cards.append(f'<div class="card alert {level_class}"><h2>{esc(label)}</h2><p><strong>{esc(row["name"])}</strong></p><p class="muted">{esc(detail)}</p><span class="badge">{esc(severity)}</span></div>')
                rows.append(f"<tr><td>{esc(row['name'])}</td><td>{esc(label)}</td><td>{esc(severity)}</td><td>{esc(detail)}</td><td>{esc(short_date(row['last_session']))}</td></tr>")
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Risk Detection Panel</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid three" style="margin-top:16px">{''.join(cards) or '<div class="card muted">No active rehabilitation risks detected.</div>'}</section>
        <section class="card" style="margin-top:16px">
          <h2>Risk Register</h2>
          <table>
            <thead><tr><th>Patient</th><th>Risk</th><th>Severity</th><th>Clinical Detail</th><th>Last Session</th></tr></thead>
            <tbody>{''.join(rows) or '<tr><td colspan="5" class="muted">No active risk items.</td></tr>'}</tbody>
          </table>
        </section>
        """
        return Page("Risk Detection", body, "risks")

    def patient_risks(self, patient: sqlite3.Row) -> list[tuple[str, str, str]]:
        name = patient["name"]
        sessions = self.repo.sessions_chrono(name)
        clinical = self.repo.clinical_intel.get_clinical_profile(name)
        upper = self.repo.latest_upper_limb_assessment(name)
        risks: list[tuple[str, str, str]] = []
        if sessions:
            recent = sessions[-3:]
            avg_pain = sum(number(row["pain_level"]) for row in recent) / len(recent)
            if avg_pain >= 6:
                risks.append(("High Pain Risk", "High", f"Recent average pain is {avg_pain:.1f}/10."))
            if len(recent) >= 3:
                rom_delta = number(recent[-1]["avg_hand_angle"]) - number(recent[0]["avg_hand_angle"])
                acc_delta = number(recent[-1]["avg_accuracy"]) - number(recent[0]["avg_accuracy"])
                if abs(rom_delta) < 2 and acc_delta <= 2:
                    risks.append(("Recovery Stagnation", "Moderate", "ROM and accuracy have not meaningfully improved over the last three sessions."))
                if fatigue_score(recent[-1]) >= 7:
                    risks.append(("Fatigue Risk", "High", f"Derived fatigue score is {fatigue_score(recent[-1]):.1f}/10."))
            try:
                last_dt = datetime.fromisoformat(str(sessions[-1]["timestamp"]))
                days_since = (datetime.now() - last_dt).days
                if days_since > 7:
                    risks.append(("Missed Sessions", "Moderate" if days_since <= 14 else "High", f"No session recorded for {days_since} days."))
            except ValueError:
                pass
        else:
            risks.append(("Missed Sessions", "Moderate", "Patient has no stored rehabilitation sessions."))
        if upper and number(upper["compensation_score"]) >= 0.45:
            risks.append(("Compensation Risk", "High", f"Latest compensation score is {number(upper['compensation_score']) * 100:.0f}%."))
        for detected in clinical["detected_risks"]:
            if not any(label == detected for label, _, _ in risks):
                risks.append((detected, "High" if detected in ("High Pain Risk", "Dropout Risk") else "Moderate", "Flagged by clinical intelligence layer."))
        return risks

    def reports(self, params: dict[str, str]) -> Page:
        selected = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in self.repo.patients())
        patient = self.repo.patient(selected) if selected else None
        summary = ""
        if patient:
            sessions = self.repo.sessions_chrono(selected)
            pred = recovery_prediction(sessions)
            summary = f"""
            <div class="grid three" style="margin-top:16px">
              {self.stat_card('Sessions', str(len(sessions)), selected)}
              {self.stat_card('Average Accuracy', f"{number(patient['avg_accuracy']):.1f}%", 'Exercise performance')}
              {self.stat_card('Average ROM', f"{number(patient['avg_rom']):.1f} deg", 'ROM analysis')}
            </div>
            <div class="card" style="margin-top:16px">
              <h2>Report Preview</h2>
              <p><strong>Patient:</strong> {esc(patient['name'])}</p>
              <p><strong>Injury:</strong> {esc(patient['injury_type'] or 'Not specified')}</p>
              <p><strong>Stage:</strong> {esc(patient['rehab_stage'] or 'Not specified')}</p>
              <p><strong>Recovery prediction:</strong> {f'{pred:.1f}%' if pred >= 0 else 'Need more data'}</p>
              <p><strong>Therapist observations:</strong> {esc(patient['therapist_notes'] or 'No profile observations recorded.')}</p>
              <div class="toolbar" style="justify-content:flex-start">
                <a class="button" href="/report.pdf?patient={quote(selected)}">Download PDF</a>
                <button type="button" class="button secondary" onclick="window.print()">Print Report</button>
              </div>
            </div>
            """
        body = f"""
        <section class="card">
          <h2>Recovery Reports</h2>
          <form method="get" class="toolbar">
            <select name="patient"><option value="">Select patient</option>{patient_options}</select>
            <button>Build Report</button>
          </form>
        </section>
        {summary}
        """
        return Page("Recovery Reports", body, "reports")

    def performance(self, params: dict[str, str]) -> Page:
        rows = self.repo.sessions()
        by_exercise: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            by_exercise.setdefault(exercise_for_level(row["level"]), []).append(row)
        perf_rows = []
        for exercise, items in by_exercise.items():
            attempts = len(items)
            correct = sum(1 for row in items if number(row["avg_accuracy"]) >= 60)
            incorrect = attempts - correct
            avg_accuracy = sum(number(row["avg_accuracy"]) for row in items) / attempts if attempts else 0
            time_spent = sum(number(row["duration"]) for row in items)
            perf_rows.append((exercise, attempts, correct, incorrect, avg_accuracy, time_spent))
        best = max(perf_rows, key=lambda item: item[4], default=None)
        weakest = min(perf_rows, key=lambda item: item[4], default=None)
        table = "".join(
            f"""
            <tr><td>{esc(ex)}</td><td>{done}</td><td>{correct}</td><td>{incorrect}</td><td>{acc:.1f}%</td><td>{time_spent/60:.1f} min</td></tr>
            """
            for ex, done, correct, incorrect, acc, time_spent in perf_rows
        ) or '<tr><td colspan="6" class="muted">No exercise data available.</td></tr>'
        body = f"""
        <section class="grid three">
          {self.stat_card('Best Exercise', best[0] if best else '-', f'{best[4]:.1f}% accuracy' if best else '')}
          {self.stat_card('Weakest Exercise', weakest[0] if weakest else '-', f'{weakest[4]:.1f}% accuracy' if weakest else '')}
          {self.stat_card('Exercises Completed', str(sum(item[1] for item in perf_rows)), 'Session-level completions')}
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Exercise Performance</h2>
          <table><thead><tr><th>Exercise</th><th>Completed</th><th>Correct</th><th>Incorrect</th><th>Accuracy</th><th>Time Spent</th></tr></thead><tbody>{table}</tbody></table>
        </section>
        """
        return Page("Exercise Performance", body, "performance")

    def notes(self, params: dict[str, str]) -> Page:
        selected = params.get("patient", "")
        selected_session = params.get("session_id", "")
        selected_date = params.get("date", "")
        patients = self.repo.patients()
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in patients)
        session_options = "".join(
            f'<option value="{row["id"]}" {"selected" if str(row["id"]) == selected_session else ""}>{esc(short_date(row["timestamp"]))} - {esc(exercise_for_level(row["level"]))}</option>'
            for row in self.repo.sessions(selected, limit=30)
        )
        notes = self.repo.notes(selected, selected_session, selected_date)
        note_rows = "".join(
            f"""
            <div class="card">
              <div class="toolbar"><strong>{esc(row['patient_name'])}</strong><span class="badge">{esc(row['therapist_name'])}</span></div>
              <p><strong>Clinical observation:</strong> {esc(row['clinical_observation'] or row['note'])}</p>
              <p>{esc(row['note'])}</p>
              <p class="muted"><strong>Recommendation:</strong> {esc(row['recommendation'] or '-')}</p>
              <p class="muted"><strong>Modified:</strong> {esc(short_date(row['modified_at']))}</p>
              <form method="post" action="/notes/save" class="form-grid">
                <input type="hidden" name="note_id" value="{int(number(row['id']))}">
                <input type="hidden" name="patient_name" value="{esc(row['patient_name'])}">
                <input type="hidden" name="session_id" value="{esc(row['session_id'] or '')}">
                <label>Therapist<input name="therapist_name" value="{esc(row['therapist_name'])}"></label>
                <label class="full">Edit note<textarea name="note" required>{esc(row['note'])}</textarea></label>
                <label class="full">Clinical observation<textarea name="clinical_observation">{esc(row['clinical_observation'])}</textarea></label>
                <label class="full">Recommendation<textarea name="recommendation">{esc(row['recommendation'])}</textarea></label>
                <button class="full">Update Note</button>
              </form>
              <span class="muted">Created {esc(short_date(row['created_at']))}</span>
            </div>
            """
            for row in notes
        ) or '<div class="card muted">No therapist notes recorded.</div>'
        body = f"""
        <section class="grid two">
          <div class="card">
            <h2>Therapist Notes</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <select name="session_id"><option value="">All sessions</option>{session_options}</select>
              <input name="date" type="date" value="{esc(selected_date)}">
              <button>Filter</button>
            </form>
            <form method="post" action="/notes/save" class="form-grid">
              <label>Patient<select name="patient_name" required><option value="">Select patient</option>{patient_options}</select></label>
              <label>Session<select name="session_id"><option value="">General note</option>{session_options}</select></label>
              <label>Therapist<input name="therapist_name" value="Therapist"></label>
              <label class="full">Note text<textarea name="note" required></textarea></label>
              <label class="full">Clinical observation<textarea name="clinical_observation"></textarea></label>
              <label class="full">Recommendation<textarea name="recommendation"></textarea></label>
              <button class="full">Add Note</button>
            </form>
          </div>
          <div class="grid">{note_rows}</div>
        </section>
        """
        return Page("Therapist Notes", body, "notes")

    def notifications(self) -> Page:
        body = f'<section class="grid two">{self.alert_cards(full=True)}</section>'
        return Page("Notifications", body, "notifications")

    def alert_cards(self, full: bool = False) -> str:
        alerts = self.alerts()
        if not alerts:
            alerts = [("No critical alerts", "All tracked sessions are within expected monitoring thresholds.", "")]
        return "".join(
            f'<div class="card alert {esc(level)}"><h2>{esc(title)}</h2><p class="muted">{esc(message)}</p></div>'
            for title, message, level in alerts[:12 if full else 4]
        )

    def alerts(self) -> list[tuple[str, str, str]]:
        alerts: list[tuple[str, str, str]] = []
        now = datetime.now()
        for patient in self.repo.patients():
            name = patient["name"]
            sessions = self.repo.sessions_chrono(name)
            if not sessions:
                alerts.append((f"{name}: no completed sessions", "Patient is registered but has no stored rehabilitation session.", "warning"))
                continue
            last = sessions[-1]
            try:
                last_dt = datetime.fromisoformat(str(last["timestamp"]))
                if now - last_dt > timedelta(days=7):
                    alerts.append((f"{name}: missed therapy", f"Last session was on {short_date(last['timestamp'])}.", "warning"))
            except ValueError:
                pass
            if number(last["pain_level"]) >= 7:
                alerts.append((f"{name}: high pain score", f"Latest pain score is {int(number(last['pain_level']))}/10.", "danger"))
            if number(last["avg_accuracy"]) < 50:
                alerts.append((f"{name}: low exercise accuracy", f"Latest accuracy is {number(last['avg_accuracy']):.1f}%.", "danger"))
            adaptive = self.repo.latest_adaptive_prescription(name)
            if adaptive:
                if str(adaptive["risk_level"]).lower() == "high":
                    alerts.append((f"{name}: adaptive high risk", esc(adaptive["override_recommendation"]), "danger"))
                elif number(adaptive["readiness_score"]) < 45:
                    alerts.append((f"{name}: low readiness score", f"Readiness is {number(adaptive['readiness_score']):.0f}/100.", "warning"))
            upper_limb = self.repo.latest_upper_limb_assessment(name)
            if upper_limb and number(upper_limb["compensation_score"]) >= 0.55:
                alerts.append((f"{name}: compensation detected", str(upper_limb["feedback"]), "warning"))
            if len(sessions) >= 2:
                delta = number(sessions[-1]["avg_hand_angle"]) - number(sessions[-2]["avg_hand_angle"])
                if delta >= 10:
                    alerts.append((f"{name}: significant improvement", f"ROM improved by {delta:.1f} degrees since the previous session.", ""))
                elif delta < -8:
                    alerts.append((f"{name}: slow recovery risk", f"ROM decreased by {abs(delta):.1f} degrees since the previous session.", "warning"))
        return alerts

    def report_chart_image(self, sessions: list[sqlite3.Row]) -> io.BytesIO:
        labels = [short_date(row["timestamp"]) for row in sessions[-10:]]
        rom = [number(row["avg_hand_angle"]) for row in sessions[-10:]]
        acc = [number(row["avg_accuracy"]) for row in sessions[-10:]]
        pain_before = [number(row_value(row, "pain_before_session", row["pain_level"])) for row in sessions[-10:]]
        pain_after = [number(row_value(row, "pain_after_session", row["pain_level"])) for row in sessions[-10:]]
        recovery_scores = [calculated_functional_recovery_score(row) for row in sessions[-10:]]
        fig, ax = plt.subplots(figsize=(7.2, 3.1), dpi=120)
        ax.plot(labels, rom, marker="o", linewidth=2, label="ROM")
        ax.plot(labels, acc, marker="o", linewidth=2, label="Accuracy")
        ax.plot(labels, pain_before, marker="o", linewidth=2, label="Pain Before")
        ax.plot(labels, pain_after, marker="o", linewidth=2, label="Pain After")
        ax.plot(labels, recovery_scores, marker="o", linewidth=2, label="Recovery Score")
        ax.set_title("ROM, Accuracy, Pain, and Recovery Trend", loc="left", fontsize=11, fontweight="bold")
        ax.grid(True, color="#dbe7f0")
        ax.tick_params(axis="x", labelrotation=20, labelsize=7)
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        image = io.BytesIO()
        fig.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    def report_pdf(self, patient_name: str) -> bytes:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
        except Exception as exc:
            return f"PDF export requires reportlab. Import error: {exc}".encode("utf-8")

        patient = self.repo.patient(patient_name)
        sessions = self.repo.sessions_chrono(patient_name)
        notes = self.repo.notes(patient_name)
        adaptive = self.repo.latest_adaptive_prescription(patient_name)
        metrics = self.repo.research_metrics(patient_name)
        clinical = self.repo.clinical_intel.get_clinical_profile(patient_name) if patient_name else None
        sensei = self.repo.sensei_history(patient_name, limit=8)
        pred = recovery_prediction(sessions)
        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        y = height - 50
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(50, y, "AI Hand Rehabilitation - Therapist Report")
        y -= 32
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, f"Generated: {datetime.now().strftime('%d %B %Y %H:%M')}")
        y -= 26
        if patient:
            fields = [
                ("Patient", patient["name"]),
                ("Age", patient["age"] or "-"),
                ("Gender", patient["gender"] or "-"),
                ("Injury Type", patient["injury_type"] or "-"),
                ("Rehabilitation Stage", patient["rehab_stage"] or "-"),
                ("Assigned Exercises", patient["assigned_exercises"] or "-"),
            ]
            for label, value in fields:
                pdf.drawString(50, y, f"{label}: {value}")
                y -= 16
        y -= 8
        avg_acc = sum(number(s["avg_accuracy"]) for s in sessions) / len(sessions) if sessions else 0
        avg_rom = sum(number(s["avg_hand_angle"]) for s in sessions) / len(sessions) if sessions else 0
        max_rom = max([number(s["avg_hand_angle"]) for s in sessions], default=0)
        avg_pain = sum(number(s["pain_level"]) for s in sessions) / len(sessions) if sessions else 0
        readiness = number(adaptive["readiness_score"]) if adaptive else number(clinical["health_score"] if clinical else 0)
        latest_session = sessions[-1] if sessions else None
        pain_before = number(row_value(latest_session, "pain_before_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_after = number(row_value(latest_session, "pain_after_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_difference = number(row_value(latest_session, "pain_difference", 0)) if latest_session else 0
        pain_trend = sum(number(row_value(row, "pain_difference", 0)) for row in sessions) / len(sessions) if sessions else 0
        recovery_score_value = calculated_functional_recovery_score(latest_session) if latest_session else 0
        recovery_category_value = recovery_category(recovery_score_value) if latest_session else "Not started"
        recovery_trend = (
            calculated_functional_recovery_score(sessions[-1]) - calculated_functional_recovery_score(sessions[0])
            if len(sessions) >= 2
            else 0.0
        )
        summary = [
            f"Completed Sessions: {len(sessions)}",
            f"Average Accuracy: {avg_acc:.1f}%",
            f"Average ROM: {avg_rom:.1f} degrees",
            f"Maximum ROM Achieved: {max_rom:.1f} degrees",
            f"Average Pain Score: {avg_pain:.1f}/10",
            f"Pain Before Latest Session: {pain_before:.0f}/10",
            f"Pain After Latest Session: {pain_after:.0f}/10",
            f"Pain Difference Latest Session: {pain_difference:+.0f}",
            f"Pain Improvement Trend: {pain_trend:+.1f} average after-before",
            f"Functional Recovery Score: {recovery_score_value:.0f}/100",
            f"Recovery Category: {recovery_category_value}",
            f"Recovery Progress Trend: {recovery_trend:+.1f} points",
            f"Readiness Score: {readiness:.0f}/100",
            f"Current Recovery Stage: {clinical['recovery_stage'] if clinical else 'Unknown'}",
            f"Recovery Prediction: {pred:.1f}%" if pred >= 0 else "Recovery Prediction: Need more data",
        ]
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Session Summary")
        y -= 18
        pdf.setFont("Helvetica", 10)
        for line in summary:
            pdf.drawString(60, y, line)
            y -= 15
        if adaptive:
            y -= 8
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(50, y, "Adaptive AI Prescription")
            y -= 18
            pdf.setFont("Helvetica", 9)
            adaptive_lines = [
                f"Readiness Score: {number(adaptive['readiness_score']):.0f}/100",
                f"Difficulty Tier: {int(number(adaptive['difficulty_tier']))}",
                f"AI Prescription: {int(number(adaptive['repetitions']))} reps, {number(adaptive['required_rom']):.0f} deg ROM, {number(adaptive['hold_seconds']):.1f}s holds",
                f"Risk Level: {adaptive['risk_level']}",
                f"Recovery Trend: {adaptive['recovery_trend']}",
                f"Progression Recommendation: {adaptive['progression']}",
                f"Adaptive Rationale: {adaptive['rationale']}",
                f"Override Recommendation: {adaptive['override_recommendation']}",
            ]
            for line in adaptive_lines:
                pdf.drawString(60, y, str(line)[:110])
                y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Research Metrics")
        y -= 18
        pdf.setFont("Helvetica", 9)
        research_lines = [
            f"Weekly ROM Improvement: {metrics['weekly_rom_improvement']:+.1f} degrees",
            f"Accuracy Improvement: {metrics['accuracy_improvement']:+.1f}%",
            f"Pain-Adjusted Performance: {metrics['pain_adjusted_performance']:.1f}",
            f"Session Adherence: {metrics['session_adherence']:.0f}%",
            f"Difficulty Progression: {metrics['difficulty_progression']:+.1f}",
            f"Forearm Progress: {metrics['forearm_progress']:+.1f}",
            f"Compensation Frequency: {metrics['compensation_frequency']:.0f}%",
            f"Shoulder / Elbow / Trunk Compensation: {metrics['shoulder_compensation']:.0f}% / {metrics['elbow_compensation']:.0f}% / {metrics['trunk_compensation']:.0f}%",
            f"Movement Efficiency: {metrics['movement_efficiency']:.0f}%",
        ]
        for line in research_lines:
            pdf.drawString(60, y, line)
            y -= 13
        if sessions:
            if y < 310:
                pdf.showPage()
                y = height - 50
            y -= 10
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(50, y, "Progress Charts")
            y -= 200
            chart = ImageReader(self.report_chart_image(sessions))
            pdf.drawImage(chart, 50, y, width=500, height=180, preserveAspectRatio=True, mask="auto")
            y -= 20
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Recent Sessions")
        y -= 18
        pdf.setFont("Helvetica", 9)
        for row in sessions[-10:]:
            if y < 80:
                pdf.showPage()
                y = height - 50
            line = (
                f"{short_date(row['timestamp'])} | {exercise_for_level(row['level'])} | "
                f"Acc {number(row['avg_accuracy']):.1f}% | ROM {number(row['avg_hand_angle']):.1f} | "
                f"Pain {int(number(row_value(row, 'pain_before_session', row['pain_level'])))}/10 to "
                f"{int(number(row_value(row, 'pain_after_session', row['pain_level'])))} /10 | "
                f"Recovery {calculated_functional_recovery_score(row):.0f}/100"
            )
            pdf.drawString(60, y, line[:110])
            y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Virtual Sensei Summary")
        y -= 18
        pdf.setFont("Helvetica", 9)
        sensei_lines = [f"{short_date(row['created_at'])}: {row['message']}" for row in sensei] or ["No Virtual Sensei messages recorded."]
        for line in sensei_lines:
            if y < 80:
                pdf.showPage()
                y = height - 50
            pdf.drawString(60, y, str(line)[:110])
            y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Therapist Observations")
        y -= 18
        pdf.setFont("Helvetica", 9)
        observation_lines = [
            f"{n['therapist_name']}: {n['note']} Recommendation: {n['recommendation'] or '-'}"
            for n in notes[:6]
        ] or ["No therapist notes recorded."]
        for line in observation_lines:
            for chunk in [line[i:i + 95] for i in range(0, len(line), 95)]:
                if y < 80:
                    pdf.showPage()
                    y = height - 50
                pdf.drawString(60, y, chunk)
                y -= 13
        pdf.save()
        return buf.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    repo = DashboardRepository(DB_PATH)
    renderer = DashboardRenderer(repo)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        path = parsed.path.rstrip("/") or "/"
        if path == "/report.pdf":
            patient = params.get("patient", "")
            data = self.renderer.report_pdf(patient)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="rehab_report_{quote(patient or "patient")}.pdf"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        page_map = {
            "/": self.renderer.home,
            "/patients": lambda: self.renderer.patients(params),
            "/sessions": lambda: self.renderer.sessions_page(params),
            "/analytics": lambda: self.renderer.analytics(params),
            "/adaptive": lambda: self.renderer.adaptive_ai(params),
            "/sensei": lambda: self.renderer.sensei_review(params),
            "/risks": lambda: self.renderer.risks_page(params),
            "/digital-twin": lambda: self.renderer.digital_twin_page(params),
            "/reports": lambda: self.renderer.reports(params),
            "/performance": lambda: self.renderer.performance(params),
            "/notes": lambda: self.renderer.notes(params),
            "/notifications": self.renderer.notifications,
        }
        page_factory = page_map.get(path)
        if not page_factory:
            self.send_error(HTTPStatus.NOT_FOUND, "Page not found")
            return
        body = self.renderer.layout(page_factory(), params)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8")
        form = {key: values[-1] for key, values in parse_qs(data).items()}
        path = urlparse(self.path).path
        if path == "/patients/save":
            self.repo.save_patient(form)
            self.redirect(f"/patients?patient={quote(form.get('name', ''))}")
        elif path == "/patients/delete":
            self.repo.delete_patient(form.get("name", ""))
            self.redirect("/patients")
        elif path == "/notes/save":
            self.repo.save_note(form)
            patient = form.get("patient_name", "")
            self.redirect(f"/notes?patient={quote(patient)}")
        elif path == "/adaptive/override":
            self.repo.save_override(form)
            self.redirect("/adaptive")
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Action not found")

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()


def run_server(host: str = HOST, port: int = PORT, open_browser: bool = True) -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    url = f"http://{host}:{port}"
    print("=" * 64)
    print("AI Hand Rehabilitation - Therapist Dashboard")
    print("=" * 64)
    print(f"Dashboard URL: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    chosen_port = PORT
    if len(sys.argv) > 1:
        try:
            chosen_port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port=chosen_port)
