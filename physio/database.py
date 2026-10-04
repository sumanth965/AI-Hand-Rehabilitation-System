"""
Database Manager for the Zero-Keyboard AI Physiotherapy System.
Handles all SQLite operations for session storage and analytics.
"""

from __future__ import annotations

import sqlite3
import numpy as np
import pygame
import io
import security_utils
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class DatabaseManager:
    """Analytics database"""
    
    def __init__(self, db_path="rehab_data.db"):
        self.db_path = db_path
        self.last_session_id = None
        self._init_database()
    
    def _init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT DEFAULT 'Unknown',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    level INTEGER,
                    score INTEGER,
                    duration REAL,
                    avg_accuracy REAL,
                    max_finger_extension REAL,
                    reach_distance REAL,
                    avg_hand_angle REAL DEFAULT 0,
                    pain_level INTEGER DEFAULT 0,
                    pain_before_session INTEGER DEFAULT 0,
                    pain_after_session INTEGER DEFAULT 0,
                    pain_difference INTEGER DEFAULT 0,
                    functional_recovery_score REAL DEFAULT 0,
                    recovery_category TEXT DEFAULT 'Not recorded',
                    movement_smoothness REAL DEFAULT 0,
                    successful_hits INTEGER DEFAULT 0,
                    total_attempts INTEGER DEFAULT 0,
                    accuracy_type TEXT DEFAULT 'hit_rate',
                    exercise_name TEXT DEFAULT '',
                    session_number INTEGER DEFAULT 0,
                    tracking_quality REAL DEFAULT NULL,
                    tracking_frames_valid INTEGER DEFAULT 0,
                    tracking_frames_total INTEGER DEFAULT 0,
                    session_aborted INTEGER DEFAULT 0,
                    quality_flag TEXT DEFAULT 'VALID',
                    active_engagement_duration REAL DEFAULT 0,
                    tracking_valid_duration REAL DEFAULT 0,
                    difficulty_tier INTEGER DEFAULT 3,
                    target_scale REAL DEFAULT 1.0,
                    speed_scale REAL DEFAULT 1.0,
                    session_time_limit REAL DEFAULT 30.0,
                    hold_duration REAL DEFAULT 1.5,
                    rotation_tolerance REAL DEFAULT 25.0,
                    assembly_position_tolerance REAL DEFAULT 50.0,
                    corridor_width REAL DEFAULT 60.0,
                    index_successes INTEGER DEFAULT 0,
                    middle_successes INTEGER DEFAULT 0,
                    ring_successes INTEGER DEFAULT 0,
                    pinky_successes INTEGER DEFAULT 0,
                    index_attempts INTEGER DEFAULT 0,
                    middle_attempts INTEGER DEFAULT 0,
                    ring_attempts INTEGER DEFAULT 0,
                    pinky_attempts INTEGER DEFAULT 0,
                    unintended_movement_events INTEGER DEFAULT 0,
                    target_activation_time_avg REAL DEFAULT 0.0,
                    dwell_success_count INTEGER DEFAULT 0,
                    dwell_failure_count INTEGER DEFAULT 0,
                    average_movement_time REAL DEFAULT 0.0,
                    average_target_error REAL DEFAULT 0.0,
                    average_overshoot REAL DEFAULT 0.0,
                    average_hold_stability REAL DEFAULT 0.0,
                    direction_accuracy REAL DEFAULT 0.0,
                    card_shift_successes INTEGER DEFAULT 0,
                    card_shift_attempts INTEGER DEFAULT 0,
                    average_shift_latency REAL DEFAULT 0.0,
                    median_shift_latency REAL DEFAULT 0.0,
                    maximum_shift_latency REAL DEFAULT 0.0,
                    incorrect_finger_events INTEGER DEFAULT 0,
                    target_timeouts INTEGER DEFAULT 0,
                    sequence_completion_rate REAL DEFAULT 0.0
                )
            """)
            cursor.execute("""
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
            cursor.execute("""
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
            cursor.execute("""
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
            # Migrations for older DBs
            for col, defn in [("level",          "INTEGER DEFAULT 1"),
                              ("score",          "INTEGER DEFAULT 0"),
                              ("duration",       "REAL DEFAULT 0"),
                              ("avg_accuracy",   "REAL DEFAULT 0"),
                              ("max_finger_extension", "REAL DEFAULT 0"),
                              ("reach_distance", "REAL DEFAULT 0"),
                              ("patient_id",     "TEXT DEFAULT 'Unknown'"),
                              ("avg_hand_angle", "REAL DEFAULT 0"),
                              ("pain_level",     "INTEGER DEFAULT 0"),
                              ("pain_before_session", "INTEGER DEFAULT 0"),
                              ("pain_after_session", "INTEGER DEFAULT 0"),
                              ("pain_difference", "INTEGER DEFAULT 0"),
                              ("functional_recovery_score", "REAL DEFAULT 0"),
                              ("recovery_category", "TEXT DEFAULT 'Not recorded'"),
                              ("movement_smoothness", "REAL DEFAULT 0"),
                              ("movement_quality_score", "REAL DEFAULT 0"),
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
                              ("quality_flag", "TEXT DEFAULT 'VALID'"),
                              ("active_engagement_duration", "REAL DEFAULT 0"),
                              ("tracking_valid_duration", "REAL DEFAULT 0"),
                              ("difficulty_tier", "INTEGER DEFAULT 3"),
                              ("target_scale", "REAL DEFAULT 1.0"),
                              ("speed_scale", "REAL DEFAULT 1.0"),
                              ("session_time_limit", "REAL DEFAULT 30.0"),
                              ("hold_duration", "REAL DEFAULT 1.5"),
                              ("rotation_tolerance", "REAL DEFAULT 25.0"),
                              ("assembly_position_tolerance", "REAL DEFAULT 50.0"),
                              ("corridor_width", "REAL DEFAULT 60.0"),
                              ("successful_pickups", "INTEGER DEFAULT 0"),
                              ("pickup_attempts", "INTEGER DEFAULT 0"),
                              ("successful_translations", "INTEGER DEFAULT 0"),
                              ("translation_attempts", "INTEGER DEFAULT 0"),
                              ("successful_placements", "INTEGER DEFAULT 0"),
                              ("placement_attempts", "INTEGER DEFAULT 0"),
                              ("unintended_drops", "INTEGER DEFAULT 0"),
                              ("manipulation_time_avg", "REAL DEFAULT 0.0"),
                              ("placement_time_avg", "REAL DEFAULT 0.0"),
                              ("correction_count", "INTEGER DEFAULT 0"),
                              ("d2_contacts", "INTEGER DEFAULT 0"),
                              ("d3_contacts", "INTEGER DEFAULT 0"),
                              ("d4_contacts", "INTEGER DEFAULT 0"),
                              ("d5_contacts", "INTEGER DEFAULT 0"),
                              ("opposition_latency_avg", "REAL DEFAULT 0.0"),
                              ("index_successes", "INTEGER DEFAULT 0"),
                              ("middle_successes", "INTEGER DEFAULT 0"),
                              ("ring_successes", "INTEGER DEFAULT 0"),
                              ("pinky_successes", "INTEGER DEFAULT 0"),
                              ("index_attempts", "INTEGER DEFAULT 0"),
                              ("middle_attempts", "INTEGER DEFAULT 0"),
                              ("ring_attempts", "INTEGER DEFAULT 0"),
                              ("pinky_attempts", "INTEGER DEFAULT 0"),
                              ("unintended_movement_events", "INTEGER DEFAULT 0"),
                              ("target_activation_time_avg", "REAL DEFAULT 0.0"),
                              ("dwell_success_count", "INTEGER DEFAULT 0"),
                              ("dwell_failure_count", "INTEGER DEFAULT 0"),
                              ("average_movement_time", "REAL DEFAULT 0.0"),
                              ("average_target_error", "REAL DEFAULT 0.0"),
                              ("average_overshoot", "REAL DEFAULT 0.0"),
                              ("average_hold_stability", "REAL DEFAULT 0.0"),
                              ("direction_accuracy", "REAL DEFAULT 0.0"),
                              ("card_shift_successes", "INTEGER DEFAULT 0"),
                              ("card_shift_attempts", "INTEGER DEFAULT 0"),
                              ("average_shift_latency", "REAL DEFAULT 0.0"),
                              ("median_shift_latency", "REAL DEFAULT 0.0"),
                              ("maximum_shift_latency", "REAL DEFAULT 0.0"),
                              ("incorrect_finger_events", "INTEGER DEFAULT 0"),
                              ("target_timeouts", "INTEGER DEFAULT 0"),
                              ("sequence_completion_rate", "REAL DEFAULT 0.0")]:
                try:
                    cursor.execute(f"SELECT {col} FROM sessions LIMIT 1")
                except sqlite3.OperationalError:
                    try:
                        cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col} {defn}")
                    except Exception as e:
                        print(f"Migration error for sessions {col}: {e}")
                        
            # Patient migrations
            try:
                cursor.execute(f"SELECT id_number FROM patients LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    cursor.execute(f"ALTER TABLE patients ADD COLUMN id_number TEXT")
                    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_id_number ON patients(id_number)")
                except Exception as e:
                    print(f"Migration error for patients id_number: {e}")

            # Migrate any unencrypted patient rows to deterministic encryption and deduplicate
            try:
                cursor.execute("SELECT name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active, id_number FROM patients")
                p_rows = cursor.fetchall()
                for prow in p_rows:
                    raw_name = prow[0]
                    dec_name = security_utils.decrypt_deterministic(raw_name)
                    if dec_name == raw_name and raw_name:
                        enc_name = security_utils.encrypt_deterministic(raw_name)
                        cursor.execute("SELECT name FROM patients WHERE name = ?", (enc_name,))
                        existing = cursor.fetchone()
                        if existing:
                            cursor.execute(
                                """
                                UPDATE patients SET 
                                    age = COALESCE(age, ?),
                                    age_group = COALESCE(age_group, ?),
                                    id_number = COALESCE(id_number, ?)
                                WHERE name = ?
                                """,
                                (prow[1], prow[2], prow[8], enc_name)
                            )
                            cursor.execute("DELETE FROM patients WHERE name = ?", (raw_name,))
                        else:
                            cursor.execute("UPDATE patients SET name = ? WHERE name = ?", (enc_name, raw_name))
            except Exception:
                pass

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"CRITICAL: Database initialization failed: {e}")
            with open("db_error.txt", "a") as f:
                f.write(f"{datetime.now()} - Init Error: {e}\n")

    def save_patient(self, name: str, age: int, age_group: str,
                     cal_fist_val: float = 0.12, cal_max_ext: float = 170.0,
                     cal_min_ang: float = 15.0, cal_max_ang: float = 90.0,
                     cal_active: int = 0, id_number: str = None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            enc_name = security_utils.encrypt_deterministic(name)
            
            # If id_number is not provided but exists in db, preserve it
            if id_number is None:
                cursor.execute("SELECT id_number FROM patients WHERE name = ?", (enc_name,))
                row = cursor.fetchone()
                if row:
                    id_number = row[0]
                else:
                    id_number = None
            else:
                id_number = security_utils.encrypt_deterministic(id_number)
                    
            cursor.execute("""
                INSERT OR REPLACE INTO patients 
                (name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active, id_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (enc_name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active, id_number))
            conn.commit()
            conn.close()
            print(f"[SUCCESS] Saved patient profile: {name} (Age {age}, Group {age_group})")
        except Exception as e:
            print(f"Failed to save patient profile: {e}")

    def get_patient(self, name: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            enc_name = security_utils.encrypt_deterministic(name)
            cursor.execute("""
                SELECT age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active
                FROM patients WHERE name = ?
            """, (enc_name,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    'age': row[0],
                    'age_group': row[1],
                    'cal_fist_val': row[2],
                    'cal_max_ext': row[3],
                    'cal_min_ang': row[4],
                    'cal_max_ang': row[5],
                    'cal_active': row[6]
                }
            return None
        except Exception as e:
            print(f"Failed to get patient: {e}")
            return None

    def get_patient_by_id(self, id_number: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            enc_id = security_utils.encrypt_deterministic(id_number)
            cursor.execute("""
                SELECT name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active
                FROM patients WHERE id_number = ?
            """, (enc_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                dec_name = security_utils.decrypt_deterministic(row[0])
                return {
                    'name': dec_name,
                    'age': row[1],
                    'age_group': row[2],
                    'cal_fist_val': row[3],
                    'cal_max_ext': row[4],
                    'cal_min_ang': row[5],
                    'cal_max_ang': row[6],
                    'cal_active': row[7]
                }
        except Exception as e:
            print(f"Error fetching patient by ID: {e}")
        return None

    def get_all_patients(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active, id_number
                FROM patients ORDER BY name ASC
            """)
            rows = cursor.fetchall()
            conn.close()
            res = []
            for row in rows:
                dec_name = security_utils.decrypt_deterministic(row[0])
                dec_id = security_utils.decrypt_deterministic(row[8]) if row[8] else None
                res.append({
                    'name': dec_name,
                    'age': row[1],
                    'age_group': row[2],
                    'cal_fist_val': row[3],
                    'cal_max_ext': row[4],
                    'cal_min_ang': row[5],
                    'cal_max_ang': row[6],
                    'cal_active': row[7],
                    'id_number': dec_id
                })
            return res
        except Exception as e:
            print(f"Failed to get all patients: {e}")
            return []
    
    def save_session(self, level: int, score: int, duration: float,
                    avg_accuracy: Optional[float], max_extension: float,
                    reach_distance: float = 0, avg_hand_angle: float = 0,
                    pain_level: int = 0, patient_id: str = "Unknown",
                    pain_before_session: int | None = None,
                    pain_after_session: int | None = None,
                    functional_recovery_score: float = 0.0,
                    recovery_category: str = "Not recorded",
                    movement_smoothness: float = 0.0,
                    movement_quality_score: float = 0.0,
                    sub_smoothness: float = 0.0,
                    sub_accuracy: float = 0.0,
                    sub_rom: float = 0.0,
                    sub_stability: float = 0.0,
                    successful_hits: int = 0,
                    total_attempts: int = 0,
                    accuracy_type: str = "hit_rate",
                    exercise_name: str = "",
                    session_number: int = 0,
                    tracking_quality: Optional[float] = None,
                    tracking_frames_valid: int = 0,
                    tracking_frames_total: int = 0,
                    session_aborted: int = 0,
                    quality_flag: str = "VALID",
                    active_engagement_duration: float = 0.0,
                    tracking_valid_duration: float = 0.0,
                    difficulty_tier: int = 3,
                    target_scale: float = 1.0,
                    speed_scale: float = 1.0,
                    session_time_limit: float = 30.0,
                    hold_duration: float = 1.5,
                    rotation_tolerance: float = 25.0,
                    assembly_position_tolerance: float = 50.0,
                    corridor_width: float = 60.0,
                    successful_pickups: int = 0,
                    pickup_attempts: int = 0,
                    successful_translations: int = 0,
                    translation_attempts: int = 0,
                    successful_placements: int = 0,
                    placement_attempts: int = 0,
                    unintended_drops: int = 0,
                    manipulation_time_avg: float = 0.0,
                    placement_time_avg: float = 0.0,
                    correction_count: int = 0,
                    d2_contacts: int = 0,
                    d3_contacts: int = 0,
                    d4_contacts: int = 0,
                    d5_contacts: int = 0,
                    opposition_latency_avg: float = 0.0,
                    index_successes: int = 0,
                    middle_successes: int = 0,
                    ring_successes: int = 0,
                    pinky_successes: int = 0,
                    index_attempts: int = 0,
                    middle_attempts: int = 0,
                    ring_attempts: int = 0,
                    pinky_attempts: int = 0,
                    unintended_movement_events: int = 0,
                    target_activation_time_avg: float = 0.0,
                    dwell_success_count: int = 0,
                    dwell_failure_count: int = 0,
                    average_movement_time: float = 0.0,
                    average_target_error: float = 0.0,
                    average_overshoot: float = 0.0,
                    average_hold_stability: float = 0.0,
                    direction_accuracy: float = 0.0,
                    card_shift_successes: int = 0,
                    card_shift_attempts: int = 0,
                    average_shift_latency: float = 0.0,
                    median_shift_latency: float = 0.0,
                    maximum_shift_latency: float = 0.0,
                    incorrect_finger_events: int = 0,
                    target_timeouts: int = 0,
                    sequence_completion_rate: float = 0.0):
        try:
            pain_before = int(pain_level if pain_before_session is None else pain_before_session)
            pain_after = int(pain_before if pain_after_session is None else pain_after_session)
            pain_difference = pain_after - pain_before
            
            enc_patient_id = security_utils.encrypt_deterministic(patient_id)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions
                  (patient_id, level, score, duration, avg_accuracy,
                   max_finger_extension, reach_distance, avg_hand_angle, pain_level,
                   pain_before_session, pain_after_session, pain_difference,
                   functional_recovery_score, recovery_category, movement_smoothness,
                   movement_quality_score, sub_smoothness, sub_accuracy, sub_rom, sub_stability,
                   successful_hits, total_attempts, accuracy_type, exercise_name,
                   session_number, tracking_quality, tracking_frames_valid, tracking_frames_total,
                   session_aborted, quality_flag, active_engagement_duration, tracking_valid_duration,
                   difficulty_tier, target_scale, speed_scale, session_time_limit,
                   hold_duration, rotation_tolerance, assembly_position_tolerance, corridor_width,
                   successful_pickups, pickup_attempts, successful_translations, translation_attempts,
                   successful_placements, placement_attempts, unintended_drops, manipulation_time_avg,
                   placement_time_avg, correction_count,
                   d2_contacts, d3_contacts, d4_contacts, d5_contacts, opposition_latency_avg,
                   index_successes, middle_successes, ring_successes, pinky_successes,
                   index_attempts, middle_attempts, ring_attempts, pinky_attempts,
                   unintended_movement_events, target_activation_time_avg, dwell_success_count, dwell_failure_count,
                   average_movement_time, average_target_error, average_overshoot, average_hold_stability, direction_accuracy,
                   card_shift_successes, card_shift_attempts, average_shift_latency, median_shift_latency,
                   maximum_shift_latency, incorrect_finger_events, target_timeouts, sequence_completion_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (enc_patient_id, level, score, duration, avg_accuracy,
                   max_extension, reach_distance, avg_hand_angle, pain_before,
                   pain_before, pain_after, pain_difference,
                   functional_recovery_score, recovery_category, movement_smoothness,
                   movement_quality_score, sub_smoothness, sub_accuracy, sub_rom, sub_stability,
                   successful_hits, total_attempts, accuracy_type, exercise_name,
                   session_number, tracking_quality, tracking_frames_valid, tracking_frames_total,
                   session_aborted, quality_flag, active_engagement_duration, tracking_valid_duration,
                   difficulty_tier, target_scale, speed_scale, session_time_limit,
                   hold_duration, rotation_tolerance, assembly_position_tolerance, corridor_width,
                   successful_pickups, pickup_attempts, successful_translations, translation_attempts,
                   successful_placements, placement_attempts, unintended_drops, manipulation_time_avg,
                   placement_time_avg, correction_count,
                   d2_contacts, d3_contacts, d4_contacts, d5_contacts, opposition_latency_avg,
                   index_successes, middle_successes, ring_successes, pinky_successes,
                   index_attempts, middle_attempts, ring_attempts, pinky_attempts,
                   unintended_movement_events, target_activation_time_avg, dwell_success_count, dwell_failure_count,
                   average_movement_time, average_target_error, average_overshoot, average_hold_stability, direction_accuracy,
                   card_shift_successes, card_shift_attempts, average_shift_latency, median_shift_latency,
                   maximum_shift_latency, incorrect_finger_events, target_timeouts, sequence_completion_rate))
            
            self.last_session_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            acc_str = f"{avg_accuracy:.1f}%" if avg_accuracy is not None else "N/A (No Valid Attempts)"
            print(f"[SUCCESS] Session saved: Level {level}, Score {score}, Accuracy {acc_str}, Type {accuracy_type}, Flag {quality_flag}")
        except Exception as e:
            import logging
            logging.basicConfig(filename='db_error.txt', level=logging.ERROR, 
                                format='%(asctime)s - Database Error: %(message)s')
            logging.error(f"Failed to save session (locked or missing db): {str(e)}")
            print("Database locked/missing! Logged error to db_error.txt instead of crashing.")
    
    def get_patient_session_count(self, patient_id: str) -> int:
        """Return the number of previous sessions recorded for a patient."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            enc_patient_id = security_utils.encrypt_deterministic(patient_id)
            cursor.execute("SELECT COUNT(*) FROM sessions WHERE patient_id = ?", (enc_patient_id,))
            row = cursor.fetchone()
            conn.close()
            return int(row[0]) if row else 0
        except Exception as e:
            print(f"Error fetching patient session count: {e}")
            return 0

    def get_last_session(self):
        """Get the most recent session data"""
        if self.last_session_id is None:
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT level, score, duration, avg_accuracy, max_finger_extension, reach_distance, avg_hand_angle,
                   movement_quality_score, sub_smoothness, sub_accuracy, sub_rom, sub_stability
            FROM sessions
            WHERE id = ?
        """, (self.last_session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'level': result[0],
                'score': result[1],
                'duration': result[2],
                'avg_accuracy': result[3],
                'max_extension': result[4],
                'reach_distance': result[5],
                'avg_hand_angle': result[6],
                'movement_quality_score': result[7],
                'sub_smoothness': result[8],
                'sub_accuracy': result[9],
                'sub_rom': result[10],
                'sub_stability': result[11]
            }
        return None
    
    def get_all_time_best(self):
        """Get all-time best performance metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(score) FROM sessions")
            best_score = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(avg_accuracy) FROM sessions")
            best_accuracy = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(avg_hand_angle) FROM sessions")
            best_angle = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(max_finger_extension) FROM sessions")
            best_extension = cursor.fetchone()[0] or 0
            conn.close()
            return {
                'score': best_score,
                'accuracy': best_accuracy,
                'angle': best_angle,
                'extension': best_extension
            }
        except Exception as e:
            print(f"Failed to pull all-time best: {e}")
            return {
                'score': 0,
                'accuracy': 0,
                'angle': 0,
                'extension': 0
            }

    def get_recent_sessions(self, limit: int = 6, patient_id: str = None):
        """Return last N sessions ordered oldest→newest for progress chart"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if patient_id:
                enc_id = security_utils.encrypt_deterministic(patient_id)
                cursor.execute("""
                    SELECT level, avg_accuracy, avg_hand_angle, score,
                           strftime('%d/%m', timestamp) as date
                    FROM sessions 
                    WHERE patient_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (enc_id, limit))
            else:
                cursor.execute("""
                    SELECT level, avg_accuracy, avg_hand_angle, score,
                           strftime('%d/%m', timestamp) as date
                    FROM sessions ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return list(reversed(rows))
        except Exception as e:
            print(f"Failed to pull recent sessions: {e}")
            return []

    def get_session_history(self, limit: int = 20, patient_id: str = None):
        """Full session list for the History screen (newest first)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if patient_id:
                enc_id = security_utils.encrypt_deterministic(patient_id)
                cursor.execute("""
                    SELECT id,
                           strftime('%d/%m/%Y %H:%M', timestamp) as dt,
                           level, score, avg_accuracy, avg_hand_angle,
                           duration, pain_level
                    FROM sessions 
                    WHERE patient_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (enc_id, limit))
            else:
                cursor.execute("""
                    SELECT id,
                           strftime('%d/%m/%Y %H:%M', timestamp) as dt,
                           level, score, avg_accuracy, avg_hand_angle,
                           duration, pain_level
                    FROM sessions ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f"Failed to pull session history: {e}")
            return []

    def get_rom_trend(self, limit: int = 10, patient_id: str = None):
        """ROM angle per session newest→oldest, for trend line chart"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if patient_id:
                enc_id = security_utils.encrypt_deterministic(patient_id)
                cursor.execute("""
                    SELECT avg_hand_angle, strftime('%d/%m', timestamp)
                    FROM sessions 
                    WHERE patient_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (enc_id, limit))
            else:
                cursor.execute("""
                    SELECT avg_hand_angle, strftime('%d/%m', timestamp)
                    FROM sessions ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return list(reversed(rows))
        except Exception as e:
            print(f"Failed to pull ROM trend: {e}")
            return []

    def predict_recovery_progress(self, patient_id: str = None) -> float:
        """
        Longitudinal recovery trend estimation over subsequent sessions based on historical data.
        The system estimates longitudinal recovery trends from historical session metrics using
        the implemented computational model; this should not be interpreted as a clinical prognosis.
        """
        try:
            sessions = self.get_session_history(20, patient_id=patient_id)
            if len(sessions) < 3: return -1.0
            
            # Use max_finger_extension or avg_hand_angle for trend
            # session format: (id, dt, level, score, acc, rom, dur, pain)
            x = np.array(range(len(sessions))).reshape(-1, 1)
            y = np.array([float(s[5]) for s in sessions]) # ROM
            
            from sklearn.linear_model import LinearRegression
            model = LinearRegression().fit(x, y)
            
            future_x = np.array([[len(sessions) + 7]])
            prediction = model.predict(future_x)[0]
            
            current_avg = np.mean(y)
            improvement = ((prediction - current_avg) / current_avg * 100) if current_avg != 0 else 0
            return max(0, improvement)
        except Exception as e:
            print(f"Prediction error: {e}")
            return -1.0

    def clear_all_history(self):
        """Purge all session records from database"""
        try:
            import sqlite3
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions")
                conn.commit()
            print("Database history purged.")
        except Exception as e:
            print(f"Purge error: {e}")

    def render_matplotlib_dashboard(self, patient_id: str = None) -> pygame.Surface:
        try:
            rom_data = self.get_rom_trend(15, patient_id=patient_id) 
            sessions = self.get_session_history(15, patient_id=patient_id)
            
            if not rom_data or not sessions:
                surf = pygame.Surface((660, 560))
                surf.fill((8, 12, 22))
                # Render placeholders
                font = pygame.font.SysFont("segoeui", 20)
                lbl = font.render("AWAITING PATIENT DATA FOR CLINICAL DASHBOARD", True, (0, 180, 255))
                surf.blit(lbl, lbl.get_rect(center=(330, 280)))
                return surf
                
            # Create a 2x1 vertical layout with exact size 6.6x5.6 to match container aspect ratio perfectly
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.6, 5.6), dpi=100)
            fig.patch.set_facecolor('#080c16')
            
            rom_chrono = list(reversed(rom_data))
            angles = [r[0] or 0 for r in rom_chrono]
            dates = [r[1] or "" for r in rom_chrono] 
            
            # High-visibility neon green trend line with white nodes
            ax1.plot(dates, angles, marker='o', markersize=6, color='#00f0ff', linewidth=3, 
                     markerfacecolor='#32ff96', markeredgecolor='#080c16')
            ax1.set_facecolor('#0f172a')
            ax1.set_title("Flexion ROM Trend (deg)", color='#00f0ff', fontsize=11, fontweight='bold', pad=8)
            ax1.tick_params(colors='#ffffff', labelsize=9)
            ax1.tick_params(axis='x', rotation=15)
            ax1.grid(color='#1e293b', linestyle=':', linewidth=0.8)
            ax1.spines['bottom'].set_color('#1e293b')
            ax1.spines['top'].set_color('#1e293b')
            ax1.spines['left'].set_color('#1e293b')
            ax1.spines['right'].set_color('#1e293b')
            
            sess_chrono = list(reversed(sessions))
            durations = [s[6] or 0 for s in sess_chrono] # Duration in seconds
            sdates = [(s[1] or "")[:6] for s in sess_chrono]
            
            # High-visibility sky blue bars with neon green borders
            ax2.bar(sdates, durations, color='#0088ff', edgecolor='#32ff96', linewidth=1.5, alpha=0.9)
            ax2.set_facecolor('#0f172a')
            ax2.set_title("Rehab Session Consistency", color='#00f0ff', fontsize=11, fontweight='bold', pad=8)
            ax2.tick_params(colors='#ffffff', labelsize=9)
            ax2.tick_params(axis='x', rotation=15)
            ax2.grid(color='#1e293b', linestyle=':', linewidth=0.8)
            ax2.spines['bottom'].set_color('#1e293b')
            ax2.spines['top'].set_color('#1e293b')
            ax2.spines['left'].set_color('#1e293b')
            ax2.spines['right'].set_color('#1e293b')
            
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', facecolor='#080c16')
            buf.seek(0)
            plt.close(fig)
            return pygame.image.load(buf, 'png')
        except Exception as e:
            print(f"Matplotlib dashboard error: {e}")
            surf = pygame.Surface((660, 560))
            surf.fill((8, 12, 22))
            return surf


# =====================================================================
# RESEARCH VALIDATION UTILITIES
# =====================================================================

def validate_accuracy(hits: int, attempts: int) -> tuple[Optional[float], str]:
    """
    Standardize research accuracy calculation:
    IF total_attempts > 0:
        accuracy = hits / attempts * 100 (clamped 0-100)
    ELSE:
        accuracy = None, quality_flag = 'NO_VALID_ATTEMPTS'
        
    Returns:
        (accuracy_or_none, quality_flag)
    """
    if attempts < 0 or hits < 0 or hits > attempts:
        return None, "ACCURACY_ERROR"
    if attempts == 0:
        return None, "NO_VALID_ATTEMPTS"
    accuracy = round(min(100.0, max(0.0, (hits / attempts) * 100.0)), 2)
    return accuracy, "VALID"


def validate_session_data(session_dict: dict) -> tuple[bool, str]:
    """
    Validates a session dictionary against research constraints.
    Distinguishes between computer vision tracking failure, patient motor failure,
    session abort, and valid session outcomes.
    Returns (is_valid_for_research, quality_flag).
    """
    attempts = session_dict.get("total_attempts", 0)
    hits = session_dict.get("successful_hits", 0)
    acc = session_dict.get("avg_accuracy")
    tracking_quality = session_dict.get("tracking_quality")
    tracking_frames_total = session_dict.get("tracking_frames_total", 0)
    tracking_frames_valid = session_dict.get("tracking_frames_valid", 0)
    aborted = session_dict.get("session_aborted", 0)

    if aborted:
        return False, "ABORTED_SESSION"

    if tracking_quality is not None and tracking_quality < 50.0:
        return False, "TRACKING_ERROR"

    if tracking_quality is None and (tracking_frames_total == 0 or tracking_frames_valid == 0):
        return False, "MISSING_DATA"

    if attempts < 0 or hits < 0 or hits > attempts:
        return False, "ACCURACY_ERROR"

    if acc is not None and (acc < 0.0 or acc > 100.0):
        return False, "ACCURACY_ERROR"

    if attempts == 0:
        return False, "NO_VALID_ATTEMPTS"

    if hits == 0 and attempts > 0:
        return True, "MOTOR_FAILURE"

    return True, "VALID"


