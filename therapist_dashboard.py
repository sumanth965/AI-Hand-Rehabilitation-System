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
                COUNT(s.id) AS sessions_count,
                COALESCE(AVG(s.avg_accuracy), 0) AS avg_accuracy,
                COALESCE(AVG(s.avg_hand_angle), 0) AS avg_rom,
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
                COUNT(s.id) AS sessions_count,
                COALESCE(AVG(s.avg_accuracy), 0) AS avg_accuracy,
                COALESCE(AVG(s.avg_hand_angle), 0) AS avg_rom,
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

    def notes(self, patient: str = "") -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE n.patient_name = ?"
            params.append(patient)
        return self.query(
            f"""
            SELECT n.*, s.timestamp, s.level
            FROM dashboard_notes n
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
        self.execute(
            """
            INSERT INTO dashboard_notes
                (patient_name, session_id, note_type, note, recommendation, next_plan)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                patient,
                int(session_id) if session_id.isdigit() else None,
                form.get("note_type", "Observation").strip(),
                note,
                form.get("recommendation", "").strip(),
                form.get("next_plan", "").strip(),
            ),
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
        active = 0
        for row in sessions:
            try:
                if datetime.fromisoformat(str(row["timestamp"])) >= seven_days_ago:
                    active += 1
            except ValueError:
                pass
        return {
            "patients": len(patients),
            "active_sessions": active,
            "completed_sessions": len(sessions),
            "avg_recovery": sum(predictions) / len(predictions) if predictions else 0,
            "overall_accuracy": sum(number(r["avg_accuracy"]) for r in sessions) / len(sessions) if sessions else 0,
            "avg_rom": sum(number(r["avg_hand_angle"]) for r in sessions) / len(sessions) if sessions else 0,
            "therapy_hours": total_seconds / 3600.0,
        }


class DashboardRenderer:
    def __init__(self, repo: DashboardRepository):
        self.repo = repo

    def layout(self, page: Page, params: dict[str, str] | None = None) -> bytes:
        params = params or {}
        theme = params.get("theme", "light")
        nav = [
            ("home", "/", "Dashboard"),
            ("patients", "/patients", "Patients"),
            ("sessions", "/sessions", "Sessions"),
            ("analytics", "/analytics", "Analytics"),
            ("adaptive", "/adaptive", "Adaptive AI"),
            ("digital_twin", "/digital-twin", "Digital Twin"),
            ("reports", "/reports", "Reports"),
            ("performance", "/performance", "Performance"),
            ("notes", "/notes", "Notes"),
            ("notifications", "/notifications", "Alerts"),
        ]
        nav_html = "".join(
            f'<a class="nav-item {"active" if key == page.active else ""}" href="{href}">{label}</a>'
            for key, href, label in nav
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
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <div>
        <strong>Hand Rehab</strong>
        <span>Therapist Console</span>
      </div>
    </div>
    <nav>{nav_html}</nav>
    <a class="theme-toggle" href="?theme={toggled_theme}">{'Dark' if toggled_theme == 'dark' else 'Light'} mode</a>
  </aside>
  <main class="main">
    <header class="topbar">
      <div>
        <h1>{esc(page.title)}</h1>
        <p>Centralized rehabilitation monitoring for clinical review and decision support.</p>
      </div>
      <div class="date-chip">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</div>
    </header>
    {page.body}
  </main>
  <script>{self.js()}</script>
  {page.scripts}
</body>
</html>"""
        return html_doc.encode("utf-8")

    def css(self) -> str:
        return """
:root {
  --bg: #f5f8fc;
  --panel: #ffffff;
  --panel-2: #eef5fa;
  --text: #1c2735;
  --muted: #66778a;
  --line: #d2e0ec;
  --primary: #0077b6;
  --primary-2: #00a0a8;
  --success: #1da365;
  --warning: #dc8f14;
  --danger: #cc404a;
  --shadow: 0 14px 34px rgba(39, 64, 91, .10);
}
[data-theme="dark"] {
  --bg: #101820;
  --panel: #172432;
  --panel-2: #1d3040;
  --text: #ecf4fb;
  --muted: #a6b6c6;
  --line: #2b4256;
  --shadow: 0 18px 42px rgba(0, 0, 0, .28);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
}
a { color: inherit; text-decoration: none; }
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 250px;
  padding: 22px 16px;
  background: var(--panel);
  border-right: 1px solid var(--line);
}
.brand { display: flex; gap: 12px; align-items: center; margin-bottom: 28px; }
.brand-mark {
  width: 42px; height: 42px; border-radius: 8px;
  display: grid; place-items: center;
  color: white; background: linear-gradient(135deg, var(--primary), var(--primary-2));
  font-weight: 800;
}
.brand strong { display: block; }
.brand span, .topbar p, .muted { color: var(--muted); font-size: 13px; }
.nav-item, .theme-toggle {
  display: block;
  padding: 11px 12px;
  border-radius: 8px;
  margin: 4px 0;
  color: var(--muted);
}
.nav-item.active, .nav-item:hover, .theme-toggle:hover {
  background: var(--panel-2);
  color: var(--primary);
}
.theme-toggle { position: absolute; bottom: 18px; left: 16px; right: 16px; }
.main { margin-left: 250px; padding: 26px; min-height: 100vh; }
.topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
  margin-bottom: 22px;
}
h1 { margin: 0 0 6px; font-size: 28px; letter-spacing: 0; }
h2 { margin: 0 0 14px; font-size: 19px; }
.date-chip, .pill {
  padding: 9px 12px;
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 8px;
  color: var(--muted);
}
.grid { display: grid; gap: 16px; }
.stats { grid-template-columns: repeat(4, minmax(160px, 1fr)); }
.two { grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr); }
.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  box-shadow: var(--shadow);
}
.stat-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.stat-value { margin-top: 8px; font-size: 30px; font-weight: 800; }
.stat-sub { margin-top: 6px; color: var(--muted); font-size: 13px; }
.toolbar {
  display: flex; gap: 10px; align-items: center; justify-content: space-between;
  margin-bottom: 14px; flex-wrap: wrap;
}
input, select, textarea {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--text);
  border-radius: 8px;
  padding: 10px 11px;
  font: inherit;
}
textarea { min-height: 96px; resize: vertical; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.full { grid-column: 1 / -1; }
button, .button {
  border: 0;
  border-radius: 8px;
  padding: 10px 13px;
  background: var(--primary);
  color: white;
  font-weight: 700;
  cursor: pointer;
}
.button.secondary { background: var(--panel-2); color: var(--primary); border: 1px solid var(--line); }
.button.danger, button.danger { background: var(--danger); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 11px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
tr:hover td { background: var(--panel-2); }
.progress { height: 9px; border-radius: 999px; background: var(--panel-2); overflow: hidden; }
.progress span { display: block; height: 100%; background: linear-gradient(90deg, var(--primary), var(--success)); }
.badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; background: var(--panel-2); color: var(--primary); }
.alert { border-left: 4px solid var(--primary); }
.alert.warning { border-left-color: var(--warning); }
.alert.danger { border-left-color: var(--danger); }
.chart { width: 100%; border-radius: 8px; border: 1px solid var(--line); background: white; }
.tabs { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.pagination { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
@media (max-width: 980px) {
  .sidebar { position: static; width: auto; }
  .theme-toggle { position: static; }
  .main { margin-left: 0; padding: 18px; }
  .stats, .two, .three, .form-grid { grid-template-columns: 1fr; }
  .topbar { align-items: flex-start; flex-direction: column; }
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
          {self.stat_card('Active Sessions', str(stats['active_sessions']), 'Sessions recorded in the last 7 days')}
          {self.stat_card('Completed Sessions', str(stats['completed_sessions']), 'All stored rehabilitation sessions')}
          {self.stat_card('Avg Recovery', f"{stats['avg_recovery']:.1f}%", 'Linear trend projection where available')}
          {self.stat_card('Overall Accuracy', f"{stats['overall_accuracy']:.1f}%", 'Average exercise success rate')}
          {self.stat_card('Average ROM', f"{stats['avg_rom']:.1f} deg", 'Mean recorded hand angle')}
          {self.stat_card('Therapy Hours', f"{stats['therapy_hours']:.1f}", 'Total guided session duration')}
          {self.stat_card('Profiles Reviewed', str(len(patients)), 'Available patient records')}
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
              <td><a href="/patients?patient={quote(row['name'])}"><strong>{esc(row['name'])}</strong></a><div class="muted">{esc(row['injury_type'] or 'No injury type set')}</div></td>
              <td>{esc(row['id_number'] or '-')}</td>
              <td>{esc(row['age'] or '-')}</td>
              <td>{esc(row['gender'] or '-')}</td>
              <td>{esc(row['rehab_stage'] or '-')}</td>
              <td>{int(row['sessions_count'])}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_rom']):.1f} deg</td>
              <td>{esc(short_date(row['last_session']))}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="8" class="muted">No matching patients.</td></tr>'
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
              <thead><tr><th onclick="sortTable('patientsTable',0)">Name</th><th>ID Number</th><th>Age</th><th>Gender</th><th>Stage</th><th>Sessions</th><th>Accuracy</th><th>ROM</th><th>Last Visit</th></tr></thead>
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
        adaptive = self.repo.latest_adaptive_prescription(row["name"])
        forearm = self.repo.latest_forearm_assessment(row["name"])
        upper_limb = self.repo.latest_upper_limb_assessment(row["name"])
        history = "".join(
            f"<tr><td>{esc(short_date(s['timestamp']))}</td><td>{esc(exercise_for_level(s['level']))}</td><td>{number(s['avg_accuracy']):.1f}%</td><td>{number(s['avg_hand_angle']):.1f} deg</td><td>{esc(format_duration(s['duration']))}</td></tr>"
            for s in sessions
        ) or '<tr><td colspan="5" class="muted">No rehabilitation history yet.</td></tr>'
        if adaptive:
            adaptive_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Adaptive AI Recommendation</h2>
              <div class="grid three">
                {self.stat_card('Readiness Score', f"{number(adaptive['readiness_score']):.0f}/100", f"{adaptive['progression'].title()} progression")}
                {self.stat_card('Risk Level', adaptive['risk_level'].title(), f"Recovery: {adaptive['recovery_trend']}")}
                {self.stat_card('Next Time Limit', f"{number(adaptive['time_limit']):.0f}s", f"Target scale {number(adaptive['target_scale']):.2f}")}
              </div>
              <p class="muted" style="margin-top:12px">{esc(adaptive['rationale'])}</p>
              <p><strong>Override recommendation:</strong> {esc(adaptive['override_recommendation'])}</p>
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
        return f"""
        <div>
          {self.patient_form(row)}
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
          {forearm_panel}
          {upper_limb_panel}
        </div>
        """

    def option(self, value: str, label: str, selected: str) -> str:
        return f'<option value="{esc(value)}" {"selected" if value == selected else ""}>{esc(label)}</option>'

    def sessions_page(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        rows = self.repo.sessions(patient)
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
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
              <td>{int(number(row['pain_level']))}/10</td>
              <td>{esc(tremor_rating_for_sessions(self.repo.sessions_chrono(row['patient_id'])))}</td>
              <td>{int(number(row['score']))}</td>
              <td>{self.prediction_badge(row['patient_id'])}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="11" class="muted">No sessions found.</td></tr>'
        body = f"""
        <section class="card">
          <div class="toolbar">
            <h2>Session History</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <button>Filter</button>
            </form>
          </div>
          <input id="sessionSearch" oninput="filterTable('sessionSearch','sessionsTable')" placeholder="Search session table">
          <table id="sessionsTable" style="margin-top:12px">
            <thead><tr>
              <th onclick="sortTable('sessionsTable',0)">Date</th><th>Patient</th><th>Exercise</th><th>Duration</th><th>Max ROM</th><th>Avg ROM</th><th>Accuracy</th><th>Pain</th><th>Tremor</th><th>Score</th><th>Recovery</th>
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
        completion = [1 if number(row["avg_accuracy"]) >= 60 else 0 for row in sessions[-16:]]
        weekly = self.bucket_progress(sessions, "%Y-W%W")
        monthly = self.bucket_progress(sessions, "%Y-%m")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Progress Analytics</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('ROM Improvement', {'Average ROM': rom}, labels, 'degrees')}</div>
          <div class="card">{self.chart('Accuracy Trend', {'Accuracy': acc}, labels, '%')}</div>
          <div class="card">{self.chart('Pain Level Trend', {'Pain': pain}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Exercise Completion Rate', {'Completed': completion}, labels, 'completed')}</div>
          <div class="card">{self.chart('Weekly Progress', {'Weekly Accuracy': weekly[1]}, weekly[0], '%')}</div>
          <div class="card">{self.chart('Monthly Progress', {'Monthly Accuracy': monthly[1]}, monthly[0], '%')}</div>
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
        buckets: dict[str, list[float]] = {}
        for row in sessions:
            try:
                key = datetime.fromisoformat(str(row["timestamp"])).strftime(fmt)
            except ValueError:
                key = str(row["timestamp"])[:7]
            buckets.setdefault(key, []).append(number(row["avg_accuracy"]))
        labels = list(buckets.keys())[-12:]
        values = [sum(buckets[label]) / len(buckets[label]) for label in labels]
        return labels, values

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
              <a class="button" href="/report.pdf?patient={quote(selected)}">Download PDF Report</a>
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
        patients = self.repo.patients()
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in patients)
        session_options = "".join(
            f'<option value="{row["id"]}">{esc(short_date(row["timestamp"]))} - {esc(exercise_for_level(row["level"]))}</option>'
            for row in self.repo.sessions(selected, limit=30)
        )
        note_rows = "".join(
            f"""
            <div class="card">
              <div class="toolbar"><strong>{esc(row['patient_name'])}</strong><span class="badge">{esc(row['note_type'])}</span></div>
              <p>{esc(row['note'])}</p>
              <p class="muted"><strong>Recommendation:</strong> {esc(row['recommendation'] or '-')}</p>
              <p class="muted"><strong>Next plan:</strong> {esc(row['next_plan'] or '-')}</p>
              <span class="muted">{esc(short_date(row['created_at']))}</span>
            </div>
            """
            for row in self.repo.notes(selected)
        ) or '<div class="card muted">No therapist notes recorded.</div>'
        body = f"""
        <section class="grid two">
          <div class="card">
            <h2>Therapist Notes</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <button>Filter</button>
            </form>
            <form method="post" action="/notes/save" class="form-grid">
              <label>Patient<select name="patient_name" required><option value="">Select patient</option>{patient_options}</select></label>
              <label>Session<select name="session_id"><option value="">General note</option>{session_options}</select></label>
              <label>Type<select name="note_type"><option>Observation</option><option>Recommendation</option><option>Next Session Plan</option><option>Risk Note</option></select></label>
              <label class="full">Observation<textarea name="note" required></textarea></label>
              <label class="full">Recommendation<textarea name="recommendation"></textarea></label>
              <label class="full">Next rehabilitation session plan<textarea name="next_plan"></textarea></label>
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

    def report_pdf(self, patient_name: str) -> bytes:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except Exception as exc:
            return f"PDF export requires reportlab. Import error: {exc}".encode("utf-8")

        patient = self.repo.patient(patient_name)
        sessions = self.repo.sessions_chrono(patient_name)
        notes = self.repo.notes(patient_name)
        adaptive = self.repo.latest_adaptive_prescription(patient_name)
        metrics = self.repo.research_metrics(patient_name)
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
        summary = [
            f"Completed Sessions: {len(sessions)}",
            f"Average Accuracy: {avg_acc:.1f}%",
            f"Average ROM: {avg_rom:.1f} degrees",
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
                f"Risk Level: {adaptive['risk_level']}",
                f"Recovery Trend: {adaptive['recovery_trend']}",
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
                f"Pain {int(number(row['pain_level']))}/10"
            )
            pdf.drawString(60, y, line[:110])
            y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Therapist Observations")
        y -= 18
        pdf.setFont("Helvetica", 9)
        observation_lines = [n["note"] for n in notes[:6]] or ["No therapist notes recorded."]
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
