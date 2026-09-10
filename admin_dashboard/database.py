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
import security_utils
import secrets



from admin_dashboard.config import *
from admin_dashboard.utils import *

class DecryptedRow:
    def __init__(self, row: sqlite3.Row, decrypt_fn: Any):
        self._data = dict(row)
        self._keys = list(row.keys()) if hasattr(row, 'keys') else list(self._data.keys())
        decrypt_fn(self._data)


    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def keys(self) -> list[str]:
        return self._keys

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

def decrypt_row_fields(d: dict[str, Any]) -> None:
    # Deterministic decryption for names and identifiers
    for k in ['name', 'patient_id', 'patient_name', 'id_number', 'username']:
        if k in d and d[k]:
            d[k] = security_utils.decrypt_deterministic(d[k])

    # Non-deterministic decryption for PII/notes/summaries
    for k in ['gender', 'injury_type', 'rehab_stage', 'assigned_exercises', 'therapist_notes',
              'note', 'recommendation', 'next_plan', 'note_text', 'clinical_observation',
              'ai_recommendation_json', 'modified_recommendation_json', 'patient_context_json',
              'summary_text', 'ai_recommendation']:
        if k in d and d[k]:
            d[k] = security_utils.decrypt_non_deterministic(d[k])


@dataclass

class DashboardRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.digital_twin = DigitalTwinRehabModel(db_path)
        self.clinical_intel = ClinicalIntelligenceLayer(db_path)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except sqlite3.OperationalError:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            # Create therapists and audit_logs tables
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS therapists (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT,
                    username TEXT,
                    role TEXT,
                    action TEXT,
                    target TEXT,
                    ip_address TEXT,
                    status TEXT
                )
                """
            )
            
            # Insert default therapist user if empty
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM therapists")
            if cursor.fetchone()[0] == 0:
                default_hash = security_utils.hash_password("Admin1234!")
                # Store username deterministically (or plaintext since username is not sensitive PII)
                # Wait, the prompt says "user_id / username / role / target". We can keep username as plaintext or encrypted.
                # Username in therapists table is better kept in plaintext so we can query it easily.
                cursor.execute(
                    "INSERT INTO therapists (username, password_hash) VALUES (?, ?)",
                    ("admin", default_hash)
                )
                conn.commit()

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

            # Ensure new tables exist
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compensation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    exercise TEXT,
                    compensation_type TEXT,
                    severity REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS clinical_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    session_id INTEGER UNIQUE,
                    movement_quality REAL,
                    rom_improvement REAL,
                    grip_accuracy REAL,
                    compensation_events INTEGER,
                    pain_before INTEGER,
                    pain_after INTEGER,
                    recovery_trend TEXT,
                    ai_recommendation TEXT,
                    summary_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Sessions column migrations
            for col, defn in [("movement_quality_score", "REAL DEFAULT 0"),
                              ("sub_smoothness", "REAL DEFAULT 0"),
                              ("sub_accuracy", "REAL DEFAULT 0"),
                              ("sub_rom", "REAL DEFAULT 0"),
                              ("sub_stability", "REAL DEFAULT 0"),
                              ("successful_hits", "INTEGER DEFAULT 0"),
                              ("total_attempts", "INTEGER DEFAULT 0"),
                              ("accuracy_type", "TEXT DEFAULT 'hit_rate'"),
                              ("exercise_name", "TEXT DEFAULT ''"),
                              ("session_number", "INTEGER DEFAULT 0"),
                              ("tracking_quality", "REAL DEFAULT NULL"),
                              ("tracking_frames_valid", "INTEGER DEFAULT 0"),
                              ("tracking_frames_total", "INTEGER DEFAULT 0"),
                              ("session_aborted", "INTEGER DEFAULT 0"),
                              ("quality_flag", "TEXT DEFAULT 'VALID'")]:
                try:
                    conn.execute(f"SELECT {col} FROM sessions LIMIT 1")
                except sqlite3.OperationalError:
                    try:
                        conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {defn}")
                    except Exception:
                        pass

            conn.commit()

    def verify_therapist(self, username: str, password: str) -> bool:
        """Verifies therapist credentials using bcrypt."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT password_hash FROM therapists WHERE username = ?",
                (username,)
            ).fetchone()
            if row:
                stored_hash = row["password_hash"]
                return security_utils.verify_password(stored_hash, password)
        return False

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[Any]:
        with self.connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [DecryptedRow(row, decrypt_row_fields) for row in rows]


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

        # Encrypt PII fields
        enc_name = security_utils.encrypt_deterministic(name)
        enc_id = security_utils.encrypt_deterministic(id_number) if id_number else None
        enc_gender = security_utils.encrypt_non_deterministic(form.get("gender", "").strip())
        enc_injury = security_utils.encrypt_non_deterministic(form.get("injury_type", "").strip())
        enc_stage = security_utils.encrypt_non_deterministic(form.get("rehab_stage", "").strip())
        enc_exercises = security_utils.encrypt_non_deterministic(form.get("assigned_exercises", "").strip())
        enc_notes = security_utils.encrypt_non_deterministic(form.get("therapist_notes", "").strip())

        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO patients (name, age, age_group, id_number)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET age = excluded.age, age_group = excluded.age_group, id_number = excluded.id_number
                """,
                (enc_name, age_value, age_group, enc_id),
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
                (enc_name, enc_gender, enc_injury, enc_stage, enc_exercises, enc_notes),
            )
            conn.commit()

    def delete_patient(self, name: str) -> None:
        enc_name = security_utils.encrypt_deterministic(name)
        with self.connect() as conn:
            conn.execute("DELETE FROM patients WHERE name = ?", (enc_name,))
            conn.execute("DELETE FROM dashboard_patient_profiles WHERE patient_name = ?", (enc_name,))
            conn.execute("DELETE FROM dashboard_notes WHERE patient_name = ?", (enc_name,))
            conn.commit()

    def sessions(self, patient: str = "", limit: int | None = None) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            enc_patient = security_utils.encrypt_deterministic(patient)
            where = "WHERE patient_id = ?"
            params.append(enc_patient)
        sql = f"SELECT * FROM sessions {where} ORDER BY datetime(timestamp) DESC, id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return self.query(sql, params)

    def sessions_chrono(self, patient: str = "") -> list[sqlite3.Row]:
        rows = self.sessions(patient)
        return list(reversed(rows))

    def latest_adaptive_prescription(self, patient: str, level: int | None = None) -> sqlite3.Row | None:
        enc_patient = security_utils.encrypt_deterministic(patient)
        where = "WHERE patient_id = ?"
        params: list[Any] = [enc_patient]

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
        enc_patient = security_utils.encrypt_deterministic(patient)
        rows = self.query(
            """
            SELECT *
            FROM forearm_assessments
            WHERE patient_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (enc_patient,),
        )
        return rows[0] if rows else None

    def adaptive_history(self, patient: str = "", limit: int = 30) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            enc_patient = security_utils.encrypt_deterministic(patient)
            where = "WHERE patient_id = ?"
            params.append(enc_patient)
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
        
        # Encrypt patient name deterministically and JSON columns non-deterministically
        enc_patient = security_utils.encrypt_deterministic(row["patient_id"])
        enc_ai_rec = security_utils.encrypt_non_deterministic(json.dumps(ai_recommendation, sort_keys=True))
        enc_modified = security_utils.encrypt_non_deterministic(json.dumps(modified, sort_keys=True))
        enc_context = security_utils.encrypt_non_deterministic(json.dumps(patient_context, sort_keys=True))
        
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
                enc_patient,
                form.get("therapist_id", "Therapist").strip() or "Therapist",
                form.get("decision", "accept").strip(),
                form.get("reason", "Clinical judgement").strip(),
                form.get("therapist_reason", "").strip(),
                enc_ai_rec,
                enc_modified,
                enc_context,
                row["metrics_json"] or "{}",
            ),
        )

    def override_history(self, patient: str = "", limit: int = 50) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            enc_patient = security_utils.encrypt_deterministic(patient)
            where = "WHERE patient_id = ?"
            params.append(enc_patient)
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
            enc_patient = security_utils.encrypt_deterministic(patient)
            where = "WHERE patient_id = ?"
            params.append(enc_patient)
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
            enc_patient = security_utils.encrypt_deterministic(patient)
            where = "WHERE patient_id = ?"
            params.append(enc_patient)
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
            enc_patient = security_utils.encrypt_deterministic(patient)
            where = "WHERE patient_id = ?"
            params.append(enc_patient)
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

    def exercise_analytics_data(self, patient: str = "") -> list[dict]:
        conn = self.connect()
        cursor = conn.cursor()
        
        where_clause = ""
        params = []
        if patient:
            enc_patient = security_utils.encrypt_deterministic(patient)
            where_clause = "WHERE patient_id = ?"
            params.append(enc_patient)
            
        cursor.execute(f"""
            SELECT level, 
                   AVG(duration) as avg_duration,
                   AVG(sub_smoothness) as avg_smoothness,
                   AVG(sub_accuracy) as avg_accuracy,
                   AVG(sub_rom) as avg_rom,
                   COUNT(id) as completed_count
            FROM sessions
            {where_clause}
            GROUP BY level
        """, params)
        rows = cursor.fetchall()
        
        comp_counts = {}
        level_map = {
            "Flexibility Training": 1,
            "Strength Coordination": 2,
            "Fine Motor Pinch": 3,
            "Path Tracing Control": 4,
            "Grip Release Cycle": 5,
            "Cognitive Finger Taps": 6,
            "Forearm Rotation Orbit": 7,
            "Smart Functional Assembly": 8
        }
        
        if patient:
            cursor.execute("SELECT exercise, COUNT(*) as cnt FROM compensation_events WHERE patient_id = ? GROUP BY exercise", (enc_patient,))
        else:
            cursor.execute("SELECT exercise, COUNT(*) as cnt FROM compensation_events GROUP BY exercise")
            
        for r in cursor.fetchall():
            ex_name = r["exercise"]
            matched_lvl = None
            for name, lvl in level_map.items():
                if name.lower() in ex_name.lower() or ex_name.lower() in name.lower():
                    matched_lvl = lvl
                    break
            if matched_lvl is not None:
                comp_counts[matched_lvl] = comp_counts.get(matched_lvl, 0) + r["cnt"]
                
        improvements = {}
        for lvl in range(1, 10):
            if patient:
                cursor.execute("""
                    SELECT avg_accuracy FROM sessions 
                    WHERE patient_id = ? AND level = ? 
                    ORDER BY timestamp ASC
                """, (enc_patient, lvl))
            else:
                cursor.execute("""
                    SELECT avg_accuracy FROM sessions 
                    WHERE level = ? 
                    ORDER BY timestamp ASC
                """, (lvl,))
            lvl_sessions = [r[0] for r in cursor.fetchall()]
            if len(lvl_sessions) >= 2:
                first_3 = lvl_sessions[:3]
                last_3 = lvl_sessions[-3:]
                avg_first = sum(first_3) / len(first_3)
                avg_last = sum(last_3) / len(last_3)
                improvements[lvl] = avg_last - avg_first
            else:
                improvements[lvl] = 0.0
                
        conn.close()
        
        analytics_list = []
        for row in rows:
            lvl = row["level"]
            analytics_list.append({
                "level": lvl,
                "exercise_name": exercise_for_level(lvl),
                "avg_duration": row["avg_duration"],
                "avg_smoothness": row["avg_smoothness"] if row["avg_smoothness"] is not None else 75.0,
                "avg_accuracy": row["avg_accuracy"],
                "avg_rom": row["avg_rom"],
                "completed_count": row["completed_count"],
                "compensation_count": comp_counts.get(lvl, 0),
                "improvement_percentage": improvements.get(lvl, 0.0)
            })
            
        return analytics_list

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
            enc_patient = security_utils.encrypt_deterministic(patient)
            clauses.append("n.patient_id = ?")
            params.append(enc_patient)
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

        enc_patient = security_utils.encrypt_deterministic(patient)
        enc_note = security_utils.encrypt_non_deterministic(note)
        enc_recommendation = security_utils.encrypt_non_deterministic(form.get("recommendation", "").strip())
        enc_observation = security_utils.encrypt_non_deterministic(form.get("clinical_observation", form.get("next_plan", "")).strip())
        therapist_name = form.get("therapist_name", "Therapist").strip() or "Therapist"

        values = (
            enc_patient,
            int(session_id) if session_id.isdigit() else None,
            therapist_name,
            enc_note,
            enc_recommendation,
            enc_observation,
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


