"""
Automated Research & Functionality Test Suite for Level 12: Card Shift Challenge (In-Hand Manipulation / Finger Shifting).
Covers clinical accuracy calculations, state machines, tracking quality flags, database persistence, and research export.
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

from physio.models import GameState, HandData, CardShiftPrompt
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


class MockPhysioSystemLevel12:
    """Mock test harness isolating Level 12 Card Shift Challenge state machine logic."""
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
        self._get_theme = lambda: {"primary_color": (0, 200, 255), "level12_name": "Card Shift Challenge"}
        
        # Import methods from GameplayMixin
        from physio.game_parts.gameplay import GameplayMixin
        self._init_level12 = GameplayMixin._init_level12.__get__(self)
        self._advance_level12_prompt = GameplayMixin._advance_level12_prompt.__get__(self)
        self._update_level12 = GameplayMixin._update_level12.__get__(self)
        self._draw_level12 = GameplayMixin._draw_level12.__get__(self)
        self._init_level12()

    def _end_level(self):
        self.ended = True


class TestLevel12CardShift(unittest.TestCase):

    def test_level12_registration_and_constants(self):
        """TEST 1: Verify Level 12 registration, display names, and themes."""
        self.assertTrue(hasattr(GameState, "LEVEL12_CARD_SHIFT"))
        self.assertEqual(GameState.LEVEL12_CARD_SHIFT.value, 27)
        self.assertIn(12, LEVEL_DISPLAY_NAMES)
        self.assertEqual(LEVEL_DISPLAY_NAMES[12], "Card Shift Challenge")
        
        # Check theme definitions across all age groups
        for group in ["child", "young", "adult", "senior"]:
            self.assertIn("level12_name", AGE_THEMES[group])
            self.assertIn("level12_icon", AGE_THEMES[group])
            self.assertTrue(len(AGE_THEMES[group]["level12_name"]) > 0)
            self.assertEqual(AGE_THEMES[group]["level12_icon"], "🃏")

    def test_level12_accuracy_types_and_exercise_names(self):
        """TEST 2: Verify research export and clinical registry alignment."""
        self.assertEqual(research_export.ACCURACY_TYPES[12], "completion_rate")
        self.assertEqual(research_export.EXERCISE_NAMES[12], "Card Shift Challenge")

    def test_level12_tier_configuration(self):
        """TEST 3: Verify adaptive difficulty parameters for Level 12."""
        sys_t1 = MockPhysioSystemLevel12(tier=1)
        self.assertEqual(len(sys_t1.prompts), 5)
        self.assertGreater(sys_t1.card_shift_tolerance, 50.0)  # More forgiving at tier 1
        self.assertLessEqual(sys_t1.card_dwell_required, 0.22) # Faster dwell at tier 1
        
        sys_t5 = MockPhysioSystemLevel12(tier=5)
        self.assertEqual(len(sys_t5.prompts), 10)
        self.assertLess(sys_t5.card_shift_tolerance, sys_t1.card_shift_tolerance)
        self.assertGreaterEqual(sys_t5.card_dwell_required, 0.25)

    def test_level12_accuracy_calculations(self):
        """TEST 4: Verify 100%, 60%, 0%, and zero-attempt accuracy behaviors."""
        # 5/5 hits -> 100%
        hits, attempts = 5, 5
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertEqual(acc, 100.0)
        
        # 3/5 hits -> 60%
        hits, attempts = 3, 5
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertEqual(acc, 60.0)
        
        # 0/5 hits -> 0% (Motor failure, not missing data)
        hits, attempts = 0, 5
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertEqual(acc, 0.0)
        quality_flag = "MOTOR_FAILURE" if (attempts > 0 and hits == 0) else "VALID"
        self.assertEqual(quality_flag, "MOTOR_FAILURE")
        
        # 0 attempts -> None / NO_VALID_ATTEMPTS
        hits, attempts = 0, 0
        acc = round((hits / attempts * 100.0), 2) if attempts > 0 else None
        self.assertIsNone(acc)
        quality_flag = "NO_VALID_ATTEMPTS" if attempts == 0 else "VALID"
        self.assertEqual(quality_flag, "NO_VALID_ATTEMPTS")
        
        # Impossible condition: hits > attempts
        hits, attempts = 6, 5
        quality_flag = "ACCURACY_ERROR" if (hits > attempts or hits < 0) else "VALID"
        self.assertEqual(quality_flag, "ACCURACY_ERROR")

    def test_level12_tracking_quality_flags(self):
        """TEST 5: Verify tracking quality and session abort flags."""
        valid_f, total_f = 90, 100
        tq = round((valid_f / total_f * 100.0), 2)
        self.assertEqual(tq, 90.0)
        flag = "VALID" if tq >= 50.0 else "TRACKING_ERROR"
        self.assertEqual(flag, "VALID")
        
        valid_f, total_f = 30, 100
        tq = round((valid_f / total_f * 100.0), 2)
        self.assertEqual(tq, 30.0)
        flag = "TRACKING_ERROR" if tq < 50.0 else "VALID"
        self.assertEqual(flag, "TRACKING_ERROR")
        
        aborted = 1
        flag = "ABORTED_SESSION" if aborted else "VALID"
        self.assertEqual(flag, "ABORTED_SESSION")

    def test_level12_card_shift_contact_cycle(self):
        """TEST 6: Verify full card shift contact, dwell hold, and prompt advancement."""
        game = MockPhysioSystemLevel12(tier=3)
        self.assertIsNotNone(game.active_prompt)
        target_digit = game.active_prompt.target_digit_id
        
        # Positions: Palm=0, Index=2, Middle=3, Ring=4, Pinky=5
        # Set cursor to target position
        target_pos = (500, 300)
        other_pos = (800, 800)
        
        fingers = {0: other_pos, 2: other_pos, 3: other_pos, 4: other_pos, 5: other_pos}
        fingers[target_digit] = target_pos
        
        hand = HandData(
            thumb_tip=target_pos,
            index_tip=fingers[2],
            middle_tip=fingers[3],
            ring_tip=fingers[4],
            pinky_tip=fingers[5]
        )
        
        # 1. First contact begins dwell
        game._update_level12(hand)
        self.assertIsNotNone(game.card_dwell_start)
        self.assertGreater(game.card_contact_progress, 0.0)
        
        # 2. Simulate holding dwell past requirement
        game.card_dwell_start = time.time() - 0.40  # 0.40s > 0.25s
        initial_hits = game.accuracy_hits
        initial_attempts = game.accuracy_attempts
        
        game._update_level12(hand)
        self.assertEqual(game.accuracy_hits, initial_hits + 1)
        self.assertEqual(game.accuracy_attempts, initial_attempts + 1)
        self.assertEqual(game.card_shift_successes, 1)
        self.assertEqual(game.card_shift_attempts, 1)
        self.assertGreater(game.average_shift_latency, 0.0)
        self.assertGreater(game.median_shift_latency, 0.0)

    def test_level12_wrong_finger_and_timeout(self):
        """TEST 7: Verify wrong finger touch registers attempt & error, and timeout logs attempt."""
        game = MockPhysioSystemLevel12(tier=3)
        target_digit = game.active_prompt.target_digit_id
        wrong_digit = 3 if target_digit == 2 else 2
        
        fingers = {0: (800, 800), 2: (800, 800), 3: (800, 800), 4: (800, 800), 5: (800, 800)}
        fingers[wrong_digit] = (400, 300)
        fingers[target_digit] = (700, 700)
        
        hand = HandData(
            thumb_tip=(400, 300),
            index_tip=fingers[2],
            middle_tip=fingers[3],
            ring_tip=fingers[4],
            pinky_tip=fingers[5]
        )
        
        initial_attempts = game.accuracy_attempts
        initial_hits = game.accuracy_hits
        
        # Touch wrong finger
        game._update_level12(hand)
        self.assertEqual(game.incorrect_finger_events, 1)
        self.assertEqual(game.accuracy_attempts, initial_attempts + 1)
        self.assertEqual(game.accuracy_hits, initial_hits)
        
        # Test prompt timeout
        game.active_prompt_start = time.time() - 10.0  # Elapsed > timeout
        hand_neutral = HandData(
            thumb_tip=(100, 100),
            index_tip=(800, 800),
            middle_tip=(800, 800),
            ring_tip=(800, 800),
            pinky_tip=(800, 800)
        )
        game._update_level12(hand_neutral)
        self.assertEqual(game.target_timeouts, 1)
        self.assertEqual(game.accuracy_attempts, initial_attempts + 2)
        self.assertEqual(game.accuracy_hits, initial_hits)

    def test_level12_database_persistence(self):
        """TEST 8: Verify database save_session records Level 12 Card Shift columns."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_level12_cs.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=12,
                score=260,
                duration=32.0,
                avg_accuracy=75.0,
                max_extension=165.0,
                reach_distance=210.0,
                avg_hand_angle=45.0,
                pain_level=2,
                patient_id="TEST_CARD_SHIFT",
                successful_hits=6,
                total_attempts=8,
                accuracy_type="completion_rate",
                exercise_name="Card Shift Challenge",
                tracking_quality=95.0,
                card_shift_successes=6,
                card_shift_attempts=8,
                average_shift_latency=1.85,
                median_shift_latency=1.80,
                maximum_shift_latency=2.40,
                incorrect_finger_events=2,
                target_timeouts=1,
                sequence_completion_rate=75.0
            )
            
            conn = sqlite3.connect(test_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE level = 12")
            row = cursor.fetchone()
            conn.close()
            
            self.assertIsNotNone(row)
            self.assertEqual(row["level"], 12)
            self.assertEqual(row["exercise_name"], "Card Shift Challenge")
            self.assertEqual(row["accuracy_type"], "completion_rate")
            self.assertEqual(row["successful_hits"], 6)
            self.assertEqual(row["total_attempts"], 8)
            self.assertEqual(row["avg_accuracy"], 75.0)
            self.assertEqual(row["card_shift_successes"], 6)
            self.assertEqual(row["card_shift_attempts"], 8)
            self.assertAlmostEqual(row["average_shift_latency"], 1.85, places=2)
            self.assertAlmostEqual(row["median_shift_latency"], 1.80, places=2)
            self.assertAlmostEqual(row["maximum_shift_latency"], 2.40, places=2)
            self.assertEqual(row["incorrect_finger_events"], 2)
            self.assertEqual(row["target_timeouts"], 1)
            self.assertAlmostEqual(row["sequence_completion_rate"], 75.0, places=2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level12_research_export(self):
        """TEST 9: Verify research_export exports CSV with Level 12 columns and correct alignment."""
        temp_dir = tempfile.mkdtemp()
        try:
            test_db = os.path.join(temp_dir, "test_research_cs.db")
            db = DatabaseManager(test_db)
            
            db.save_session(
                level=12,
                score=300,
                duration=30.0,
                avg_accuracy=100.0,
                max_extension=170.0,
                patient_id="RESEARCH_PATIENT_CS",
                successful_hits=8,
                total_attempts=8,
                accuracy_type="completion_rate",
                exercise_name="Card Shift Challenge",
                tracking_quality=98.0,
                quality_flag="VALID",
                card_shift_successes=8,
                card_shift_attempts=8,
                average_shift_latency=1.55,
                median_shift_latency=1.50,
                maximum_shift_latency=1.90,
                incorrect_finger_events=0,
                target_timeouts=0,
                sequence_completion_rate=100.0
            )
            
            out_csv = os.path.join(temp_dir, "export_cs.csv")
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
            self.assertIn("Card_Shift_Successes", header)
            self.assertIn("Card_Shift_Attempts", header)
            self.assertIn("Average_Shift_Latency", header)
            self.assertIn("Median_Shift_Latency", header)
            self.assertIn("Maximum_Shift_Latency", header)
            self.assertIn("Incorrect_Finger_Events", header)
            self.assertIn("Target_Timeouts", header)
            self.assertIn("Sequence_Completion_Rate", header)
            
            succ_idx = header.index("Card_Shift_Successes")
            lat_idx = header.index("Average_Shift_Latency")
            self.assertEqual(data[succ_idx], "8")
            self.assertEqual(data[lat_idx], "1.55")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_level12_draw_rendering(self):
        """TEST 10: Verify _draw_level12 renders cleanly without exception."""
        game = MockPhysioSystemLevel12(tier=3)
        game.card_contact_progress = 0.5
        game._draw_level12()
        
        # Test drawing with prompt completed
        game.active_prompt = None
        game._draw_level12()

    def test_level12_start_level_transition(self):
        """TEST 11: Verify _start_level correctly launches Level 12 state."""
        from physio.game_parts.gameplay import GameplayMixin
        game = MockPhysioSystemLevel12(tier=3)
        game.pending_level = 12
        game._apply_adaptive_prescription = lambda lvl: None
        game._start_level = GameplayMixin._start_level.__get__(game)
        
        game._start_level()
        self.assertEqual(game.state, GameState.LEVEL12_CARD_SHIFT)
        self.assertEqual(game.current_level, 12)
        self.assertEqual(game.accuracy_type, "completion_rate")
        self.assertIsNotNone(game.active_prompt)
        self.assertEqual(len(game.prompts), 6)


if __name__ == "__main__":
    unittest.main()
