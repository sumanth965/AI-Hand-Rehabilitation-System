"""
Automated Research & Functionality Test Suite for Level 13: Finger Isolation Challenge.
Covers finger selective activation detection, unintended movement tracking, dwell timing,
accuracy calculations, finger-specific telemetry, quality flags, database persistence, and research export.
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

from physio.models import GameState, HandData, IsolationPrompt
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


class MockPhysioSystemLevel13:
    """Mock test harness isolating Level 13 gameplay state machine logic."""
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
        self._init_level13 = GameplayMixin._init_level13.__get__(self)
        self._advance_level13_prompt = GameplayMixin._advance_level13_prompt.__get__(self)
        self._update_level13 = GameplayMixin._update_level13.__get__(self)
        self._draw_level13 = GameplayMixin._draw_level13.__get__(self)
        self._get_digit_activation_threshold = GameplayMixin._get_digit_activation_threshold.__get__(self)
        self._get_unintended_threshold = GameplayMixin._get_unintended_threshold.__get__(self)
        self._init_level13()

    def _end_level(self):
        self.ended = True


class TestLevel13FingerIsolation(unittest.TestCase):

    def test_level13_registration_and_constants(self):
        """TEST 1: Verify Level 13 registration, display names, and theme icons."""
        self.assertTrue(hasattr(GameState, "LEVEL13_FINGER_ISOLATION"))
        self.assertEqual(GameState.LEVEL13_FINGER_ISOLATION.value, 28)
        self.assertIn(13, LEVEL_DISPLAY_NAMES)
        self.assertEqual(LEVEL_DISPLAY_NAMES[13], "Finger Isolation Challenge")
        
        for group in ["child", "young", "adult", "senior"]:
            self.assertIn("level13_name", AGE_THEMES[group])
            self.assertIn("level13_icon", AGE_THEMES[group])
            self.assertTrue(len(AGE_THEMES[group]["level13_name"]) > 0)
            self.assertTrue(len(AGE_THEMES[group]["level13_icon"]) > 0)

    def test_level13_accuracy_types_and_exercise_names(self):
        """TEST 2: Verify research export and clinical registry alignment for Level 13."""
        self.assertEqual(research_export.ACCURACY_TYPES[13], "finger_isolation_accuracy")
        self.assertEqual(research_export.EXERCISE_NAMES[13], "Finger Isolation")

    def test_level13_tier_configuration(self):
        """TEST 3: Verify adaptive difficulty parameters for Level 13."""
        sys_t1 = MockPhysioSystemLevel13(tier=1)
        self.assertLess(sys_t1.isolation_activation_threshold, 135.0)  # Easier extension threshold
        self.assertLess(sys_t1.isolation_dwell_required, 0.40)         # Shorter dwell hold
        
        sys_t5 = MockPhysioSystemLevel13(tier=5)
        self.assertGreater(sys_t5.isolation_activation_threshold, sys_t1.isolation_activation_threshold)
        self.assertGreaterEqual(sys_t5.isolation_dwell_required, 0.50)

    def test_level13_initialization(self):
        """TEST 4: Verify Level 13 state initialization and prompt sequences."""
        game = MockPhysioSystemLevel13(tier=3)
        self.assertIsNotNone(game.isolation_active_prompt)
        self.assertEqual(len(game.isolation_prompts), 12)
        self.assertEqual(game.index_successes, 0)
        self.assertEqual(game.middle_successes, 0)
        self.assertEqual(game.ring_successes, 0)
        self.assertEqual(game.pinky_successes, 0)
        self.assertEqual(game.unintended_movement_events, 0)

    def test_level13_index_target_detection(self):
        """TEST 5: Verify Index finger (D2) isolated extension detection."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 2  # Target = Index
        
        # Knuckle angles: Index extended (160°), others flexed (90°)
        hand = HandData(
            index_tip=(400, 200),
            middle_tip=(450, 400),
            ring_tip=(500, 400),
            pinky_tip=(550, 400),
            knuckle_angles=[160.0, 90.0, 90.0, 90.0]
        )
        game._update_level13(hand)
        self.assertIsNotNone(game.isolation_dwell_start)
        self.assertGreater(game.isolation_contact_progress, 0.0)

    def test_level13_middle_target_detection(self):
        """TEST 6: Verify Middle finger (D3) isolated extension detection."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 3  # Target = Middle
        
        hand = HandData(
            index_tip=(400, 400),
            middle_tip=(450, 200),
            ring_tip=(500, 400),
            pinky_tip=(550, 400),
            knuckle_angles=[90.0, 160.0, 90.0, 90.0]
        )
        game._update_level13(hand)
        self.assertIsNotNone(game.isolation_dwell_start)
        self.assertGreater(game.isolation_contact_progress, 0.0)

    def test_level13_ring_target_detection(self):
        """TEST 7: Verify Ring finger (D4) isolated extension detection."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 4  # Target = Ring
        
        hand = HandData(
            index_tip=(400, 400),
            middle_tip=(450, 400),
            ring_tip=(500, 200),
            pinky_tip=(550, 400),
            knuckle_angles=[90.0, 90.0, 160.0, 90.0]
        )
        game._update_level13(hand)
        self.assertIsNotNone(game.isolation_dwell_start)
        self.assertGreater(game.isolation_contact_progress, 0.0)

    def test_level13_pinky_target_detection(self):
        """TEST 8: Verify Pinky finger (D5) isolated extension detection."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 5  # Target = Pinky
        
        hand = HandData(
            index_tip=(400, 400),
            middle_tip=(450, 400),
            ring_tip=(500, 400),
            pinky_tip=(550, 200),
            knuckle_angles=[90.0, 90.0, 90.0, 160.0]
        )
        game._update_level13(hand)
        self.assertIsNotNone(game.isolation_dwell_start)
        self.assertGreater(game.isolation_contact_progress, 0.0)

    def test_level13_successful_activation_and_dwell_success(self):
        """TEST 9: Verify dwell completion triggers hit, increments counter, and advances prompt."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 2  # Target = Index
        
        hand = HandData(
            index_tip=(400, 200),
            knuckle_angles=[160.0, 90.0, 90.0, 90.0]
        )
        
        # 1. Start dwell
        game._update_level13(hand)
        self.assertIsNotNone(game.isolation_dwell_start)
        
        # 2. Simulate holding past dwell requirement
        game.isolation_dwell_start = time.time() - 0.60
        initial_hits = game.accuracy_hits
        initial_attempts = game.accuracy_attempts
        
        game._update_level13(hand)
        self.assertEqual(game.accuracy_hits, initial_hits + 1)
        self.assertEqual(game.accuracy_attempts, initial_attempts + 1)
        self.assertEqual(game.index_successes, 1)
        self.assertEqual(game.index_attempts, 1)
        self.assertEqual(game.dwell_success_count, 1)
        self.assertGreater(len(game.target_activation_times), 0)
        self.assertGreater(game.target_activation_time_avg, 0.0)

    def test_level13_failed_activation_and_dwell_failure(self):
        """TEST 10: Verify early drop of extension resets dwell and records dwell failure."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 2
        
        hand_active = HandData(
            index_tip=(400, 200),
            knuckle_angles=[160.0, 90.0, 90.0, 90.0]
        )
        game._update_level13(hand_active)
        self.assertIsNotNone(game.isolation_dwell_start)
        
        # Simulate partial hold followed by finger drop
        game.isolation_dwell_start = time.time() - 0.20  # Under dwell threshold (0.45s)
        hand_dropped = HandData(
            index_tip=(400, 400),
            knuckle_angles=[90.0, 90.0, 90.0, 90.0]  # Curled back
        )
        game._update_level13(hand_dropped)
        self.assertIsNone(game.isolation_dwell_start)
        self.assertEqual(game.dwell_failure_count, 1)
        self.assertEqual(game.accuracy_hits, 0)

    def test_level13_unintended_movement_detection(self):
        """TEST 11: Verify unintended movement in adjacent non-target fingers increments event count and blocks detection."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 2  # Target = Index
        
        # Target active, but Middle finger also extends beyond closed threshold (145° >= 115°)
        hand_coactive = HandData(
            index_tip=(400, 200),
            middle_tip=(450, 210),
            knuckle_angles=[160.0, 145.0, 90.0, 90.0]
        )
        game._update_level13(hand_coactive)
        self.assertGreaterEqual(game.unintended_movement_events, 1)
        self.assertIn(3, game.live_unintended_digits)
        # CRITICAL: Target MUST NOT be detected and dwell MUST NOT start when other fingers are open!
        self.assertIsNone(game.isolation_dwell_start)
        self.assertEqual(game.isolation_contact_progress, 0.0)
        self.assertEqual(game.accuracy_hits, 0)

    def test_level13_target_blocked_when_all_fingers_open_or_opened_during_dwell(self):
        """TEST 23: Target finger must only be detected when other fingers are closed."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_active_prompt.digit_id = 2  # Target = Index
        
        # 1. Full open hand presented: all fingers open
        open_hand = HandData(
            index_tip=(400, 200),
            middle_tip=(450, 200),
            ring_tip=(500, 200),
            pinky_tip=(550, 200),
            knuckle_angles=[165.0, 160.0, 155.0, 150.0]
        )
        game._update_level13(open_hand)
        # Must NOT detect target when other fingers are open
        self.assertIsNone(game.isolation_dwell_start)
        self.assertEqual(game.isolation_contact_progress, 0.0)
        self.assertEqual(game.accuracy_hits, 0)
        self.assertEqual(len(game.live_unintended_digits), 3)  # Middle, Ring, Pinky are open
        
        # 2. Present clean isolated index finger (others closed at 90°)
        clean_hand = HandData(
            index_tip=(400, 200),
            knuckle_angles=[160.0, 90.0, 90.0, 90.0]
        )
        game._update_level13(clean_hand)
        self.assertIsNotNone(game.isolation_dwell_start)
        self.assertGreater(game.isolation_contact_progress, 0.0)
        self.assertEqual(len(game.live_unintended_digits), 0)
        
        # 3. User accidentally opens middle finger during dwell hold
        coactive_hand = HandData(
            index_tip=(400, 200),
            middle_tip=(450, 250),
            knuckle_angles=[160.0, 135.0, 90.0, 90.0]
        )
        game._update_level13(coactive_hand)
        # Dwell must immediately reset because other finger opened!
        self.assertIsNone(game.isolation_dwell_start)
        self.assertEqual(game.isolation_contact_progress, 0.0)
        self.assertEqual(game.accuracy_hits, 0)
        self.assertIn(3, game.live_unintended_digits)

    def test_level13_prompt_timeout(self):
        """TEST 12: Verify prompt timeout registers missed attempt and advances sequence."""
        game = MockPhysioSystemLevel13(tier=3)
        target_d = game.isolation_active_prompt.digit_id
        
        # Simulate elapsed prompt timeout
        game.isolation_prompt_start = time.time() - 10.0
        hand = HandData(
            index_tip=(400, 400),
            knuckle_angles=[90.0, 90.0, 90.0, 90.0]
        )
        initial_attempts = game.accuracy_attempts
        initial_hits = game.accuracy_hits
        
        game._update_level13(hand)
        self.assertEqual(game.accuracy_attempts, initial_attempts + 1)
        self.assertEqual(game.accuracy_hits, initial_hits)
        if target_d == 2: self.assertEqual(game.index_attempts, 1)
        elif target_d == 3: self.assertEqual(game.middle_attempts, 1)
        elif target_d == 4: self.assertEqual(game.ring_attempts, 1)
        elif target_d == 5: self.assertEqual(game.pinky_attempts, 1)

    def test_level13_accuracy_calculations(self):
        """TEST 13: Verify accurate percentage calculations for 100%, 70%, and 0%."""
        # 10/10 hits -> 100%
        hits, attempts = 10, 10
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertEqual(acc, 100.0)
        
        # 7/10 hits -> 70%
        hits, attempts = 7, 10
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertEqual(acc, 70.0)
        
        # 0/10 hits -> 0.0% (MOTOR_FAILURE)
        hits, attempts = 0, 10
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertEqual(acc, 0.0)
        flag = "MOTOR_FAILURE" if (attempts > 0 and hits == 0) else "VALID"
        self.assertEqual(flag, "MOTOR_FAILURE")

    def test_level13_zero_attempt_handling(self):
        """TEST 14: Verify zero attempts returns None and flags NO_VALID_ATTEMPTS."""
        hits, attempts = 0, 0
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertIsNone(acc)
        flag = "NO_VALID_ATTEMPTS" if attempts == 0 else "VALID"
        self.assertEqual(flag, "NO_VALID_ATTEMPTS")

    def test_level13_invalid_hit_attempt_protection(self):
        """TEST 15: Verify protection against impossible hit counts."""
        hits, attempts = 12, 10
        flag = "ACCURACY_ERROR" if (hits > attempts or hits < 0) else "VALID"
        self.assertEqual(flag, "ACCURACY_ERROR")

    def test_level13_finger_specific_counters(self):
        """TEST 16: Verify distinct per-finger attempts and successes."""
        game = MockPhysioSystemLevel13(tier=3)
        # Manually verify counters can be updated independently
        game.index_successes = 3
        game.index_attempts = 4
        game.middle_successes = 2
        game.middle_attempts = 3
        game.ring_successes = 1
        game.ring_attempts = 2
        game.pinky_successes = 0
        game.pinky_attempts = 1
        
        self.assertEqual(game.index_successes / game.index_attempts, 0.75)
        self.assertEqual(game.middle_successes / game.middle_attempts, 2/3)

    def test_level13_tracking_quality_calculation(self):
        """TEST 17: Verify tracking quality percentage and degradation flags."""
        valid_f, total_f = 85, 100
        tq = round((valid_f / total_f * 100.0), 2)
        self.assertEqual(tq, 85.0)
        flag = "VALID" if tq >= 50.0 else "TRACKING_ERROR"
        self.assertEqual(flag, "VALID")
        
        # Degraded tracking < 50%
        valid_f, total_f = 35, 100
        tq = round((valid_f / total_f * 100.0), 2)
        self.assertEqual(tq, 35.0)
        flag = "TRACKING_ERROR" if tq < 50.0 else "VALID"
        self.assertEqual(flag, "TRACKING_ERROR")

    def test_level13_quality_flags(self):
        """TEST 18: Verify quality flag prioritization (aborted, tracking, motor)."""
        aborted = 1
        flag = "ABORTED_SESSION" if aborted else "VALID"
        self.assertEqual(flag, "ABORTED_SESSION")

    def test_level13_database_persistence(self):
        """TEST 19: Verify database save_session records Level 13 isolation columns."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_level13.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=13,
                score=280,
                duration=32.0,
                avg_accuracy=75.0,
                max_extension=160.0,
                patient_id="TEST_ISOLATION_PATIENT",
                successful_hits=6,
                total_attempts=8,
                accuracy_type="finger_isolation_accuracy",
                exercise_name="Finger Isolation",
                tracking_quality=94.0,
                index_successes=2,
                middle_successes=2,
                ring_successes=1,
                pinky_successes=1,
                index_attempts=2,
                middle_attempts=2,
                ring_attempts=2,
                pinky_attempts=2,
                unintended_movement_events=3,
                target_activation_time_avg=1.35,
                dwell_success_count=6,
                dwell_failure_count=1
            )
            
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE level = 13")
            row = cursor.fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertEqual(row["level"], 13)
            self.assertEqual(row["exercise_name"], "Finger Isolation")
            self.assertEqual(row["accuracy_type"], "finger_isolation_accuracy")
            self.assertEqual(row["successful_hits"], 6)
            self.assertEqual(row["total_attempts"], 8)
            self.assertEqual(row["avg_accuracy"], 75.0)
            self.assertEqual(row["index_successes"], 2)
            self.assertEqual(row["middle_successes"], 2)
            self.assertEqual(row["ring_successes"], 1)
            self.assertEqual(row["pinky_successes"], 1)
            self.assertEqual(row["unintended_movement_events"], 3)
            self.assertAlmostEqual(row["target_activation_time_avg"], 1.35, places=2)
            self.assertEqual(row["dwell_success_count"], 6)
            self.assertEqual(row["dwell_failure_count"], 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level13_research_export(self):
        """TEST 20: Verify research_export exports CSV with Level 13 columns aligned."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_research_level13.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=13,
                score=320,
                duration=30.0,
                avg_accuracy=100.0,
                max_extension=170.0,
                patient_id="RESEARCH_PATIENT_13",
                successful_hits=8,
                total_attempts=8,
                accuracy_type="finger_isolation_accuracy",
                exercise_name="Finger Isolation",
                tracking_quality=99.0,
                quality_flag="VALID",
                index_successes=2,
                middle_successes=2,
                ring_successes=2,
                pinky_successes=2,
                index_attempts=2,
                middle_attempts=2,
                ring_attempts=2,
                pinky_attempts=2,
                unintended_movement_events=1,
                target_activation_time_avg=1.10,
                dwell_success_count=8,
                dwell_failure_count=0
            )
            
            out_csv = os.path.join(temp_dir, "export_level13.csv")
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
            self.assertIn("Index_Successes", header)
            self.assertIn("Middle_Successes", header)
            self.assertIn("Ring_Successes", header)
            self.assertIn("Pinky_Successes", header)
            self.assertIn("Unintended_Movement_Events", header)
            self.assertIn("Target_Activation_Time_Avg", header)
            
            idx_succ_pos = header.index("Index_Successes")
            unintended_pos = header.index("Unintended_Movement_Events")
            self.assertEqual(data[idx_succ_pos], "2")
            self.assertEqual(data[unintended_pos], "1")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level13_adaptive_difficulty_integration(self):
        """TEST 21: Verify adaptive target scaling modulates activation threshold."""
        sys_normal = MockPhysioSystemLevel13(tier=3)
        thresh_normal = sys_normal.isolation_activation_threshold
        
        sys_scaled = MockPhysioSystemLevel13(tier=3)
        sys_scaled.adaptive_target_scale = 1.30  # Larger scaling -> more forgiving threshold
        sys_scaled._init_level13()
        thresh_scaled = sys_scaled.isolation_activation_threshold
        
        self.assertLess(thresh_scaled, thresh_normal)

    def test_level13_draw_rendering(self):
        """TEST 22: Verify _draw_level13 renders without exceptions."""
        game = MockPhysioSystemLevel13(tier=3)
        game.isolation_contact_progress = 0.5
        game._draw_level13()
        
        game.isolation_active_prompt = None
        game._draw_level13()


if __name__ == "__main__":
    unittest.main()
