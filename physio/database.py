"""
Database Manager for the Zero-Keyboard AI Physiotherapy System.
Handles all SQLite operations for session storage and analytics.
"""

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
                    movement_smoothness REAL DEFAULT 0
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
                              ("sub_stability", "REAL DEFAULT 0")]:
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
                    avg_accuracy: float, max_extension: float,
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
                    sub_stability: float = 0.0):
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
                   movement_quality_score, sub_smoothness, sub_accuracy, sub_rom, sub_stability)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (enc_patient_id, level, score, duration, avg_accuracy,
                   max_extension, reach_distance, avg_hand_angle, pain_before,
                   pain_before, pain_after, pain_difference,
                   functional_recovery_score, recovery_category, movement_smoothness,
                   movement_quality_score, sub_smoothness, sub_accuracy, sub_rom, sub_stability))
            
            self.last_session_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] Session saved: Level {level}, Score {score}, Accuracy {avg_accuracy:.1f}%")
        except Exception as e:
            import logging
            logging.basicConfig(filename='db_error.txt', level=logging.ERROR, 
                                format='%(asctime)s - Database Error: %(message)s')
            logging.error(f"Failed to save session (locked or missing db): {str(e)}")
            print("Database locked/missing! Logged error to db_error.txt instead of crashing.")
    
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
        """Predict recovery percentage over next 7 days based on recent data."""
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
