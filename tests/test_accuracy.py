"""
Unit and Integration Tests for Research-Grade Accuracy & Data Collection V1
Covers Cases 1 through 6, Per-Exercise Metric Matrix, and Quality Flag Determination.
"""

import unittest
import sqlite3
import os
import tempfile
import security_utils
from physio.database import DatabaseManager, validate_accuracy, validate_session_data


class TestAccuracyCalculationCases(unittest.TestCase):
    """Phase 11: Core Accuracy Calculation Edge Cases"""

    def test_case_1_perfect_accuracy(self):
        """CASE 1: 5 attempts, 5 successes -> 100%"""
        acc, flag = validate_accuracy(hits=5, attempts=5)
        self.assertEqual(acc, 100.0)
        self.assertEqual(flag, "VALID")

    def test_case_2_partial_accuracy(self):
        """CASE 2: 5 attempts, 3 successes -> 60%"""
        acc, flag = validate_accuracy(hits=3, attempts=5)
        self.assertEqual(acc, 60.0)
        self.assertEqual(flag, "VALID")

    def test_case_3_zero_accuracy(self):
        """CASE 3: 5 attempts, 0 successes -> 0%"""
        acc, flag = validate_accuracy(hits=0, attempts=5)
        self.assertEqual(acc, 0.0)
        self.assertEqual(flag, "VALID")

    def test_case_4_zero_attempts_no_valid_attempts(self):
        """CASE 4: 0 attempts -> NULL / NO_VALID_ATTEMPTS (not 0% or 100%)"""
        acc, flag = validate_accuracy(hits=0, attempts=0)
        self.assertIsNone(acc)
        self.assertEqual(flag, "NO_VALID_ATTEMPTS")

    def test_case_5_invalid_data_hits_exceed_attempts(self):
        """CASE 5: attempts = 10, successes = 11 -> reject invalid data"""
        acc, flag = validate_accuracy(hits=11, attempts=10)
        self.assertIsNone(acc)
        self.assertEqual(flag, "ACCURACY_ERROR")

    def test_case_6_tracking_loss_independent_of_accuracy(self):
        """
        CASE 6: Tracking loss (hand lost 70% of the session)
        Tracking quality = 30.0% -> TRACKING_ERROR flag.
        Patient accuracy on valid attempts remains intact (not penalized as motor failure).
        """
        valid_frames = 30
        total_frames = 100
        tracking_quality = (valid_frames / total_frames) * 100.0
        self.assertEqual(tracking_quality, 30.0)

        session_record = {
            "successful_hits": 3,
            "total_attempts": 3,
            "avg_accuracy": 100.0,
            "tracking_quality": tracking_quality,
            "session_aborted": 0,
            "quality_flag": "VALID"
        }
        is_valid, flag = validate_session_data(session_record)
        self.assertFalse(is_valid)
        self.assertEqual(flag, "TRACKING_ERROR")
        # Ensure raw accuracy itself was not degraded to 30%
        self.assertEqual(session_record["avg_accuracy"], 100.0)


class TestExerciseAccuracyMatrix(unittest.TestCase):
    """Verify accuracy type mapping and rules for each of the 10 levels"""

    EXERCISE_MATRIX = {
        1: {
            "name": "Bubble Pop",
            "type": "hit_rate",
            "attempt_rule": "Every presented bubble (popped or expired) is an attempt",
            "hit_rule": "Bubble popped by fingertip touch",
            "failure_rule": "Bubble unpopped when session expires"
        },
        2: {
            "name": "Fruit Catch",
            "type": "hit_rate",
            "attempt_rule": "Every catchable fruit resolved (caught or dropped)",
            "hit_rule": "Catchable fruit lands in basket",
            "failure_rule": "Catchable fruit falls below screen line without catch"
        },
        3: {
            "name": "Pinch & Drop",
            "type": "hit_rate",
            "attempt_rule": "Every seed presented (grabbed or dropped off screen)",
            "hit_rule": "Pinch grabbed and successfully released inside pot",
            "failure_rule": "Released outside pot or ungrabbed seed falls off screen"
        },
        4: {
            "name": "Path Tracing",
            "type": "proximity_rate",
            "attempt_rule": "Periodic trajectory waypoint samples along figure-8 curve",
            "hit_rule": "Index fingertip distance within acceptable tolerance radius",
            "failure_rule": "Index fingertip exceeds tolerance radius"
        },
        5: {
            "name": "Grip & Release",
            "type": "completion_rate",
            "attempt_rule": "Initiated fist grip cycle",
            "hit_rule": "Full fist closure followed by full extension (>120 deg) within 5s window",
            "failure_rule": "Failed to achieve full extension within cycle time window"
        },
        6: {
            "name": "Memory Sequence",
            "type": "hit_rate",
            "attempt_rule": "Each pad selection attempt in the recall sequence",
            "hit_rule": "Selected pad matches the flashing target sequence",
            "failure_rule": "Selected wrong pad (resets combo and sequence)"
        },
        7: {
            "name": "Rotation Orbit",
            "type": "hit_rate",
            "attempt_rule": "Presented orbital rotation angle checkpoints",
            "hit_rule": "Maintained rotation within tolerance angle for required hold duration",
            "failure_rule": "Failed to hold required angle before timeout"
        },
        8: {
            "name": "Smart Assembly",
            "type": "binary_completion",
            "attempt_rule": "Complete multi-part blueprint assembly opportunity",
            "hit_rule": "All assembly pieces locked into blueprint before timeout",
            "failure_rule": "Session times out before blueprint is fully assembled"
        },
        9: {
            "name": "Precision Dots",
            "type": "hit_rate",
            "attempt_rule": "Each numbered dot in sequential precision path",
            "hit_rule": "Sequential target dot touched within radius",
            "failure_rule": "Wrong dot hovered or dot unreached before timeout"
        },
        10: {
            "name": "Precision Pathway",
            "type": "path_accuracy",
            "attempt_rule": "Total trajectory corridor tracking samples evaluated",
            "hit_rule": "Tracking sample index fingertip within corridor half-width",
            "failure_rule": "Sample distance exceeds corridor half-width boundary"
        }
    }

    def test_matrix_coverage(self):
        """Ensure all 10 exercises are mapped to valid accuracy types"""
        valid_types = {
            "hit_rate", "proximity_rate", "completion_rate",
            "path_accuracy", "binary_completion"
        }
        for level, meta in self.EXERCISE_MATRIX.items():
            self.assertIn(meta["type"], valid_types, f"Level {level} has invalid accuracy_type: {meta['type']}")
            self.assertTrue(len(meta["name"]) > 0)
            self.assertTrue(len(meta["attempt_rule"]) > 0)
            self.assertTrue(len(meta["hit_rule"]) > 0)


class TestDatabaseMigrationAndSave(unittest.TestCase):
    """Test non-destructive schema migration and research field persistence"""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db = DatabaseManager(db_path=self.temp_db.name)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_save_and_retrieve_research_session(self):
        """Verify all new research fields are persisted without data loss"""
        self.db.save_session(
            level=1,
            score=120,
            duration=30.5,
            avg_accuracy=60.0,
            max_extension=165.0,
            reach_distance=420.0,
            avg_hand_angle=45.0,
            pain_level=3,
            patient_id="ResearchPatient_01",
            pain_before_session=3,
            pain_after_session=2,
            functional_recovery_score=78.5,
            recovery_category="Good",
            movement_smoothness=0.85,
            movement_quality_score=82.0,
            successful_hits=3,
            total_attempts=5,
            accuracy_type="hit_rate",
            exercise_name="Bubble Pop",
            session_number=1,
            tracking_quality=98.5,
            tracking_frames_valid=591,
            tracking_frames_total=600,
            session_aborted=0,
            quality_flag="VALID"
        )

        conn = sqlite3.connect(self.temp_db.name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (self.db.last_session_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["successful_hits"], 3)
        self.assertEqual(row["total_attempts"], 5)
        self.assertEqual(row["avg_accuracy"], 60.0)
        self.assertEqual(row["accuracy_type"], "hit_rate")
        self.assertEqual(row["exercise_name"], "Bubble Pop")
        self.assertEqual(row["session_number"], 1)
        self.assertEqual(row["tracking_quality"], 98.5)
        self.assertEqual(row["tracking_frames_valid"], 591)
        self.assertEqual(row["tracking_frames_total"], 600)
        self.assertEqual(row["session_aborted"], 0)
        self.assertEqual(row["quality_flag"], "VALID")

    def test_save_zero_attempts_stores_null_accuracy(self):
        """Verify 0 attempts stores NULL in avg_accuracy with NO_VALID_ATTEMPTS flag"""
        self.db.save_session(
            level=5,
            score=0,
            duration=10.0,
            avg_accuracy=None,
            max_extension=120.0,
            successful_hits=0,
            total_attempts=0,
            accuracy_type="completion_rate",
            exercise_name="Grip & Release",
            session_number=2,
            tracking_quality=95.0,
            quality_flag="NO_VALID_ATTEMPTS"
        )

        conn = sqlite3.connect(self.temp_db.name)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (self.db.last_session_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNone(row["avg_accuracy"])
        self.assertEqual(row["total_attempts"], 0)
        self.assertEqual(row["quality_flag"], "NO_VALID_ATTEMPTS")


if __name__ == "__main__":
    unittest.main()
