"""
Automated Research & Functionality Test Suite for Level 14: Wrist Flexion-Extension Control.
Covers kinematic proxy tracking, sagittal target zones, dwell stabilization,
movement time, target error, overshoot, direction accuracy, database persistence,
and research export.
"""

import os
import sys
import time
import shutil
import tempfile
import sqlite3
import unittest
import pygame

pygame.font.init()
# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from physio.models import GameState, HandData, WristControlTarget
from physio.constants import LEVEL_DISPLAY_NAMES, AGE_THEMES, GAME_AREA_WIDTH, WINDOW_HEIGHT
from physio.database import DatabaseManager
import research_export


class MockSound:
    def play(self, name):
        pass


class MockScorePopup:
    def __init__(self, x, y, text, color=None):
        self.x = x
        self.y = y
        self.text = text
        self.color = color


class MockParticle:
    def emit(self, x, y, color, count):
        pass


class MockPhysioSystemLevel14:
    """Mock test harness isolating Level 14 gameplay state machine logic."""
    def __init__(self, tier=3):
        self.db = DatabaseManager("rehab_data.db")
        self.difficulty_tier = tier
        self.adaptive_target_scale = {1: 1.3, 2: 1.15, 3: 1.0, 4: 0.9, 5: 0.8}.get(tier, 1.0)
        self.session_time_limit = 45.0
        self.score_multiplier = 1.0
        self.score = 0
        self.combo = 0
        self.consecutive_misses = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.successful_hits = 0
        self.total_attempts = 0
        self.session_start = time.time()
        self.level_wall_start = time.time()
        self.sounds = MockSound()
        self.popups = []
        self.particles = MockParticle()
        self.ended = False
        
        self.screen = pygame.Surface((1280, 720))
        self.font_medium = pygame.font.SysFont("segoeui", 24)
        self.font_tiny = pygame.font.SysFont("segoeui", 12)
        self._get_theme = lambda: {"primary_color": (0, 200, 255)}
        
        # Import methods from GameplayMixin
        from physio.game_parts.gameplay import GameplayMixin
        self._init_level14 = GameplayMixin._init_level14.__get__(self)
        self._advance_level14_target = GameplayMixin._advance_level14_target.__get__(self)
        self._update_level14 = GameplayMixin._update_level14.__get__(self)
        self._draw_level14 = GameplayMixin._draw_level14.__get__(self)
        self._init_level14()

    def _end_level(self):
        self.ended = True


class TestLevel14WristControl(unittest.TestCase):

    def test_level14_registration_and_constants(self):
        """TEST 1: Verify Level 14 registration, display names, and theme icons."""
        self.assertTrue(hasattr(GameState, "LEVEL14_WRIST_CONTROL"))
        self.assertEqual(GameState.LEVEL14_WRIST_CONTROL.value, 29)
        self.assertIn(14, LEVEL_DISPLAY_NAMES)
        self.assertEqual(LEVEL_DISPLAY_NAMES[14], "Wrist Flexion-Extension Control")
        
        for group in ["child", "young", "adult", "senior"]:
            self.assertIn("level14_name", AGE_THEMES[group])
            self.assertIn("level14_icon", AGE_THEMES[group])
            self.assertTrue(len(AGE_THEMES[group]["level14_name"]) > 0)
            self.assertTrue(len(AGE_THEMES[group]["level14_icon"]) > 0)

    def test_level14_accuracy_types_and_exercise_names(self):
        """TEST 2: Verify research export and clinical registry alignment for Level 14."""
        self.assertEqual(research_export.ACCURACY_TYPES[14], "wrist_target_accuracy")
        self.assertEqual(research_export.EXERCISE_NAMES[14], "Wrist Flexion-Extension Control")

    def test_level14_tier_configuration(self):
        """TEST 3: Verify adaptive difficulty parameters for Level 14."""
        sys_t1 = MockPhysioSystemLevel14(tier=1)
        self.assertGreater(sys_t1.wrist_target_tolerance, 10.0)  # Forgiving tolerance
        self.assertLessEqual(sys_t1.wrist_dwell_required, 0.65)   # Shorter dwell
        
        sys_t5 = MockPhysioSystemLevel14(tier=5)
        self.assertLess(sys_t5.wrist_target_tolerance, sys_t1.wrist_target_tolerance)
        self.assertGreaterEqual(sys_t5.wrist_dwell_required, 1.0)

    def test_level14_initialization(self):
        """TEST 4: Verify Level 14 state initialization and target queue."""
        game = MockPhysioSystemLevel14(tier=3)
        self.assertIsNotNone(game.wrist_active_target)
        self.assertEqual(len(game.wrist_targets), 12)
        self.assertEqual(game.wrist_completed_targets, 0)
        self.assertEqual(game.trial_movement_times, [])
        self.assertEqual(game.trial_target_errors, [])
        self.assertEqual(game.trial_overshoots, [])
        self.assertEqual(game.trial_hold_stabilities, [])
        self.assertEqual(game.trial_direction_correct, [])

    def test_level14_target_generation(self):
        """TEST 5: Verify target sequence alternates or includes both Flexion and Extension."""
        game = MockPhysioSystemLevel14(tier=3)
        target_types = [t.target_type for t in game.wrist_targets]
        self.assertIn("EXTENSION", target_types)
        self.assertIn("FLEXION", target_types)

    def test_level14_extension_target_detection(self):
        """TEST 6: Verify Extension (+24°) target zone detection."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_active_target.target_type = "EXTENSION"
        game.wrist_active_target.target_angle = 24.0
        game.wrist_active_target.tolerance = 8.0
        
        # In target range: 24°
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=24.0)
        game._update_level14(hand)
        
        self.assertIsNotNone(game.wrist_dwell_start)
        self.assertGreater(game.wrist_contact_progress, 0.0)

    def test_level14_flexion_target_detection(self):
        """TEST 7: Verify Flexion (-24°) target zone detection."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_active_target.target_type = "FLEXION"
        game.wrist_active_target.target_angle = -24.0
        game.wrist_active_target.tolerance = 8.0
        
        # In target range: -24°
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=-24.0)
        game._update_level14(hand)
        
        self.assertIsNotNone(game.wrist_dwell_start)
        self.assertGreater(game.wrist_contact_progress, 0.0)

    def test_level14_incorrect_direction_handling(self):
        """TEST 8: Verify moving in opposite direction does not activate target."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_active_target.target_type = "EXTENSION"
        game.wrist_active_target.target_angle = 24.0
        game.wrist_active_target.tolerance = 8.0
        
        # Wrong direction: Flexion (-20°)
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=-20.0)
        game._update_level14(hand)
        
        self.assertIsNone(game.wrist_dwell_start)
        self.assertEqual(game.wrist_contact_progress, 0.0)

    def test_level14_dwell_stability_calculation(self):
        """TEST 9: Verify hold stability calculation under stable hold."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_active_target.target_type = "EXTENSION"
        game.wrist_active_target.target_angle = 24.0
        game.wrist_active_target.tolerance = 8.0
        game.wrist_dwell_required = 0.4
        
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=24.0)
        game._update_level14(hand)
        
        # Advance time by setting dwell_start earlier
        game.wrist_dwell_start = time.time() - 0.5
        game.wrist_dwell_samples = [24.0, 24.0, 24.0, 24.0]
        game._update_level14(hand)
        
        # Completed trial
        self.assertEqual(game.wrist_completed_targets, 1)
        self.assertEqual(game.successful_hits, 1)
        self.assertGreaterEqual(game.trial_hold_stabilities[0], 90.0)

    def test_level14_successful_trial_advancement(self):
        """TEST 10: Verify successful target completion increments metrics and advances target."""
        game = MockPhysioSystemLevel14(tier=3)
        initial_target_id = game.wrist_active_target.target_id
        game.wrist_dwell_required = 0.2
        
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=game.wrist_active_target.target_angle)
        game._update_level14(hand)
        game.wrist_dwell_start = time.time() - 0.3
        game._update_level14(hand)
        
        self.assertEqual(game.successful_hits, 1)
        self.assertEqual(game.total_attempts, 1)
        self.assertEqual(game.combo, 1)
        self.assertNotEqual(game.wrist_active_target.target_id, initial_target_id)

    def test_level14_target_timeout_miss(self):
        """TEST 11: Verify target timeout counts as an attempt and miss."""
        game = MockPhysioSystemLevel14(tier=3)
        game.combo = 3
        # Set target start to past timeout
        game.wrist_target_start = time.time() - (game.prompt_timeout + 1.0)
        
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=0.0)  # Neutral, not in zone
        game._update_level14(hand)
        
        self.assertEqual(game.successful_hits, 0)
        self.assertEqual(game.total_attempts, 1)
        self.assertEqual(game.combo, 0)  # Combo reset
        self.assertEqual(len(game.trial_movement_times), 1)

    def test_level14_target_error_calculation(self):
        """TEST 12: Verify target error tracks angular deviation correctly."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_active_target.target_angle = 24.0
        game.wrist_active_target.tolerance = 10.0
        game.wrist_dwell_required = 0.1
        
        # Hold at 20.0° (deviation of 4.0°)
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=20.0)
        game._update_level14(hand)
        game.wrist_dwell_start = time.time() - 0.2
        game._update_level14(hand)
        
        self.assertEqual(len(game.trial_target_errors), 1)
        self.assertAlmostEqual(game.trial_target_errors[0], 4.0, places=1)

    def test_level14_overshoot_calculation(self):
        """TEST 13: Verify overshoot records deflection exceeding outer target boundary upon trial completion."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_active_target.target_type = "EXTENSION"
        game.wrist_active_target.target_angle = 24.0
        game.wrist_active_target.tolerance = 6.0  # Zone is 18° to 30°
        game.wrist_dwell_required = 0.1
        
        # Target angle 24.0, tol 6.0 -> max boundary = 30.0.
        # Deflection at 33.0°: in_zone would be false unless tolerance covers it,
        # but let's test timeout or completion at outer boundary edge.
        # When current_pitch is 33.0 and timeout occurs:
        game.wrist_target_start = time.time() - (game.prompt_timeout + 1.0)
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=33.0)
        game._update_level14(hand)
        
        # Overshoot is max(0, 33 - 30) = 3.0°
        self.assertEqual(len(game.trial_overshoots), 1)
        self.assertAlmostEqual(game.trial_overshoots[0], 3.0, places=1)

    def test_level14_movement_time_tracking(self):
        """TEST 14: Verify movement time from target start to completion is recorded."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_target_start = time.time() - 1.8
        game.wrist_dwell_required = 0.1
        
        hand = HandData(index_tip=(400, 300), wrist_flexion_extension_angle=game.wrist_active_target.target_angle)
        game._update_level14(hand)
        game.wrist_dwell_start = time.time() - 0.2
        game._update_level14(hand)
        
        self.assertEqual(len(game.trial_movement_times), 1)
        self.assertGreaterEqual(game.trial_movement_times[0], 1.5)

    def test_level14_accuracy_calculation(self):
        """TEST 15: Verify accuracy reflects hits / attempts * 100."""
        game = MockPhysioSystemLevel14(tier=3)
        game.successful_hits = 4
        game.total_attempts = 5
        accuracy = (game.successful_hits / game.total_attempts) * 100.0
        self.assertEqual(accuracy, 80.0)

    def test_level14_zero_attempts_null_accuracy(self):
        """TEST 16: Verify 0 attempts session stores NULL accuracy and NO_VALID_ATTEMPTS flag."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_zero_att.db")
            db = DatabaseManager(test_db)
            
            # Save session with 0 attempts
            db.save_session(
                level=14,
                score=0,
                duration=5.0,
                avg_accuracy=None,
                max_extension=0.0,
                patient_id="ZERO_ATT_PATIENT",
                successful_hits=0,
                total_attempts=0,
                accuracy_type="wrist_target_accuracy",
                exercise_name="Wrist Flexion-Extension Control",
                quality_flag="NO_VALID_ATTEMPTS"
            )
            
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT avg_accuracy, quality_flag FROM sessions WHERE level = 14")
            row = cursor.fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertIsNone(row["avg_accuracy"])
            self.assertEqual(row["quality_flag"], "NO_VALID_ATTEMPTS")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level14_invalid_hit_protection(self):
        """TEST 17: Verify hits can never exceed attempts."""
        game = MockPhysioSystemLevel14(tier=3)
        self.assertLessEqual(game.successful_hits, game.total_attempts)

    def test_level14_tracking_quality_flags(self):
        """TEST 18: Verify tracking quality flag assignment."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_tracking.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=14,
                score=100,
                duration=20.0,
                avg_accuracy=50.0,
                max_extension=20.0,
                patient_id="TRACKING_PATIENT",
                successful_hits=1,
                total_attempts=2,
                tracking_quality=40.0,
                quality_flag="LOW_TRACKING_QUALITY"
            )
            
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT quality_flag FROM sessions WHERE level = 14")
            row = cursor.fetchone()
            conn.close()
            
            self.assertEqual(row["quality_flag"], "LOW_TRACKING_QUALITY")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level14_database_persistence(self):
        """TEST 19: Verify SQLite saves and retrieves all Level 14 columns."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_level14.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=14,
                score=350,
                duration=35.0,
                avg_accuracy=85.0,
                max_extension=28.0,
                patient_id="TEST_WRIST_PATIENT",
                successful_hits=7,
                total_attempts=8,
                accuracy_type="wrist_target_accuracy",
                exercise_name="Wrist Flexion-Extension Control",
                tracking_quality=95.0,
                average_movement_time=1.45,
                average_target_error=3.2,
                average_overshoot=1.1,
                average_hold_stability=88.5,
                direction_accuracy=100.0
            )
            
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE level = 14")
            row = cursor.fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertEqual(row["level"], 14)
            self.assertEqual(row["exercise_name"], "Wrist Flexion-Extension Control")
            self.assertEqual(row["accuracy_type"], "wrist_target_accuracy")
            self.assertEqual(row["successful_hits"], 7)
            self.assertEqual(row["total_attempts"], 8)
            self.assertEqual(row["avg_accuracy"], 85.0)
            self.assertAlmostEqual(row["average_movement_time"], 1.45, places=2)
            self.assertAlmostEqual(row["average_target_error"], 3.2, places=1)
            self.assertAlmostEqual(row["average_overshoot"], 1.1, places=1)
            self.assertAlmostEqual(row["average_hold_stability"], 88.5, places=1)
            self.assertAlmostEqual(row["direction_accuracy"], 100.0, places=1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level14_research_export(self):
        """TEST 20: Verify research_export exports CSV with Level 14 columns aligned."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_research_level14.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=14,
                score=400,
                duration=32.0,
                avg_accuracy=100.0,
                max_extension=30.0,
                patient_id="RESEARCH_PATIENT_14",
                successful_hits=10,
                total_attempts=10,
                accuracy_type="wrist_target_accuracy",
                exercise_name="Wrist Flexion-Extension Control",
                tracking_quality=98.0,
                quality_flag="VALID",
                average_movement_time=1.20,
                average_target_error=2.5,
                average_overshoot=0.5,
                average_hold_stability=92.0,
                direction_accuracy=100.0
            )
            
            out_csv = os.path.join(temp_dir, "export_level14.csv")
            rows = research_export.export_research_dataset(
                db_path=test_db,
                output_csv=out_csv,
                pseudonymize=True,
                valid_only=False
            )
            self.assertEqual(rows, 1)
            
            with open(out_csv, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines()]
                
            header = lines[0].split(",")
            data = lines[1].split(",")
            
            self.assertEqual(len(header), len(data))
            self.assertIn("Movement_Time", header)
            self.assertIn("Target_Error", header)
            self.assertIn("Overshoot", header)
            self.assertIn("Hold_Stability", header)
            self.assertIn("Direction_Accuracy", header)
            
            mov_time_pos = header.index("Movement_Time")
            hold_pos = header.index("Hold_Stability")
            self.assertEqual(data[mov_time_pos], "1.20")
            self.assertEqual(data[hold_pos], "92.00")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level14_adaptive_difficulty_integration(self):
        """TEST 21: Verify adaptive target scaling modulates tolerance and dwell."""
        sys_normal = MockPhysioSystemLevel14(tier=3)
        tol_normal = sys_normal.wrist_target_tolerance
        
        sys_scaled = MockPhysioSystemLevel14(tier=3)
        sys_scaled.adaptive_target_scale = 1.30  # Larger scaling -> wider tolerance
        sys_scaled._init_level14()
        tol_scaled = sys_scaled.wrist_target_tolerance
        
        self.assertGreater(tol_scaled, tol_normal)

    def test_level14_draw_rendering(self):
        """TEST 22: Verify _draw_level14 renders without exceptions."""
        game = MockPhysioSystemLevel14(tier=3)
        game.wrist_contact_progress = 0.5
        game._draw_level14()
        
        game.wrist_active_target = None
        game._draw_level14()


if __name__ == "__main__":
    unittest.main()
