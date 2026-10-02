"""
Unit tests for Real-time Movement Correctness and Adjustment Feedback across all games.
"""
import unittest
from unittest.mock import MagicMock
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

from physio.models import HandData, GameState
from physio.game_parts.gameplay import GameplayMixin


class MockSystem(GameplayMixin):
    def __init__(self):
        self.state = GameState.LEVEL1_FLEXIBILITY
        self.current_level = 1
        self.correctness_warning = ""
        self.warning_timer = 0
        self.patient_name = "TestPatient"


class TestMovementCorrectnessLabels(unittest.TestCase):
    def setUp(self):
        self.system = MockSystem()

    def test_hand_missing(self):
        empty_hand = HandData()
        label = self.system._get_correctness_label(empty_hand)
        self.assertEqual(label, "Incorrect - hand missing")

    def test_level1_bubble_reach(self):
        self.system.state = GameState.LEVEL1_FLEXIBILITY
        self.system.current_level = 1
        
        # Open hand (reaching for bubbles) - MUST NOT BE FLAGGED AS INCORRECT!
        open_hand = HandData(index_tip=(400, 300), knuckle_angles=[175.0, 172.0, 170.0, 168.0], finger_extension=150.0)
        self.assertEqual(self.system._get_correctness_label(open_hand), "Correct - reach for bubbles")

        # Clenched fist during reaching exercise
        fist_hand = HandData(index_tip=(400, 300), is_fist=True, finger_extension=20.0)
        self.assertEqual(self.system._get_correctness_label(fist_hand), "Adjust - open hand to reach")

    def test_level2_basket_catch(self):
        self.system.state = GameState.LEVEL2_STRENGTH
        self.system.current_level = 2
        
        # Palm catching falling items at standard height
        palm_hand = HandData(index_tip=(400, 500), palm_center=(400, 500))
        self.assertEqual(self.system._get_correctness_label(palm_hand), "Correct - catch falling items")

        # Hand raised too high into spawn area
        high_hand = HandData(index_tip=(400, 80), palm_center=(400, 80))
        self.assertEqual(self.system._get_correctness_label(high_hand), "Adjust - lower hand to basket")

    def test_level3_fine_motor_pinch(self):
        self.system.state = GameState.LEVEL3_FINEMOTOR
        self.system.current_level = 3
        
        # Approaching seed without pinching
        hover_hand = HandData(index_tip=(400, 300), is_pinching=False)
        self.assertEqual(self.system._get_correctness_label(hover_hand), "Ready - pinch seed to pick")

        # Pinching seed
        pinch_hand = HandData(index_tip=(400, 300), is_pinching=True)
        self.assertEqual(self.system._get_correctness_label(pinch_hand), "Correct - pinch grasp active")

    def test_level4_coordination_tracking(self):
        self.system.state = GameState.LEVEL4_COORDINATION
        self.system.current_level = 4
        self.system.target_x = 400
        self.system.target_y = 300
        self.system.target_radius = 50

        # Close to target
        close_hand = HandData(index_tip=(410, 310))
        self.assertEqual(self.system._get_correctness_label(close_hand), "Correct - smooth tracking")

        # Far from target
        far_hand = HandData(index_tip=(600, 300))
        self.assertEqual(self.system._get_correctness_label(far_hand), "Adjust - follow moving target")

    def test_level5_grip_and_release(self):
        self.system.state = GameState.LEVEL5_GRIP_RELEASE
        self.system.current_level = 5

        # Phase 0: Squeeze phase
        self.system.pump_state = 0
        open_hand = HandData(index_tip=(400, 300), is_fist=False, finger_extension=140.0)
        self.assertEqual(self.system._get_correctness_label(open_hand), "Adjust - squeeze into fist")

        fist_hand = HandData(index_tip=(400, 300), is_fist=True, finger_extension=20.0)
        self.assertEqual(self.system._get_correctness_label(fist_hand), "Correct - squeeze detected")

        # Phase 1: Release phase
        self.system.pump_state = 1
        self.assertEqual(self.system._get_correctness_label(fist_hand), "Adjust - open hand fully")
        self.assertEqual(self.system._get_correctness_label(open_hand), "Correct - release detected")

    def test_level7_wrist_mechanics(self):
        self.system.state = GameState.LEVEL7_WRIST_MECHANICS
        self.system.current_level = 7
        self.system.wrist_target_angle = 60.0
        self.system.rotation_tolerance = 25.0
        self.system.wrist_rotation_baseline = 0.0

        # Aligned rotation (current_norm = 30 * 2.0 = 60.0 -> diff = 0)
        aligned_hand = HandData(index_tip=(400, 300), wrist=(400, 400), wrist_rotation_angle=30.0)
        self.assertEqual(self.system._get_correctness_label(aligned_hand), "Correct - holding rotation")

        # Misaligned rotation (current_norm = 90 * 2.0 = 180.0 -> diff = 120 > 25)
        misaligned_hand = HandData(index_tip=(400, 300), wrist=(400, 400), wrist_rotation_angle=90.0)
        self.assertEqual(self.system._get_correctness_label(misaligned_hand), "Adjust - rotate wrist to target")

        # Initial frame before baseline initialized (wrist_rotation_baseline is None)
        self.system.wrist_rotation_baseline = None
        self.assertIn("rotate", self.system._get_correctness_label(aligned_hand).lower())

    def test_level9_precision_path(self):
        self.system.state = GameState.LEVEL9_PRECISION_PATH
        self.system.current_level = 9
        self.system.precision_current_dot = 2

        hand = HandData(index_tip=(300, 200))
        self.assertEqual(self.system._get_correctness_label(hand), "Correct - moving to dot #3")

        # With warning active
        self.system.correctness_warning = "Follow the numbered path carefully"
        self.system.warning_timer = 45
        self.assertEqual(self.system._get_correctness_label(hand), "Adjust - follow dot sequence")

    def test_level10_precision_pathway(self):
        self.system.state = GameState.LEVEL10_PRECISION_PATHWAY
        self.system.current_level = 10
        self.system.pathway_grabbed = False

        hand = HandData(index_tip=(300, 200))
        self.assertEqual(self.system._get_correctness_label(hand), "Ready - touch start marker")

        self.system.pathway_grabbed = True
        self.assertEqual(self.system._get_correctness_label(hand), "Correct - centered in pathway")

        # Off path warning
        self.system.correctness_warning = "PATH DEVIATION"
        self.system.warning_timer = 30
        self.assertEqual(self.system._get_correctness_label(hand), "Adjust - stay inside path")

    def test_level11_coin_vault(self):
        self.system.state = GameState.LEVEL11_COIN_VAULT
        self.system.current_level = 11

        hand = HandData(index_tip=(300, 200), thumb_tip=(320, 200), is_pinching=False)
        self.system.manipulation_state = "READY"
        self.assertEqual(self.system._get_correctness_label(hand), "Ready - pinch coin to pick")

        self.system.manipulation_state = "IN_HAND_TRANSLATION"
        self.assertEqual(self.system._get_correctness_label(hand), "Correct - translate into palm")

        self.system.manipulation_state = "IN_HAND_REPOSITION"
        self.assertEqual(self.system._get_correctness_label(hand), "Correct - reposition coin")

        self.system.manipulation_state = "VAULT_PLACEMENT"
        self.assertEqual(self.system._get_correctness_label(hand), "Correct - place in matching vault")


if __name__ == '__main__':
    unittest.main()
