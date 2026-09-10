"""
Main Game Application (PhysioSystem) for the Zero-Keyboard AI Physiotherapy System.
"""

import cv2
import mediapipe as mp
import pygame
import numpy as np
import sqlite3
import security_utils
import threading
import time
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List
from collections import deque
from datetime import datetime
import os
import io
import pyttsx3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from adaptive_ai_engine import AdaptiveRehabEngine, ForearmExerciseClassifier
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
except ImportError:
    pass

from physio.constants import *
from physio.utils import distance, lerp, weighted_average, recovery_category, functional_recovery_score
from physio.voice import VOICE
from physio.sound import SoundSystem
from physio.particles import ParticleSystem, ScorePopup
from physio.models import (
    GameState, AgeGroup, HandData, AssemblyPart, Bubble, FallingItem, Seed
)
from physio.camera import WebcamStream
from physio.hand_engine import HandEngine
from physio.database import DatabaseManager
from physio.ui_widgets import (
    SelectionRing, LevelButton, HomeIcon, CloseButton, Button, _get_ui_fonts
)
from physio.medical_sidebar import MedicalSidebar, MedicalSidebarV2, PostGameSummary
from physio.clinical import KinematicQualityTracker, AdvancedCompensationDetector

class PhysioSystem:
    """Main application"""
    
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.SCALED)
        pygame.display.set_caption("Zero-Keyboard AI Physiotherapy System")
        self.clock = pygame.time.Clock()
        
        # Cached fonts (NEVER create fonts inside draw loops — causes memory leak/crash)
        self.font_large  = pygame.font.SysFont("segoeui", 54)
        self.font_medium = pygame.font.SysFont("segoeui", 40)
        self.font_head   = pygame.font.SysFont("segoeui", 28)
        self.font_small  = pygame.font.SysFont("segoeui", 22)
        self.font_hud    = pygame.font.SysFont("segoeui", 22)
        self.font_hint   = pygame.font.SysFont("segoeui", 18)
        self.font_tiny   = pygame.font.SysFont("segoeui", 16)
        self.font_cd     = pygame.font.SysFont("segoeui", 32)
        self.font_badge  = pygame.font.SysFont("segoeui", 24)

        # Cursor trail buffer
        self._cursor_trail: list = []
        
        # Components
        self.hand_engine = HandEngine()
        self.db = DatabaseManager()
        self.adaptive_engine = AdaptiveRehabEngine(self.db.db_path)
        self.forearm_classifier = ForearmExerciseClassifier()
        self.quality_tracker = KinematicQualityTracker()
        self.compensation_detector = AdvancedCompensationDetector()
        self.recommended_difficulty = "Moderate"
        self.recommended_difficulty_explanation = "Ready for baseline therapy."
        self.readiness_score = 50.0
        self.current_clinical_summary = ""
        self.current_clinical_recommendation = ""
        self.sidebar = MedicalSidebarV2()
        self.sounds = SoundSystem()
        self.particles = ParticleSystem()
        self.popups: List[ScorePopup] = []
        
        # Privacy & Safety Checks
        security_utils.run_privacy_startup_checks()
        print("Privacy Mode Enabled")
        
        # State
        self.state = GameState.PATIENT_REGISTRATION
        self._last_state = None  # Track state changes for safe mouse warp and safety grace periods
        self._transition_time = 0.0  # Safe grace period timestamp on screen transitions
        self.age_group = None  # Will be set on age selection
        
        # Patient Information
        self.patient_name = ""
        self.patient_age = ""
        self.patient_id_str = ""
        self.input_active = "id"  # default to "id"
        
        self.running = True
        self.session_start = None
        self.score = 0
        self.max_extension = 0.0
        self.reach_distance = 0.0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.active_prescription = None
        self.session_time_limit = LEVEL_DURATION
        self.adaptive_target_scale = 1.0
        self.adaptive_speed_scale = 1.0
        self.adaptive_guidance_level = "standard"
        self.forearm_angle_history = deque(maxlen=90)
        self.forearm_assessment = None
        
        # Visual feedback
        self.combo = 0
        self.feedback_text = None
        self.feedback_timer = 0
        self.screen_shake = 0
        self.shake_offset = (0, 0)

        # Pain scale (before each session)
        self.pain_level = 0          # 0-10 NRS score
        self.pain_before_session = 0
        self.pain_after_session = 0
        self.pain_difference = 0
        self.functional_recovery_score = 0.0
        self.recovery_category = "Not recorded"
        self.pending_level = None    # which level player picked (before pain screen)

        # Power-ups and game modifiers
        self.score_multiplier = 1.0
        self.multiplier_timer = 0
        self.slow_mo = False
        self.slow_mo_timer = 0
        self.shield_active = False
        self.shield_timer = 0
        self.achievements_unlocked = set()
        
        # UI Elements
        # Age selection buttons (4 large cards) centered for 1280 WINDOW_WIDTH
        self.age_buttons = [
            LevelButton(240, 150, 380, 180, "CHILDREN\n5-12 years", 1),
            LevelButton(660, 150, 380, 180, "YOUNG ADULTS\n18-35 years", 2),
            LevelButton(240, 380, 380, 180, "ADULTS\n35-60 years", 3),
            LevelButton(660, 380, 380, 180, "SENIORS\n60+ years", 4)
        ]
        
        cx = GAME_AREA_WIDTH // 2
        bw = 310
        gap = 30
        col1_x = cx - bw - (gap // 2)
        col2_x = cx + (gap // 2)
        self.level_buttons = [
            LevelButton(col1_x, 165, bw, 90, "LEVEL 1", 1, ring_radius=30),
            LevelButton(col2_x, 165, bw, 90, "LEVEL 2", 2, ring_radius=30),
            LevelButton(col1_x, 270, bw, 90, "LEVEL 3", 3, ring_radius=30),
            LevelButton(col2_x, 270, bw, 90, "LEVEL 4", 4, ring_radius=30),
            LevelButton(col1_x, 375, bw, 90, "LEVEL 5", 5, ring_radius=30),
            LevelButton(col2_x, 375, bw, 90, "LEVEL 6", 6, ring_radius=30),
            LevelButton(col1_x, 480, bw, 90, "LEVEL 7", 7, ring_radius=30),
            LevelButton(col2_x, 480, bw, 90, "LEVEL 8", 8, ring_radius=30)
        ]
        # Bottom utility buttons — evenly spaced with smaller rings
        btn_w = 210
        btn_gap = 12
        total_w = btn_w * 3 + btn_gap * 2
        start_x = cx - total_w // 2
        self.history_button = LevelButton(start_x, 585, btn_w, 50, "RECOVERY HISTORY", 9, ring_radius=20)
        self.calibrate_button = LevelButton(start_x + btn_w + btn_gap, 585, btn_w, 50, "ROM DIAGNOSTICS", 8, ring_radius=20)
        self.exit_button = LevelButton(start_x + (btn_w + btn_gap) * 2, 585, btn_w, 50, "EXIT SYSTEM", 99, ring_radius=20)
        self.logout_button = Button(20, 15, 140, 40, "← LOGOUT", (50, 50, 70))
        self.logout_button.duration = 1.2
        self.home_icon = HomeIcon(GAME_AREA_WIDTH - 250, 15, 240, 60)
        
        # Calibration state variables
        self.calibrated_fist_val = 0.12       # default check threshold
        self.calibrated_max_extension = 170.0  # default reach extension in pixels
        self.calibrated_min_angle = 15.0      # min knuckle angle (fist)
        self.calibrated_max_angle = 90.0      # max knuckle angle (open)
        self.calibration_active = False       # whether calibration was completed
        
        # Game objects
        self.bubbles = []
        self.falling_items = []
        self.seeds = []
        self.basket_x = GAME_AREA_WIDTH // 2
        self.basket_y = WINDOW_HEIGHT - 100
        self.pot_x = GAME_AREA_WIDTH // 2
        self.pot_y = WINDOW_HEIGHT - 80
        
        self.trace_t = 0.0
        self.trace_target_x = GAME_AREA_WIDTH // 2
        self.trace_target_y = WINDOW_HEIGHT // 2
        self.trace_path = []
        
        self.pump_state = 0
        self.pump_reps = 0
        self.balloon_scale = 1.0
        
        self.simon_sequence = []
        self.simon_player_idx = 0
        self.simon_state = "START"
        self.simon_timer = 0
        self.simon_show_idx = 0
        self.simon_active_pad = None
        
        self.current_level = 0
        
        # Analytics tracking
        self.angle_history = deque(maxlen=300)  # Track angles for averaging
        
        # Post-game components
        self.summary_screen = PostGameSummary()
        self.quick_start_button = CloseButton(GAME_AREA_WIDTH // 2 - 240, 560, 480, 60)
        self.quick_start_button.duration = 2.0
        
        # Repositioned buttons below AI summary panel to prevent overlap
        btn_y = 608
        bw, bh = 170, 44
        cx = GAME_AREA_WIDTH // 2
        
        self.menu_button  = CloseButton(cx - 360, btn_y, bw, bh)
        self.next_button  = CloseButton(cx - 180, btn_y, bw, bh)
        self.home_button  = CloseButton(cx + 0,   btn_y, bw, bh)
        self.close_button = CloseButton(cx + 180, btn_y, bw, bh)
        
        # Calibration buttons (centered inside left panel: x=20..580, center=300)
        cal_btn_w, cal_btn_h = 280, 52
        cal_btn_x = 20 + (560 - cal_btn_w) // 2  # 160
        self.cal_start_button = CloseButton(cal_btn_x, 470, cal_btn_w, cal_btn_h)
        self.cal_start_button.duration = 1.5
        self.cal_finish_button = CloseButton(cal_btn_x, 470, cal_btn_w, cal_btn_h)
        self.cal_finish_button.duration = 1.5
        
        for b in [self.menu_button, self.next_button, self.home_button, self.close_button]:
            b.duration = 1.2
        self.session_data = None
        self.best_data = None
        self._level_complete_time = 0.0   # set by _end_level
        self.correctness_warning = ""
        self.warning_timer = 0
        self.dashboard_surf = None
        self.dashboard_loading = False
        
        # Virtual Sensei state
        self.last_coach_time = 0
        self.coaching_cooldown = 12.0 # Don't be annoying
        self.streak_counter = 0
        
        # Purge button for history
        self.purge_button = Button(WINDOW_WIDTH - 220, WINDOW_HEIGHT - 60, 200, 45, "PURGE RECORDS", (200, 50, 50))
        self.history_back_button = Button(20, WINDOW_HEIGHT - 60, 150, 45, "← BACK", (40, 60, 100))
        
        # Load and cache top 3 patient profiles for hands-free directory selection
        self._refresh_patient_profiles()

    def _refresh_patient_profiles(self):
        """Query existing patients and construct zero-keyboard buttons for the top 3"""
        self.patient_profile_buttons = {}
        
    def run(self):
        """Main application loop with initial splash screen"""
        try:
            # 1. INITIAL SPLASH SCREEN LOOP (while engine starts)
            loading = True
            start_time = time.time()
            engine_started = False
            engine_ready = False
            engine_error = False
            
            # Status messages for the medical splash
            status_msgs = [
                "BOOTING CLINICAL CORE...",
                "INITIALIZING NEURAL INTERFACE...",
                "CALIBRATING OPTICAL SENSORS...",
                "SYNCING PATIENT DATABASE...",
                "BIO-FEEDBACK ENGINE ONLINE.",
                "SYSTEM READY."
            ]
            
            while loading and self.running:
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        loading = False
                    if event.type == pygame.KEYDOWN and engine_error:
                        # Allow skipping splash if camera failed
                        loading = False
                
                # Start engine
                if not engine_started:
                    self.hand_engine.start()
                    engine_started = True
                
                # Progress
                elapsed = time.time() - start_time
                progress = min(1.0, elapsed / 3.5)
                
                # Readiness check
                engine_ready = False
                engine_error = False
                
                if self.hand_engine.webcam:
                    # Check background initialization status
                    if getattr(self.hand_engine.webcam, 'init_done', False):
                        if getattr(self.hand_engine.webcam, 'init_error', False):
                            engine_error = True
                        else:
                            with self.hand_engine.lock:
                                if self.hand_engine.mirrored_frame is not None:
                                    engine_ready = True
                else:
                    engine_error = True
                
                # Finish loading
                if progress >= 1.0 and engine_ready:
                    loading = False
                # Auto-proceed after 8s even if error (keyboard fallback)
                if engine_error and elapsed > 8.0:
                    loading = False
                
                self._draw_initial_splash(progress, status_msgs, engine_error)
                self.clock.tick(60)

            # Warp the mouse pointer to a safe, empty area (top right) immediately after loading screen
            pygame.mouse.set_pos((WINDOW_WIDTH - 50, 50))

            # 2. MAIN APPLICATION LOOP
            while self.running:
                self._handle_events()
                self._update()
                self._draw()
                self.clock.tick(FPS)
                
        finally:
            self.hand_engine.stop()
            try:
                pygame.mixer.quit()
            except:
                pass
            pygame.quit()

    def _draw_initial_splash(self, progress: float, messages: list, has_error: bool = False):
        """Premium medical-themed startup animation"""
        self.screen.fill((4, 8, 15)) # Deep space black/blue
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        t = time.time()

        # --- Tech Background Grid ---
        grid_color = (15, 25, 40)
        for x in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, WINDOW_HEIGHT), 1)
        for y in range(0, WINDOW_HEIGHT, 40):
            pygame.draw.line(self.screen, grid_color, (0, y), (WINDOW_WIDTH, y), 1)

        # --- Moving Scanline ---
        scan_y = int((t * 200) % WINDOW_HEIGHT)
        pygame.draw.line(self.screen, (0, 150, 100, 60), (0, scan_y), (WINDOW_WIDTH, scan_y), 2)

        # --- Central Neural Hub Animation ---
        # Pulsing Glow
        glow_size = int(150 + 20 * math.sin(t * 4))
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 100, 255, 30), (glow_size, glow_size), glow_size)
        self.screen.blit(glow_surf, (cx - glow_size, cy - glow_size))

        # Rotating Hexagons
        for i in range(3):
            angle = t * (i + 1) * 0.5
            pts = []
            r = 80 + i * 30
            for j in range(6):
                a = angle + j * (math.pi / 3)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            pygame.draw.polygon(self.screen, (0, 200, 255), pts, 2)

        # Inner pulsing core
        core_r = int(40 + 5 * math.sin(t * 8))
        pygame.draw.circle(self.screen, (0, 255, 180), (cx, cy), core_r, 3)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 10)

        # --- Progress Bar ---
        bar_w, bar_h = 400, 10
        bar_x, bar_y = cx - bar_w // 2, cy + 180
        pygame.draw.rect(self.screen, (20, 30, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        pygame.draw.rect(self.screen, (0, 255, 150), (bar_x, bar_y, int(bar_w * progress), bar_h), border_radius=5)
        
        # Glow for bar
        if progress > 0:
            pygame.draw.rect(self.screen, (0, 255, 150), (bar_x, bar_y, int(bar_w * progress), bar_h), 2, border_radius=5)

        # --- Loading Text Log ---
        log_idx = min(int(progress * len(messages)), len(messages) - 1)
        for i in range(log_idx + 1):
            alpha = 255 if i == log_idx else 100
            msg = messages[i]
            if i == log_idx:
                # Add flickering cursor to current line
                if int(t * 4) % 2 == 0: msg += " _"
            
            txt = self.font_hint.render(msg, True, (0, 255, 180))
            txt.set_alpha(alpha)
            self.screen.blit(txt, (50, 50 + i * 25))

        # --- Error Warning ---
        if has_error:
            err_surf = pygame.Surface((500, 100), pygame.SRCALPHA)
            err_surf.fill((100, 0, 0, 180))
            self.screen.blit(err_surf, (WINDOW_WIDTH//2 - 250, WINDOW_HEIGHT - 180))
            pygame.draw.rect(self.screen, (255, 50, 50), (WINDOW_WIDTH//2 - 250, WINDOW_HEIGHT - 180, 500, 100), 2)
            
            e_txt1 = self.font_small.render("CAMERA NOT DETECTED", True, (255, 200, 200))
            e_txt2 = self.font_hint.render("System will run in Keyboard Fallback Mode.", True, (255, 255, 255))
            e_txt3 = self.font_tiny.render("Press any key to continue...", True, (200, 200, 200))
            
            self.screen.blit(e_txt1, e_txt1.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 150)))
            self.screen.blit(e_txt2, e_txt2.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 125)))
            self.screen.blit(e_txt3, e_txt3.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 100)))

        # --- Percentage ---
        pct_txt = self.font_medium.render(f"{int(progress * 100)}%", True, (255, 255, 255))
        self.screen.blit(pct_txt, pct_txt.get_rect(center=(cx, bar_y + 40)))

        # --- Branded Footer ---
        footer = self.font_tiny.render("AI PHYSIOTHERAPY SYSTEM v2.0 | ZERO-KEYBOARD CLINICAL INTERFACE", True, (60, 90, 120))
        self.screen.blit(footer, footer.get_rect(center=(cx, WINDOW_HEIGHT - 30)))

        pygame.display.flip()
    
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Handle keyboard input for patient registration
            elif event.type == pygame.KEYDOWN and self.state == GameState.PATIENT_REGISTRATION:
                if event.key == pygame.K_BACKSPACE:
                    if self.input_active == "name":
                        self.patient_name = self.patient_name[:-1]
                    elif self.input_active == "age":
                        self.patient_age = self.patient_age[:-1]
                    elif self.input_active == "id":
                        self.patient_id_str = self.patient_id_str[:-1]
                elif event.key == pygame.K_TAB:
                    # Switch between fields
                    if self.input_active == "id": self.input_active = "name"
                    elif self.input_active == "name": self.input_active = "age"
                    else: self.input_active = "id"
                elif event.key == pygame.K_RETURN:
                    # Submit if ID is provided OR (name and age) are provided
                    if self.patient_id_str or (self.patient_name and self.patient_age):
                        self._submit_registration()
                else:
                    # Add character to active field
                    if self.input_active == "name" and len(self.patient_name) < 30:
                        if event.unicode.isprintable():
                            self.patient_name += event.unicode
                    elif self.input_active == "age" and len(self.patient_age) < 3:
                        if event.unicode.isdigit():
                            self.patient_age += event.unicode
                    elif self.input_active == "id" and len(self.patient_id_str) < 30:
                        if event.unicode.isprintable():
                            self.patient_id_str += event.unicode
                            
            # Therapist Dashboard shortcut
            elif event.type == pygame.KEYDOWN and self.state == GameState.MAIN_MENU:
                if event.key == pygame.K_F12:
                    self.state = GameState.THERAPIST_DASHBOARD
                    try: self.sounds.play('select')
                    except: pass
    
    def _update(self):
        # Check if state has transitioned to safely warp the mouse cursor and reset button hover clocks
        if self.state != self._last_state:
            # Warp the mouse pointer to a safe, empty area (top right inside the medical sidebar)
            pygame.mouse.set_pos((WINDOW_WIDTH - 50, 50))
            
            # Reset all button hover timers so the next screen starts completely fresh
            self._reset_all_button_hovers()
            
            # Update last state tracker and record transition time for safety grace period
            self._last_state = self.state
            self._transition_time = time.time()

        hand_data = self.hand_engine.get_hand_data()
        
        # Enforce 2.0-second safety grace period after transition to prevent accidental selections
        if time.time() - getattr(self, '_transition_time', 0.0) < 2.0:
            from copy import copy
            hand_data = copy(hand_data)
            hand_data.index_tip = None
        
        # Track max extension and angles
        if hand_data.finger_extension > 0:
            self.max_extension = max(self.max_extension, hand_data.finger_extension)
            
        # Virtual Sensei AI Coaching
        self._run_virtual_sensei(hand_data)
        
        if hand_data.knuckle_angles and len(hand_data.knuckle_angles) > 0:
            self.angle_history.append(hand_data.knuckle_angles[0])
            # Real-time Correctness Detection inside gameplay
            if self.state in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, GameState.LEVEL3_FINEMOTOR]:
                angle = hand_data.knuckle_angles[0]
                if angle > 165 and not hand_data.is_pinching: # Not bending enough
                    if self.warning_timer <= 0:
                        self.correctness_warning = "Bend fingers slightly more"
                        VOICE.speak("Bend fingers slightly more")
                        self.warning_timer = 120 # warn ~2s apart
                elif angle < 120:
                    if self.correctness_warning == "Bend fingers slightly more" and self.warning_timer <= 60:
                        self.correctness_warning = "Good job"
                        VOICE.speak("Good job")
                        self.warning_timer = 180 # Stay at "good job" for 3s
                if self.warning_timer > 0:
                    self.warning_timer -= 1
                elif self.warning_timer <= 0:
                    self.correctness_warning = ""
        
        # Check home icon (pause/quit) - Double-Trigger Exit
        if self.state not in [GameState.MAIN_MENU, GameState.RESULTS,
                               GameState.LEVEL_COMPLETE, GameState.PAIN_SCALE,
                               GameState.HISTORY, GameState.PATIENT_REGISTRATION,
                               GameState.AGE_SELECT, GameState.CLOUD_SYNC, GameState.THERAPIST_DASHBOARD]:
            
            # Check if we are in an active gameplay level where making a fist is part of the therapy
            gameplay_states = [
                GameState.LEVEL1_FLEXIBILITY,
                GameState.LEVEL2_STRENGTH,
                GameState.LEVEL3_FINEMOTOR,
                GameState.LEVEL4_COORDINATION,
                GameState.LEVEL5_GRIP_RELEASE,
                GameState.LEVEL6_FINGER_TAPS,
                GameState.LEVEL7_WRIST_MECHANICS,
                GameState.LEVEL8_SMART_ASSEMBLY
            ]
            is_gameplay = self.state in gameplay_states
            
            # Trigger 1: Hover-to-Select on HomeIcon (disable global fist trigger during active gameplay or calibration)
            fist_trigger_disabled = is_gameplay or (self.state == GameState.CALIBRATION)
            home_hover_exit = self.home_icon.update(False if fist_trigger_disabled else hand_data.is_fist, hand_data.index_tip)
            
            # Trigger 2: Global Fist hold countdown anywhere on the screen (disabled during active gameplay or calibration)
            global_fist_exit = False
            if not is_gameplay and self.state != GameState.CALIBRATION and hand_data.is_fist:
                if not hasattr(self, '_global_fist_start') or self._global_fist_start is None:
                    self._global_fist_start = time.time()
                elapsed = time.time() - self._global_fist_start
                if elapsed >= 2.0:
                    global_fist_exit = True
                    self._global_fist_start = None
            else:
                self._global_fist_start = None
                
            if home_hover_exit or global_fist_exit:
                self.state = GameState.MAIN_MENU
                self._reset_game()
                self._global_fist_start = None
        
        # Check tracking & Freeze Timer
        is_playing = self.state in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, 
                                    GameState.LEVEL3_FINEMOTOR, GameState.LEVEL4_COORDINATION,
                                    GameState.LEVEL5_GRIP_RELEASE, GameState.LEVEL6_FINGER_TAPS]
        
        now = time.time()
        dt = now - getattr(self, '_last_update_time', now)
        self._last_update_time = now

        if is_playing and hand_data.index_tip is None:
            self.tracking_lost = True
            # Freeze the game timer by advancing session_start
            if self.session_start is not None:
                self.session_start += dt
        else:
            self.tracking_lost = False
            if is_playing:
                self.game_has_started = True
            
        # State machine
        if self.state == GameState.PATIENT_REGISTRATION:
            self._update_patient_registration(hand_data)
        elif self.state == GameState.AGE_SELECT:
            self._update_age_select(hand_data)
        elif self.state == GameState.MAIN_MENU:
            self._update_menu(hand_data)
        elif self.state == GameState.PAIN_SCALE:
            self._update_pain_scale(hand_data)
        elif self.state == GameState.PAIN_AFTER_SESSION:
            self._update_pain_scale(hand_data)
        elif self.state == GameState.HISTORY:
            self._update_history(hand_data)
        elif self.state == GameState.CALIBRATION:
            self._update_calibration(hand_data)
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            if not getattr(self, 'tracking_lost', False):
                self._update_level1(hand_data)
        elif self.state == GameState.LEVEL2_STRENGTH:
            if not getattr(self, 'tracking_lost', False):
                self._update_level2(hand_data)
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            if not getattr(self, 'tracking_lost', False):
                self._update_level3(hand_data)
        elif self.state == GameState.LEVEL4_COORDINATION:
            if not getattr(self, 'tracking_lost', False):
                self._update_level4(hand_data)
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            if not getattr(self, 'tracking_lost', False):
                self._update_level5(hand_data)
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            if not getattr(self, 'tracking_lost', False):
                self._update_level6(hand_data)
        elif self.state == GameState.LEVEL7_WRIST_MECHANICS:
            if not getattr(self, 'tracking_lost', False):
                self._update_level7(hand_data)
        elif self.state == GameState.LEVEL8_SMART_ASSEMBLY:
            if not getattr(self, 'tracking_lost', False):
                self._update_level8(hand_data)
        elif self.state == GameState.LEVEL_COMPLETE:
            if time.time() - self._level_complete_time > 2.5:
                self.state = GameState.RESULTS
        elif self.state == GameState.RESULTS:
            self._update_results(hand_data)
        elif self.state == GameState.CLOUD_SYNC:
            if time.time() - getattr(self, 'sync_start', 0) > 2.5:
                self.state = GameState.MAIN_MENU
                self._reset_game()
        elif self.state == GameState.THERAPIST_DASHBOARD:
            self._update_therapist_dashboard(hand_data)
            if self.admin_back_button.update(hand_data.index_tip) or (hand_data.is_fist and self.home_icon.update(True, hand_data.index_tip)):
                self.state = GameState.MAIN_MENU
                    
        # Update visual effects
        self.particles.update()
        self.popups = [p for p in self.popups if p.update()]
        
        # Update power-up timers
        if self.multiplier_timer > 0:
            self.multiplier_timer -= 1
            if self.multiplier_timer == 0:
                self.score_multiplier = 1.0
        
        if self.slow_mo_timer > 0:
            self.slow_mo_timer -= 1
            if self.slow_mo_timer == 0:
                self.slow_mo = False
                
        if self.shield_timer > 0:
            self.shield_timer -= 1
            if self.shield_timer == 0:
                self.shield_active = False
        
        # Update feedback timer
        if self.feedback_timer > 0:
            self.feedback_timer -= 1
            if self.feedback_timer == 0:
                self.feedback_text = None
        
        # Update screen shake
        if self.screen_shake > 0:
            self.screen_shake -= 1
            shake_amount = self.screen_shake // 2
            self.shake_offset = (random.randint(-shake_amount, shake_amount), 
                                random.randint(-shake_amount, shake_amount))
        else:
            self.shake_offset = (0, 0)
        self._run_clinical_analysis(hand_data)
    
    def _update_age_select(self, hand_data: HandData):
        """Handle age group selection"""
        for i, button in enumerate(self.age_buttons):
            if button.update(hand_data.index_tip):
                # Set age group based on button index
                age_groups = [AgeGroup.CHILD, AgeGroup.YOUNG_ADULT, AgeGroup.ADULT, AgeGroup.SENIOR]
                self.age_group = age_groups[i]
                self.state = GameState.MAIN_MENU
                self.sounds.play('select')
                print(f"Selected age group: {self.age_group.value}")
                break
    
    def _update_patient_registration(self, hand_data: HandData):
        if hasattr(self, 'quick_start_button'):
            if self.quick_start_button.update(hand_data.index_tip):
                if not self.patient_name or not self.patient_age:
                    self.patient_name = "Quick Guest"
                    self.patient_age = "30"
                self._submit_registration()
                self.quick_start_button.hover_start = None
                return

        # Update existing profile selection buttons if they exist
        if hasattr(self, 'patient_profile_buttons') and self.patient_profile_buttons:
            for p_name, btn in list(self.patient_profile_buttons.items()):
                if btn.update(hand_data.index_tip):
                    # Load this patient profile!
                    p_data = self.db.get_patient(p_name)
                    if p_data:
                        self.patient_name = p_name
                        self.patient_age = str(p_data['age'])
                        self.age_group = AgeGroup(p_data['age_group'])
                        
                        # Load calibration thresholds if they exist and are active
                        if p_data.get('cal_active', 0):
                            self.calibrated_fist_val = p_data.get('cal_fist_val', 0.12)
                            self.calibrated_max_extension = p_data.get('cal_max_ext', 170.0)
                            self.calibrated_min_angle = p_data.get('cal_min_ang', 15.0)
                            self.calibrated_max_angle = p_data.get('cal_max_ang', 90.0)
                            
                            # Update HandEngine
                            self.hand_engine.fist_threshold = self.calibrated_fist_val
                            self.hand_engine.calibrated_max_extension = self.calibrated_max_extension
                            self.hand_engine.calibration_active = True
                            self.calibration_active = True
                            print(f"[SUCCESS] Dynamic Calibration Loaded from DB: Fist={self.calibrated_fist_val}, MaxExt={self.calibrated_max_extension}")
                        else:
                            self.calibration_active = False
                        
                        VOICE.speak(f"Welcome back {self.patient_name}. Patient profile loaded successfully.")
                        btn.hover_start = None
                        self.state = GameState.MAIN_MENU
                        self._update_readiness_and_difficulty()
                        self.sounds.play('select')
                        break

    def _submit_registration(self):
        """Process patient registration and auto-assign age group"""
        # 1. Check if ID Number is provided
        if self.patient_id_str.strip():
            existing_p = self.db.get_patient_by_id(self.patient_id_str.strip())
            if existing_p:
                self.patient_name = existing_p['name']
                self.patient_age = str(existing_p['age'])
                self.age_group = AgeGroup(existing_p['age_group'])
                if existing_p.get('cal_active', 0):
                    self.calibrated_fist_val = existing_p.get('cal_fist_val', 0.12)
                    self.calibrated_max_extension = existing_p.get('cal_max_ext', 170.0)
                    self.calibrated_min_angle = existing_p.get('cal_min_ang', 15.0)
                    self.calibrated_max_angle = existing_p.get('cal_max_ang', 90.0)
                    self.hand_engine.fist_threshold = self.calibrated_fist_val
                    self.hand_engine.calibrated_max_extension = self.calibrated_max_extension
                    self.hand_engine.calibration_active = True
                    self.calibration_active = True
                self.state = GameState.MAIN_MENU
                self._update_readiness_and_difficulty()
                self.sounds.play('select')
                print(f"Logged in via ID: {self.patient_id_str}")
                return
            else:
                print(f"No profile found for ID: {self.patient_id_str}")
                # Clear invalid ID and return
                self.patient_id_str = ""
                return

        # 2. Name + Age fallback
        try:
            age = int(self.patient_age)
            
            # Auto-assign age group based on age
            if age <= 12:
                self.age_group = AgeGroup.CHILD
            elif age <= 35:
                self.age_group = AgeGroup.YOUNG_ADULT
            elif age <= 60:
                self.age_group = AgeGroup.ADULT
            else:
                self.age_group = AgeGroup.SENIOR
            
            # Query if patient already exists in DB to prevent overwriting settings
            existing_p = self.db.get_patient(self.patient_name)
            if existing_p:
                # Load profile settings
                self.patient_age = str(existing_p['age'])
                self.age_group = AgeGroup(existing_p['age_group'])
                if existing_p.get('cal_active', 0):
                    self.calibrated_fist_val = existing_p.get('cal_fist_val', 0.12)
                    self.calibrated_max_extension = existing_p.get('cal_max_ext', 170.0)
                    self.calibrated_min_angle = existing_p.get('cal_min_ang', 15.0)
                    self.calibrated_max_angle = existing_p.get('cal_max_ang', 90.0)
                    
                    self.hand_engine.fist_threshold = self.calibrated_fist_val
                    self.hand_engine.calibrated_max_extension = self.calibrated_max_extension
                    self.hand_engine.calibration_active = True
                    self.calibration_active = True
                    print(f"[SUCCESS] Existing Patient Calibration Loaded: Fist={self.calibrated_fist_val}, MaxExt={self.calibrated_max_extension}")
            else:
                # Save new profile to DB
                self.db.save_patient(self.patient_name, age, self.age_group.value, id_number=self.patient_id_str.strip() or None)
                # Refresh local top-3 profile buttons
                self._refresh_patient_profiles()

            print(f"Patient: {self.patient_name}, Age: {age}, Group: {self.age_group.value}")
            self.state = GameState.MAIN_MENU
            self._update_readiness_and_difficulty()
            self.sounds.play('select')
        except ValueError:
            print("Invalid age entered")
    
    def _reset_all_button_hovers(self):
        """Reset all button hover progress timers on the screen to prevent accidental activations"""
        button_containers = [
            getattr(self, 'level_buttons', []),
            getattr(self, 'age_buttons', []),
            getattr(self, 'patient_profile_buttons', {}).values() if hasattr(self, 'patient_profile_buttons') else [],
        ]
        
        single_buttons = [
            getattr(self, 'quick_start_button', None),
            getattr(self, 'exit_button', None),
            getattr(self, 'calibrate_button', None),
            getattr(self, 'history_button', None),
            getattr(self, 'home_icon', None),
            getattr(self, 'close_button', None),
            getattr(self, 'menu_button', None),
            getattr(self, 'home_button', None),
            getattr(self, 'next_button', None),
            getattr(self, 'cal_start_button', None),
            getattr(self, 'cal_finish_button', None),
            getattr(self, 'history_back_button', None),
            getattr(self, 'purge_button', None),
            getattr(self, 'admin_back_button', None),
            getattr(self, 'admin_purge_button', None)
        ]
        
        for container in button_containers:
            for btn in container:
                if btn and hasattr(btn, 'ring') and btn.ring:
                    btn.ring.hover_start = None
                    
        for btn in single_buttons:
            if btn:
                if hasattr(btn, 'ring') and btn.ring:
                    btn.ring.hover_start = None

    def _update_menu(self, hand_data: HandData):
        if hasattr(self, 'logout_button') and self.logout_button.update(hand_data.index_tip):
            self.state = GameState.PATIENT_REGISTRATION
            self.patient_name = ""
            self.patient_age = ""
            self.input_active = "name"
            self.pain_checked = False
            self.calibration_active = False
            self.calibrated_fist_val = 0.12
            self.calibrated_max_extension = 170.0
            self.calibrated_min_angle = 15.0
            self.calibrated_max_angle = 90.0
            self.sounds.play('pop')
            return

        if hasattr(self, 'exit_button') and self.exit_button.update(hand_data.index_tip):
            self.running = False
            return
            
        # Calibration button
        if hasattr(self, 'calibrate_button') and self.calibrate_button.update(hand_data.index_tip):
            self.state = GameState.CALIBRATION
            self._init_calibration()
            self.sounds.play('select')
            return

        # History button
        if self.history_button.update(hand_data.index_tip):
            self.state = GameState.HISTORY
            self.dashboard_surf = None
            self.dashboard_loading = True
            self.sounds.play('select')
            
            # Load dashboard chart asynchronously in a background thread to prevent UI freezing
            def load_async():
                try:
                    surf = self.db.render_matplotlib_dashboard(self.patient_name)
                    self.dashboard_surf = surf
                except Exception as e:
                    print(f"Failed loading async chart: {e}")
                finally:
                    self.dashboard_loading = False
            
            threading.Thread(target=load_async, daemon=True).start()
            return
            
        for button in self.level_buttons:
            if button.update(hand_data.index_tip):
                self.current_level = button.level_num
                self.pending_level = button.level_num
                self.sounds.play('select')
                if not getattr(self, 'pain_checked', False):
                    self.pain_level = 0  # reset pain before pain screen
                    self.state = GameState.PAIN_SCALE  # show pain scale first
                else:
                    self._start_level()
                break
    
    def _update_level1(self, hand_data: HandData):
        """Level 1: Pop the Bubbles (Flexibility)"""
        # Safety: ensure bubbles exist
        if not self.bubbles:
            self._spawn_bubbles()
            return

        # Move bubbles
        for bubble in self.bubbles:
            if not bubble.popped:
                bubble.x += bubble.vx
                bubble.y += bubble.vy
                if bubble.x < bubble.radius or bubble.x > GAME_AREA_WIDTH - bubble.radius:
                    bubble.vx *= -1
                if bubble.y < bubble.radius or bubble.y > WINDOW_HEIGHT - bubble.radius:
                    bubble.vy *= -1

        if hand_data.index_tip:
            for bubble in self.bubbles:
                if not bubble.popped:
                    dist = distance(hand_data.index_tip, (bubble.x, bubble.y))
                    if dist < bubble.radius:
                        bubble.popped = True
                        self.accuracy_attempts += 1   # count per bubble, not per frame
                        self.accuracy_hits += 1
                        points = int(10 * self.score_multiplier * (3 if bubble.is_golden else 1))
                        self.score += points
                        self.combo += 1
                        self._trigger_feedback()
                        self.sounds.play('pop')
                        color = (255, 215, 0) if bubble.is_golden else COLOR_BUBBLE
                        self.particles.emit(int(bubble.x), int(bubble.y), color, 20 if bubble.is_golden else 15)
                        self.popups.append(ScorePopup(bubble.x, bubble.y - 20, f"+{points}"))
                        if hand_data.wrist:
                            reach = distance(hand_data.wrist, (bubble.x, bubble.y))
                            self.reach_distance = max(self.reach_distance, reach)

        # Check if all bubbles popped (only when list is non-empty)
        if (self.bubbles and all(b.popped for b in self.bubbles)) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self._end_level()
    
    def _update_level2(self, hand_data: HandData):
        """Level 2: The Basket (Strength)"""
        # Smooth basket movement
        if hand_data.palm_center:
            self.basket_x = hand_data.palm_center[0]
        
        speed_mult = 0.5 if self.slow_mo else 1.0
        
        # Update falling items
        for item in self.falling_items[:]:
            item.y += item.speed * speed_mult * getattr(self, 'pacing_multiplier', 1.0) * getattr(self, 'adaptive_speed_scale', 1.0)
            
            # Check collision with basket
            if (item.y >= self.basket_y - 20 and 
                item.y <= self.basket_y + 20 and
                abs(item.x - self.basket_x) < 75):
                
                self.falling_items.remove(item)
                
                if item.is_bomb:
                    if self.shield_active:
                        self.shield_active = False
                        self.shield_timer = 0
                        self.sounds.play('pop')
                        self.particles.emit(int(item.x), self.basket_y, (0, 200, 255), 25)
                        self.popups.append(ScorePopup(item.x, self.basket_y - 30, "DEFLECTED!"))
                    else:
                        # Bomb! Lose points and combo
                        self.score = max(0, self.score - 10)
                        self.combo = 0
                        self.sounds.play('pop')  # Different sound
                        self.particles.emit(int(item.x), self.basket_y, (255, 0, 0), 20)
                        self.popups.append(ScorePopup(item.x, self.basket_y - 30, "-10"))
                elif item.is_powerup:
                    # Power-up! 2x multiplier
                    self.score_multiplier = 2.0
                    self.multiplier_timer = 300  # 5 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (255, 215, 0), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "2X!"))
                elif getattr(item, 'is_shield', False):
                    self.shield_active = True
                    self.shield_timer = 600  # 10 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (0, 200, 255), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "SHIELD!"))
                elif getattr(item, 'is_freeze', False):
                    self.slow_mo = True
                    self.slow_mo_timer = 300  # 5 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (100, 255, 255), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "FREEZE!"))
                else:
                    # Normal item caught — count as hit
                    points = int(15 * self.score_multiplier)
                    self.score += points
                    self.accuracy_hits += 1
                    self.accuracy_attempts += 1  # Count attempt only when item resolves
                    self.combo += 1
                    self.consecutive_misses = 0 # reset misses on hit
                    if self.combo > 0 and self.combo % 8 == 0:
                        self._adjust_pacing("fast")
                    self._trigger_feedback()
                    self.sounds.play('catch')
                    self.particles.emit(int(item.x), self.basket_y, COLOR_SUCCESS, 10)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, f"+{points}"))
            
            elif item.y > WINDOW_HEIGHT:
                self.falling_items.remove(item)
                if not item.is_bomb and not item.is_powerup and not getattr(item, 'is_shield', False) and not getattr(item, 'is_freeze', False):
                    self.accuracy_attempts += 1  # Missed a catchable item
                    self.combo = 0  # Reset combo on miss (but not for bombs/powerups)
                    self.consecutive_misses += 1
                    if self.consecutive_misses >= 3:
                        self.consecutive_misses = 0
                        self._adjust_pacing("slow")
        
        # Spawn new items
        if len(self.falling_items) < 3 and random.random() < 0.02:
            self._spawn_falling_item()
        
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self._end_level()
    
    def _update_level3(self, hand_data: HandData):
        """Level 3: Pinch & Drop (Fine Motor)"""
        # Update seeds
        for seed in self.seeds[:]:
            if not seed.grabbed:
                seed.y += seed.speed * getattr(self, 'pacing_multiplier', 1.0) * getattr(self, 'adaptive_speed_scale', 1.0)
                
                # Check pinch grab
                if hand_data.is_pinching and hand_data.index_tip:
                    dist = distance(hand_data.index_tip, (seed.x, seed.y))
                    if dist < seed.radius + 35:  # Easier grab radius
                        seed.grabbed = True
                        self.accuracy_attempts += 1
            else:
                # Follow cursor
                if hand_data.index_tip:
                    seed.x = hand_data.index_tip[0]
                    seed.y = hand_data.index_tip[1]
                    
                    # Check drop in pot
                    if not hand_data.is_pinching:
                        pot_dist = distance((seed.x, seed.y), (self.pot_x, self.pot_y))
                        if pot_dist < 60:
                            points = int(25 * self.score_multiplier * (3 if seed.is_golden else 1))
                            self.score += points
                            self.accuracy_hits += 1
                            self.combo += 1
                            self.consecutive_misses = 0 # reset misses on pot success
                            if self.combo > 0 and self.combo % 6 == 0:
                                self._adjust_pacing("fast")
                            self._trigger_feedback()
                            self.sounds.play('catch')
                            color = (255, 215, 0) if seed.is_golden else COLOR_SUCCESS
                            self.particles.emit(self.pot_x, self.pot_y, color, 18 if seed.is_golden else 12)
                            self.popups.append(ScorePopup(self.pot_x, self.pot_y - 40, f"+{points}"))
                        else:
                            self.combo = 0  # Reset on miss
                        self.seeds.remove(seed)
            
            # Remove if off screen
            if seed.y > WINDOW_HEIGHT and not seed.grabbed:
                self.seeds.remove(seed)
                self.combo = 0 # Missed a seed
                self.consecutive_misses += 1
                if self.consecutive_misses >= 3:
                    self.consecutive_misses = 0
                    self._adjust_pacing("slow")
        
        # Spawn new seeds
        if len(self.seeds) < 2 and random.random() < 0.015:
            self._spawn_seed()
        
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self._end_level()

    def _update_level4(self, hand_data: HandData):
        """Level 4: Tracing / Coordination (Hand Stability)"""
        # Time-based movement for the target (Figure 8 pattern)
        theme = self._get_theme()
        speed_mult = theme.get("speed_multiplier", 1.0)
        self.trace_t += 0.008 * speed_mult * getattr(self, 'pacing_multiplier', 1.0) * getattr(self, 'adaptive_speed_scale', 1.0)
        
        # Figure 8 (Lissajous curve) parameters
        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        a = 180 # width scale (was 300)
        b = 90 # height scale (was 150)
        
        # Calculate target position
        self.trace_target_x = cx + a * math.sin(self.trace_t)
        self.trace_target_y = cy + b * math.sin(2 * self.trace_t)
        
        # Store path for drawing
        self.trace_path.append((self.trace_target_x, self.trace_target_y))
        if len(self.trace_path) > 100:
            self.trace_path.pop(0)
            
        # Check tracing accuracy
        if hand_data.index_tip:
            dist = distance(hand_data.index_tip, (self.trace_target_x, self.trace_target_y))
            
            # Record every few frames for accuracy
            if int(self.trace_t * 100) % 5 == 0:
                self.accuracy_attempts += 1
                self.recent_tracing_attempts += 1
                if dist < 85 * getattr(self, 'adaptive_target_scale', 1.0): # Good trace radius (was 60)
                    self.accuracy_hits += 1
                    self.recent_tracing_hits += 1
                    self.score += int(5 * self.score_multiplier)
                    
                    if dist < 45 * getattr(self, 'adaptive_target_scale', 1.0): # Perfect trace (was 30)
                        self.combo += 1
                        self.particles.emit(int(self.trace_target_x), int(self.trace_target_y), COLOR_SUCCESS, 2)
                else:
                    self.combo = 0 # Lost combo
                
                # Check dynamic pacing every 15 checks
                if self.recent_tracing_attempts >= 15:
                    ratio = self.recent_tracing_hits / self.recent_tracing_attempts
                    if ratio >= 0.85 and self.pacing_multiplier < 1.3:
                        self._adjust_pacing("fast")
                    elif ratio < 0.50 and self.pacing_multiplier > 0.6:
                        self._adjust_pacing("slow")
                    self.recent_tracing_attempts = 0
                    self.recent_tracing_hits = 0
            
            # Trigger feedback occasionally
            if self.combo > 0 and self.combo % 20 == 0 and int(self.trace_t * 100) % 5 == 0:
                self._trigger_feedback()
                self.sounds.play('catch')
                self.popups.append(ScorePopup(self.trace_target_x, self.trace_target_y - 40, "SMOOTH!"))
                
        # End after 30 seconds or wall-clock safety ceiling
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self._end_level()

    def _update_level5(self, hand_data: HandData):
        """Level 5: Grip & Release (Spasticity Pump)"""
        # Constantly deflate slowly (deflation rate adapts to pacing)
        if self.balloon_scale > 1.0:
            self.balloon_scale -= 0.005 * getattr(self, 'pacing_multiplier', 1.0)
            
        # If no rep completed for 8 seconds, slow down the deflation rate (make it easier)
        if not hasattr(self, 'last_rep_time'):
            self.last_rep_time = time.time()
            
        if hand_data.is_fist and self.pump_state == 0:
            self.pump_state = 1
            self.balloon_scale = max(0.5, self.balloon_scale - 0.2)
            self.sounds.play('catch')
        elif not hand_data.is_fist and hand_data.finger_extension > 120 and self.pump_state == 1:
            self.pump_state = 0
            self.pump_reps += 1
            self.accuracy_hits += 1
            self.accuracy_attempts += 1
            self.combo += 1
            self.last_rep_time = time.time() # Reset trigger timer on success
            if self.combo > 0 and self.combo % 3 == 0:
                self._adjust_pacing("fast")
            self.balloon_scale = min(2.0, self.balloon_scale + 0.5)
            self.score += int(15 * self.score_multiplier)
            self.sounds.play('pop')
            self.particles.emit(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2, COLOR_SUCCESS, 15)
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2 - 50, "+1 REP!"))
            
            if self.combo % 3 == 0:
                self._trigger_feedback()
                
        if time.time() - self.last_rep_time > 8.0:
            self.last_rep_time = time.time() # Reset trigger timer
            if self.pacing_multiplier > 0.6:
                self._adjust_pacing("slow")
                
        # End after 30 seconds
        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self.accuracy_attempts = max(self.accuracy_attempts, 5) # Provide base attempts
            self._end_level()

    def _update_level6(self, hand_data: HandData):
        """Level 6: Memory Sequence (Cognitive Motor)"""
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        pads = {
            1: (cx - 150, cy - 80),
            2: (cx + 150, cy - 80),
            3: (cx - 150, cy + 120),
            4: (cx + 150, cy + 120)
        }
        
        if self.simon_state == "START":
            self.simon_sequence = [random.randint(1, 4)]
            self.simon_state = "SHOW"
            self.simon_timer = time.time()
            self.simon_show_idx = 0
            self.simon_active_pad = None
            
        elif self.simon_state == "SHOW":
            t = time.time() - self.simon_timer
            # Every 1 second, show the next pad
            if t > 0.8:
                if self.simon_show_idx < len(self.simon_sequence):
                    self.simon_active_pad = self.simon_sequence[self.simon_show_idx]
                    self.sounds.play('pop')
                    self.simon_show_idx += 1
                    self.simon_timer = time.time()
                elif t > 1.2:
                    self.simon_active_pad = None
                    self.simon_state = "PLAY"
                    self.simon_player_idx = 0
                    self.popups.append(ScorePopup(cx, cy - 200, "YOUR TURN!", (0, 255, 255)))
            elif t > 0.4:
                self.simon_active_pad = None # brief pause between flashes
                
        elif self.simon_state == "PLAY":
            if not hand_data.index_tip: return
            hx, hy = hand_data.index_tip
            
            # Check collisions with pads
            hovered_pad = None
            for p_id, (px, py) in pads.items():
                if distance((hx, hy), (px, py)) < 75:
                    hovered_pad = p_id
                    break
                    
            if hovered_pad:
                if getattr(self, '_last_hover', None) != hovered_pad:
                    self._last_hover = hovered_pad
                    self._hover_start = time.time()
                elif time.time() - self._hover_start > 0.4: # 0.4s hover to select
                    self.simon_active_pad = hovered_pad
                    self.sounds.play('catch')
                    
                    if hovered_pad == self.simon_sequence[self.simon_player_idx]:
                        # Correct!
                        self.simon_player_idx += 1
                        self.accuracy_hits += 1
                        self.accuracy_attempts += 1
                        self.score += int(10 * self.score_multiplier)
                        self.particles.emit(pads[hovered_pad][0], pads[hovered_pad][1], COLOR_SUCCESS, 10)
                        
                        if self.simon_player_idx >= len(self.simon_sequence):
                            # Sequence complete!
                            self.popups.append(ScorePopup(cx, cy, "CORRECT!", COLOR_SUCCESS))
                            self.simon_sequence.append(random.randint(1, 4))
                            self.simon_state = "SHOW"
                            self.simon_timer = time.time() + 1.0 # Pause before showing next
                            self.simon_show_idx = 0
                            self.simon_active_pad = None
                            self.combo += 1
                            if self.combo % 2 == 0:
                                self._trigger_feedback()
                    else:
                        # Wrong!
                        self.accuracy_attempts += 1
                        self.popups.append(ScorePopup(cx, cy, "WRONG!", COLOR_WARNING))
                        self.simon_state = "START"
                        self.combo = 0
                    
                    self._last_hover = None
            else:
                self._last_hover = None
                self.simon_active_pad = None

        if (time.time() - self.session_start > self.session_time_limit) or (time.time() - getattr(self, 'level_wall_start', 0.0) > self.session_time_limit * 1.5):
            self.accuracy_attempts = max(self.accuracy_attempts, 5)
            self._end_level()


    def _update_level7(self, hand_data: HandData):
        """Level 7: Rotation Orbit (Forearm Pronation/Supination)"""
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        if not getattr(self, 'wrist_mode', None):
            self.wrist_mode = "rotation"
            self.wrist_target_angle = 45.0 # Starting orbital target
            self.wrist_hold_time = 0.0

        if not hand_data.index_tip or not hand_data.wrist: return
        
        if getattr(self, "wrist_rotation_baseline", None) is None:
            self.wrist_rotation_baseline = hand_data.wrist_rotation_angle

        relative_rotation = hand_data.wrist_rotation_angle - self.wrist_rotation_baseline
        # Map patient movement relative to their starting posture. This keeps
        # Level 7 hand-only and avoids camera/hand-label dependent absolute angles.
        current_angle = relative_rotation * 2.0
        self.forearm_angle_history.append(hand_data.wrist_rotation_angle)
        self.forearm_assessment = self.forearm_classifier.classify(
            hand_data.wrist_rotation_angle,
            self.forearm_angle_history,
            getattr(hand_data, 'wrist_deviation_angle', 0.0),
            getattr(self, 'wrist_hold_time', 0.0),
        )
        
        # Normalize angles to 0-360 for comparison
        target_norm = self.wrist_target_angle % 360
        current_norm = current_angle % 360
        
        diff = abs(current_norm - target_norm)
        if diff > 180: diff = 360 - diff
        
        if diff < getattr(self, 'rotation_tolerance', 25.0): # tolerance adapts for "locking on"
            self.wrist_hold_time += 1/30.0
            if self.wrist_hold_time > getattr(self, 'rotation_hold_required', 1.5):
                # Success!
                self.score += int(15 * getattr(self, 'score_multiplier', 1.0))
                self.accuracy_hits += 1
                self.accuracy_attempts += 1
                self.particles.emit(cx, cy, (0, 255, 255), 30)
                self.sounds.play('catch')
                
                # Spawn new target far enough away (at least 60 degrees)
                import random
                offset = random.uniform(60, 180)
                if random.choice([True, False]): offset *= -1
                self.wrist_target_angle = (self.wrist_target_angle + offset) % 360
                self.wrist_hold_time = 0.0
        else:
            self.wrist_hold_time = 0.0
            
        import time
        if (time.time() - getattr(self, 'session_start', 0)) > getattr(self, 'session_time_limit', 60):
            self.accuracy_attempts += 1
            self._end_level()

        self.satellite_angle = current_angle
    def _update_level8(self, hand_data: HandData):
        """Level 8: Smart Object Assembly"""
        if not hand_data.index_tip or not getattr(hand_data, 'is_pinching', False) and not getattr(self, 'was_pinching', False):
            pass
            
        hx, hy = hand_data.index_tip if hand_data.index_tip else (0,0)
        is_pinching = getattr(hand_data, 'is_pinching', False)
        
        if is_pinching and not getattr(self, 'was_pinching', False):
            for part in getattr(self, 'assembly_parts', []):
                if not part.is_locked:
                    dist = ((part.current_pos[0] - hx)**2 + (part.current_pos[1] - hy)**2)**0.5
                    if dist < 80 * getattr(self, 'adaptive_target_scale', 1.0):
                        part.is_grabbed = True
                        self.sounds.play('select')
                        break
        
        if not is_pinching and getattr(self, 'was_pinching', False):
            for part in getattr(self, 'assembly_parts', []):
                if part.is_grabbed:
                    part.is_grabbed = False
                    dist = ((part.current_pos[0] - part.target_pos[0])**2 + (part.current_pos[1] - part.target_pos[1])**2)**0.5
                    ang_diff = abs(part.current_angle - part.target_angle) % 360
                    if ang_diff > 180: ang_diff = 360 - ang_diff
                    
                    if dist < getattr(self, 'assembly_position_tolerance', 50.0) and ang_diff < getattr(self, 'assembly_angle_tolerance', 30.0):
                        part.is_locked = True
                        part.current_pos = list(part.target_pos)
                        part.current_angle = part.target_angle
                        self.sounds.play('catch')
                        self.particles.emit(part.current_pos[0], part.current_pos[1], (0,255,0), 30)
                        self.score += int(50 * getattr(self, 'score_multiplier', 1.0))
                        
                        if all(p.is_locked for p in self.assembly_parts):
                            self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, WINDOW_HEIGHT//2, "ASSEMBLY COMPLETE!", (0,255,0)))
                            self.accuracy_hits += 1
                            self.accuracy_attempts += 1
                            self._end_level()

        for part in getattr(self, 'assembly_parts', []):
            if part.is_grabbed:
                part.current_pos[0] = hx
                part.current_pos[1] = hy
                part.current_angle = getattr(hand_data, 'wrist_rotation_angle', 0.0)
                
        self.was_pinching = is_pinching
        
        import time
        if (time.time() - self.session_start > max(getattr(self, 'session_time_limit', 60), 60)):
            self.accuracy_attempts += 1
            self._end_level()

    def _draw_cyber_grid(self):
        """Moving background grid for technical feel"""
        scr = self.screen
        t = time.time()
        offset_y = int((t * 40) % 40)
        grid_col = (10, 25, 45)
        for y in range(-40, WINDOW_HEIGHT + 40, 40):
            pygame.draw.line(scr, grid_col, (0, y + offset_y), (GAME_AREA_WIDTH, y + offset_y), 1)
        for x in range(0, GAME_AREA_WIDTH + 40, 40):
            pygame.draw.line(scr, grid_col, (x, 0), (x, WINDOW_HEIGHT), 1)

    def _draw(self):
        self.screen.fill(COLOR_BG)
        pygame.draw.rect(self.screen, (12, 18, 30), (0, 0, GAME_AREA_WIDTH, WINDOW_HEIGHT))
        pygame.draw.line(self.screen, (35, 50, 68), (0, 72), (GAME_AREA_WIDTH, 72), 1)
            
        # Draw game area
        if self.state == GameState.PATIENT_REGISTRATION:
            self._draw_patient_registration()
        elif self.state == GameState.AGE_SELECT:
            self._draw_age_select()
        elif self.state == GameState.MAIN_MENU:
            self._draw_menu()
        elif self.state == GameState.PAIN_SCALE:
            self._draw_pain_scale()
        elif self.state == GameState.PAIN_AFTER_SESSION:
            self._draw_pain_scale()
        elif self.state == GameState.HISTORY:
            self._draw_history()
        elif self.state == GameState.CALIBRATION:
            self._draw_calibration()
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            self._draw_level1()
        elif self.state == GameState.LEVEL2_STRENGTH:
            self._draw_level2()
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            self._draw_level3()
        elif self.state == GameState.LEVEL4_COORDINATION:
            self._draw_level4()
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            self._draw_level5()
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            self._draw_level6()
        elif self.state == GameState.LEVEL7_WRIST_MECHANICS:
            self._draw_level7()
        elif self.state == GameState.LEVEL8_SMART_ASSEMBLY:
            self._draw_level8()
        elif self.state == GameState.LEVEL_COMPLETE:
            self._draw_level_complete()
        elif self.state == GameState.RESULTS:
            self._draw_results()
        elif self.state == GameState.CLOUD_SYNC:
            self._draw_cloud_sync()
        elif self.state == GameState.THERAPIST_DASHBOARD:
            self._draw_therapist_dashboard()
        
        # Draw sidebar (not for full-screen states)
        _no_sidebar = [GameState.AGE_SELECT,
                       GameState.PATIENT_REGISTRATION, GameState.LEVEL_COMPLETE,
                       GameState.PAIN_SCALE, GameState.HISTORY, GameState.CLOUD_SYNC,
                       GameState.THERAPIST_DASHBOARD]
        if self.state not in _no_sidebar:
            hand_data = self.hand_engine.get_hand_data()
            camera_frame = self.hand_engine.get_frame()
            goals = self._get_level_goals()
            self.sidebar.draw(self.screen, camera_frame, hand_data, goals,
                              self.accuracy_hits, self.accuracy_attempts,
                              is_results=(self.state == GameState.RESULTS),
                              is_calibration=(self.state == GameState.CALIBRATION),
                              is_mirror_active=getattr(self, 'results_mirror_active', False),
                              is_paused=getattr(self, 'tracking_lost', False),
                              score=self.score,
                              exercise_name=self._get_current_exercise_name(),
                              exercise_count=self._get_exercise_count(),
                              session_elapsed=self._get_session_elapsed(),
                              pain_level=self.pain_level,
                              recovery_prediction=self._get_recovery_prediction(),
                              correctness_text=self._get_correctness_label(hand_data),
                              is_menu=(self.state == GameState.MAIN_MENU),
                              readiness_score=getattr(self, 'readiness_score', 50.0),
                              rec_difficulty=getattr(self, 'recommended_difficulty', 'Moderate'),
                              rec_explanation=getattr(self, 'recommended_difficulty_explanation', 'Ready for baseline therapy.'))

            # Draw progress chart over the bottom half of the sidebar on Results screen
            if self.state == GameState.RESULTS:
                self._draw_progress_chart()

            # Draw cursor
            self._draw_cursor(hand_data)

            # Draw home icon (gameplay only)
            if self.state not in [GameState.MAIN_MENU, GameState.RESULTS]:
                self.home_icon.draw(self.screen)
        
        # Draw particles and popups on top
        self.particles.draw(self.screen)
        for popup in self.popups:
            popup.draw(self.screen)
        
        # Draw live HUD bar (in gameplay states only)
        gameplay_states = [GameState.LEVEL1_FLEXIBILITY,
                           GameState.LEVEL2_STRENGTH,
                           GameState.LEVEL3_FINEMOTOR,
                           GameState.LEVEL4_COORDINATION,
                           GameState.LEVEL5_GRIP_RELEASE,
                           GameState.LEVEL6_FINGER_TAPS]
        if self.state in gameplay_states:
            hud_y = 8
            hud_h = 36
            hud_w = GAME_AREA_WIDTH - 20
            hud_rect = pygame.Rect(10, hud_y, hud_w, hud_h)

            # Semi-transparent HUD background
            hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
            hud_surf.fill((10, 15, 30, 200))
            self.screen.blit(hud_surf, (10, hud_y))
            pygame.draw.rect(self.screen, (0, 180, 220), hud_rect, 2, border_radius=8)

            hud_font = self.font_hud  # cached — no per-frame allocation

            # Tracking Lost Overlay (Pause / Ready)
            if getattr(self, 'tracking_lost', False):
                pause_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                pause_surf.fill((0, 0, 0, 200)) # Darker background
                self.screen.blit(pause_surf, (0, 0))
                
                # Draw MASSIVE neon pause/ready box
                box_w, box_h = 700, 250
                box_x = (GAME_AREA_WIDTH - box_w) // 2
                box_y = (WINDOW_HEIGHT - box_h) // 2
                box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
                
                has_started = getattr(self, 'game_has_started', False)
                
                # Determine colors and text based on whether the game has actually started
                if has_started:
                    border_outer_color = (255, 30, 60)   # Glowing warning red
                    border_inner_color = (255, 100, 100)
                    title_text = "SYSTEM PAUSED"
                    title_color = (255, 60, 60)
                    desc_text = "PLEASE RETURN HAND TO CAMERA VIEW"
                else:
                    border_outer_color = (0, 180, 255)   # Glowing cyber cyan
                    border_inner_color = (0, 255, 200)
                    title_text = "READY? SHOW HAND TO START"
                    title_color = (0, 220, 255)
                    desc_text = "POSITION INDEX FINGER IN CAMERA FRAME TO BEGIN"
                
                # Glowing border effect
                pygame.draw.rect(self.screen, border_outer_color, pygame.Rect(box_x-4, box_y-4, box_w+8, box_h+8), border_radius=20)
                pygame.draw.rect(self.screen, (20, 10, 15), box_rect, border_radius=15)
                pygame.draw.rect(self.screen, border_inner_color, box_rect, 4, border_radius=15)
                
                warn_text = self.font_medium.render(title_text, True, title_color)
                self.screen.blit(warn_text, warn_text.get_rect(center=(box_x + box_w//2, box_y + 80)))
                
                sub_text = self.font_small.render(desc_text, True, (255, 255, 255))
                self.screen.blit(sub_text, sub_text.get_rect(center=(box_x + box_w//2, box_y + 160)))

            # Score
            score_str = f"SCORE: {self.score}"
            sc = hud_font.render(score_str, True, (255, 255, 255))
            self.screen.blit(sc, (20, hud_y + 8))

            # Accuracy
            acc = (self.accuracy_hits / self.accuracy_attempts * 100) \
                  if self.accuracy_attempts > 0 else 0.0
            acc_color = (50, 220, 120) if acc >= 70 else \
                        (255, 180, 0)  if acc >= 40 else (220, 80, 80)
            acc_str = f"ACC: {acc:.0f}%"
            ac = hud_font.render(acc_str, True, acc_color)
            self.screen.blit(ac, (180, hud_y + 8))

            # Combo
            if self.combo > 1:
                combo_color = (255, 215, 0) if self.combo >= 5 else (255, 180, 60)
                co = hud_font.render(f"x{self.combo} COMBO", True, combo_color)
                self.screen.blit(co, (310, hud_y + 8))

            # Multiplier badge
            if self.score_multiplier > 1.0:
                mx = hud_font.render(f"{self.score_multiplier:.0f}x BOOST", True, (255, 100, 255))
                self.screen.blit(mx, (470, hud_y + 8))
        
        # Draw feedback text (center screen) — use cached font to avoid per-frame allocation
        if self.feedback_text and self.feedback_timer > 0:
            feedback_surf = self.font_large.render(self.feedback_text, True, COLOR_SUCCESS)
            feedback_rect = feedback_surf.get_rect(center=(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 3))
            shadow = self.font_large.render(self.feedback_text, True, (0, 0, 0))
            self.screen.blit(shadow, shadow.get_rect(center=(GAME_AREA_WIDTH // 2 + 3, WINDOW_HEIGHT // 3 + 3)))
            self.screen.blit(feedback_surf, feedback_rect)
            
        # Draw correctness warning (top center)
        if getattr(self, 'correctness_warning', "") and getattr(self, 'state', None) in gameplay_states:
            c_color = (255, 100, 100) if "Bend" in self.correctness_warning else (100, 255, 100)
            warning_surf = self.font_hud.render(self.correctness_warning, True, c_color)
            warning_rect = warning_surf.get_rect(center=(GAME_AREA_WIDTH // 2, 70))
            shadow_warn = self.font_hud.render(self.correctness_warning, True, (0, 0, 0))
            self.screen.blit(shadow_warn, shadow_warn.get_rect(center=(GAME_AREA_WIDTH // 2 + 2, 72)))
            self.screen.blit(warning_surf, warning_rect)
        
        # Apply screen shake offset
        if self.shake_offset != (0, 0):
            # Create a temporary surface with the current screen
            temp_surf = self.screen.copy()
            self.screen.fill(COLOR_BG)
            self.screen.blit(temp_surf, self.shake_offset)
            
        # Draw Global Fist-Hold Exit Overlay
        if hasattr(self, '_global_fist_start') and self._global_fist_start is not None:
            elapsed = time.time() - self._global_fist_start
            progress = min(elapsed / 2.0, 1.0)
            if progress > 0.05:
                # Dim background
                dim_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                dim_surf.fill((10, 10, 20, 180))
                self.screen.blit(dim_surf, (0, 0))
                
                # Glowing center box
                box_w, box_h = 600, 300
                box_x = (WINDOW_WIDTH - box_w) // 2
                box_y = (WINDOW_HEIGHT - box_h) // 2
                pygame.draw.rect(self.screen, (20, 25, 45), (box_x, box_y, box_w, box_h), border_radius=20)
                pygame.draw.rect(self.screen, (255, 60, 100), (box_x, box_y, box_w, box_h), 4, border_radius=20)
                
                # Ring gauge in center of box
                cx = box_x + box_w // 2
                cy = box_y + box_h // 2 + 30
                radius = 50
                pygame.draw.circle(self.screen, (40, 45, 65), (cx, cy), radius, 8)
                
                start_a = math.radians(-90)
                end_a = math.radians(-90 + 360 * progress)
                arc_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.arc(arc_surf, (255, 60, 100), (0, 0, radius * 2, radius * 2), start_a, end_a, 10)
                self.screen.blit(arc_surf, (cx - radius, cy - radius))
                
                # Text inside ring
                rem = max(0.0, 2.0 - elapsed)
                cd_t = self.font_cd.render(f"{rem:.1f}s", True, (255, 255, 255))
                self.screen.blit(cd_t, cd_t.get_rect(center=(cx, cy)))
                
                # Heading
                h_t = self.font_medium.render("HOLDING FIST TO EXIT", True, (255, 60, 100))
                self.screen.blit(h_t, h_t.get_rect(center=(cx, box_y + 40)))
                sub_t = self.font_small.render("Keep hand closed to return to Main Menu", True, (180, 200, 220))
                self.screen.blit(sub_t, sub_t.get_rect(center=(cx, box_y + 85)))

        # Draw Compensation Warning overlay
        if hasattr(self, 'compensation_detector') and self.compensation_detector.warning_text:
            elapsed_warn = time.time() - self.compensation_detector.last_triggered_time
            if elapsed_warn < 3.0:
                alpha = int(255 * (1.0 - elapsed_warn / 3.0))
                bar_h = 50
                bar_y = WINDOW_HEIGHT - bar_h - 20
                bar_w = GAME_AREA_WIDTH - 40
                bar_x = 20
                
                # Draw red notice bar
                warn_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
                warn_surf.fill((220, 45, 45, int(alpha * 0.85)))
                pygame.draw.rect(warn_surf, (255, 90, 90, alpha), (0, 0, bar_w, bar_h), 2, border_radius=8)
                
                text_surf = self.font_hud.render(self.compensation_detector.warning_text, True, (255, 255, 255))
                text_rect = text_surf.get_rect(center=(bar_w // 2, bar_h // 2))
                warn_surf.blit(text_surf, text_rect)
                self.screen.blit(warn_surf, (bar_x, bar_y))

        pygame.display.flip()
    
    def _draw_camera_preview(self, x, y, w, h, label="SYSTEM CAMERA"):
        """Draw live camera feed with a technical border"""
        with self.hand_engine.lock:
            frame = self.hand_engine.mirrored_frame
            if frame is not None:
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    f_h, f_w = frame_rgb.shape[:2]
                    frame_surf = pygame.image.frombuffer(frame_rgb.tobytes(), (f_w, f_h), "RGB")
                    scaled_surf = pygame.transform.scale(frame_surf, (w, h))
                    self.screen.blit(scaled_surf, (x, y))
                    
                    # Green Phosphor Tint for CRT look
                    tint = pygame.Surface((w, h), pygame.SRCALPHA)
                    tint.fill((0, 255, 120, 40))
                    self.screen.blit(tint, (x, y))
                except: pass
            else:
                pygame.draw.rect(self.screen, (10, 15, 25), (x, y, w, h))
                txt = self.font_tiny.render("CALIBRATING...", True, (60, 80, 100))
                self.screen.blit(txt, txt.get_rect(center=(x+w//2, y+h//2)))

        # Technical frame
        pygame.draw.rect(self.screen, (0, 200, 255), (x, y, w, h), 2, border_radius=4)
        pygame.draw.line(self.screen, (0, 255, 150), (x, y+h+5), (x+40, y+h+5), 2)
        lbl = self.font_tiny.render(label, True, (0, 255, 150))
        self.screen.blit(lbl, (x, y+h+10))
        
        # Flickering "REC" dot
        if int(time.time()*2) % 2 == 0:
            pygame.draw.circle(self.screen, (255, 50, 50), (x+w-15, y+15), 4)
    
    
    
    def _draw_patient_registration(self):
        """Clinical grade 'Serious' medical registration portal"""
        t = time.time()
        scr = self.screen
        cx = WINDOW_WIDTH // 2

        # ── Background (Deep Clinical Blue/Black) ──────────────────────
        scr.fill((4, 8, 16)) # Very dark
        
        # ── Animated Scanning Line (Smooth Multi-Shade Glow) ──────────
        scan_y = int((t * 120) % WINDOW_HEIGHT)
        pygame.draw.line(scr, (0, 255, 200), (0, scan_y), (WINDOW_WIDTH, scan_y), 2)
        pygame.draw.line(scr, (0, 180, 120), (0, scan_y - 1), (WINDOW_WIDTH, scan_y - 1), 1)
        pygame.draw.line(scr, (0, 180, 120), (0, scan_y + 2), (WINDOW_WIDTH, scan_y + 2), 1)
        
        # ── Slim Cyber Header ──────────────────────────────────────────
        pygame.draw.rect(scr, (8, 12, 24), pygame.Rect(0, 0, WINDOW_WIDTH, 70))
        pygame.draw.line(scr, (0, 200, 150), (20, 68), (WINDOW_WIDTH - 20, 68), 2)
        
        title = self.font_large.render("CLINICAL REGISTRATION PORTAL", True, (0, 200, 150))
        scr.blit(title, title.get_rect(center=(cx, 35)))

        y_start = 90
        
        # ── Massive Diagnostic Camera Panel (Right Side) ───────────────
        cam_w, cam_h = 480, 360
        cam_x = WINDOW_WIDTH - cam_w - 40
        cam_y = y_start
        
        panel_rect = pygame.Rect(cam_x - 10, cam_y - 10, cam_w + 20, cam_h + 80)
        pygame.draw.rect(scr, (6, 10, 18), panel_rect, border_radius=8)
        pygame.draw.rect(scr, (0, 150, 120), panel_rect, 2, border_radius=8)

        # Tech corners for camera panel
        l = 20
        # Top-Left
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.x, panel_rect.y), (panel_rect.x + l, panel_rect.y), 3)
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.x, panel_rect.y), (panel_rect.x, panel_rect.y + l), 3)
        # Top-Right
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.right, panel_rect.y), (panel_rect.right - l, panel_rect.y), 3)
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.right, panel_rect.y), (panel_rect.right, panel_rect.y + l), 3)
        # Bottom-Left
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.x, panel_rect.bottom), (panel_rect.x + l, panel_rect.bottom), 3)
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.x, panel_rect.bottom), (panel_rect.x, panel_rect.bottom - l), 3)
        # Bottom-Right
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.right, panel_rect.bottom), (panel_rect.right - l, panel_rect.bottom), 3)
        pygame.draw.line(scr, (0, 255, 200), (panel_rect.right, panel_rect.bottom), (panel_rect.right, panel_rect.bottom - l), 3)
        
        # Draw camera frame
        self._draw_camera_preview(cam_x, cam_y, cam_w, cam_h, "HIGH-RES NEURAL SENSOR")
        
        # Display hand type in diagnostics - shifted down to avoid overlapping the camera label
        hand_data = self.hand_engine.get_hand_data()
        hand_txt = f"SENSE: {hand_data.hand_label.upper()} HAND DETECTED" if hand_data.hand_label != "Unknown" else "AWAITING HAND CALIBRATION..."
        diag_col = (0, 255, 150) if hand_data.hand_label != "Unknown" else (255, 180, 0)
        diag_txt = self.font_small.render(f"STATUS: {hand_txt}", True, diag_col)
        scr.blit(diag_txt, (cam_x, cam_y + cam_h + 36))

        # ── Input Fields (Left Side) ──────────────────────────────────
        left_x = 50
        input_w = cam_x - left_x - 40 # Fill remaining space
        
        # --- Mode 1: Clinical ID Login ---
        # y_id = y_start
        # id_active = self.input_active == "id"
        # id_col = (0, 255, 200) if id_active else (60, 100, 120)
        # scr.blit(self.font_hint.render("MODE 1: CLINICAL ID LOGIN", True, id_col), (left_x, y_id))
        
        # id_box = pygame.Rect(left_x, y_id+25, input_w, 50)
        # pygame.draw.rect(scr, (8, 14, 20), id_box, border_radius=6)
        
        # if id_active:
        #     pygame.draw.rect(scr, (0, 255, 200), id_box, 2, border_radius=6)
        #     pygame.draw.rect(scr, (0, 150, 120), id_box.inflate(-2, -2), 1, border_radius=5)
        # else:
        #     pygame.draw.rect(scr, (40, 60, 80), id_box, 1, border_radius=6)
            
        # d_id = self.patient_id_str + ("_" if id_active and int(t*2)%2==0 else "")
        # id_surf = self.font_medium.render(d_id or "Enter ID to Login...", True, (255, 255, 255) if self.patient_id_str else (80, 80, 80))
        # id_rect = id_surf.get_rect(midleft=(id_box.x + 15, id_box.centery))
        # scr.blit(id_surf, id_rect)

        # --- Divider ---
        # y_div = y_id + 90
        # pygame.draw.line(scr, (40, 60, 80), (left_x, y_div), (left_x + input_w, y_div), 1)
        # or_txt = self.font_small.render("OR", True, (60, 100, 120))
        # scr.blit(or_txt, or_txt.get_rect(center=(left_x + input_w // 2, y_div)))



        # --- Mode 1: Clinical ID Login ---
        y_id = y_start
        id_active = self.input_active == "id"
        id_col = (0, 255, 200) if id_active else (60, 100, 120)
        scr.blit(self.font_hint.render("MODE 1: CLINICAL ID LOGIN", True, id_col), (left_x, y_id))
        
        id_box = pygame.Rect(left_x, y_id+25, input_w, 50)
        pygame.draw.rect(scr, (8, 14, 20), id_box, border_radius=6)
        
        if id_active:
            pygame.draw.rect(scr, (0, 255, 200), id_box, 2, border_radius=6)
            pygame.draw.rect(scr, (0, 150, 120), id_box.inflate(-2, -2), 1, border_radius=5)
        else:
            pygame.draw.rect(scr, (40, 60, 80), id_box, 1, border_radius=6)
            
        d_id = self.patient_id_str + ("_" if id_active and int(t*2)%2==0 else "")
        id_surf = self.font_medium.render(d_id or "Enter ID to Login...", True, (255, 255, 255) if self.patient_id_str else (80, 80, 80))
        id_rect = id_surf.get_rect(midleft=(id_box.x + 15, id_box.centery))
        scr.blit(id_surf, id_rect)

        # --- Divider ---
        y_div = y_id + 90
        pygame.draw.line(scr, (40, 60, 80), (left_x, y_div), (left_x + input_w, y_div), 1)
        or_txt = self.font_small.render("OR", True, (60, 100, 120))
        scr.blit(or_txt, or_txt.get_rect(center=(left_x + input_w // 2, y_div)))






        # --- Mode 2: Guest Registration ---
        y_name = y_div + 20
        name_active = self.input_active == "name"
        name_col = (0, 255, 200) if name_active else (60, 100, 120)
        scr.blit(self.font_hint.render("MODE 2: GUEST REGISTRATION (NAME)", True, name_col), (left_x, y_name))
        
        name_box = pygame.Rect(left_x, y_name+25, input_w, 50)
        pygame.draw.rect(scr, (8, 14, 20), name_box, border_radius=6)
        
        if name_active:
            pygame.draw.rect(scr, (0, 255, 200), name_box, 2, border_radius=6)
            pygame.draw.rect(scr, (0, 150, 120), name_box.inflate(-2, -2), 1, border_radius=5)
        else:
            pygame.draw.rect(scr, (40, 60, 80), name_box, 1, border_radius=6)
        
        d_name = self.patient_name + ("_" if name_active and int(t*2)%2==0 else "")
        ns = self.font_medium.render(d_name or "Enter Name...", True, (255, 255, 255) if self.patient_name else (80, 80, 80))
        ns_rect = ns.get_rect(midleft=(name_box.x + 15, name_box.centery))
        scr.blit(ns, ns_rect)

        # Patient Age Field
        y_age = y_name + 90
        age_active = self.input_active == "age"
        age_col = (0, 255, 200) if age_active else (60, 100, 120)
        scr.blit(self.font_hint.render("GUEST AGE", True, age_col), (left_x, y_age))
        
        age_box = pygame.Rect(left_x, y_age+25, input_w // 2, 50)
        pygame.draw.rect(scr, (8, 14, 20), age_box, border_radius=6)
        
        if age_active:
            pygame.draw.rect(scr, (0, 255, 200), age_box, 2, border_radius=6)
            pygame.draw.rect(scr, (0, 150, 120), age_box.inflate(-2, -2), 1, border_radius=5)
        else:
            pygame.draw.rect(scr, (40, 60, 80), age_box, 1, border_radius=6)
        
        d_age = self.patient_age + ("_" if age_active and int(t*2)%2==0 else "")
        as_ = self.font_medium.render(d_age or "00", True, (255, 255, 255) if self.patient_age else (80, 80, 80))
        as_rect = as_.get_rect(midleft=(age_box.x + 15, age_box.centery))
        scr.blit(as_, as_rect)

        # Automatic Mode Tag
        if self.patient_age.isdigit():
            age = int(self.patient_age)
            label, lcol = "ADULT REHAB", (100, 255, 180)
            if age <= 12: label, lcol = "PEDIATRIC MODE", (255, 160, 200)
            elif age > 60: label, lcol = "GERIATRIC CARE", (255, 200, 100)
            
            mode_tag = self.font_small.render(f"[{label}]", True, lcol)
            scr.blit(mode_tag, mode_tag.get_rect(midleft=(left_x + input_w // 2 + 15, age_box.centery)))

        # ── Medical Sub-Panel ──────────────────────────────────────────
        y_info = y_age + 90
        info_rect = pygame.Rect(left_x, y_info, input_w, 120)
        pygame.draw.rect(scr, (10, 18, 28), info_rect, border_radius=8)
        pygame.draw.rect(scr, (0, 100, 150), info_rect, 1, border_radius=8)
        
        scr.blit(self.font_small.render("DIAGNOSTIC PROTOCOL:", True, (0, 180, 255)), (left_x + 15, y_info + 12))
        scr.blit(self.font_hint.render("1. Stand 1-2 meters from the camera", True, (150, 180, 200)), (left_x + 15, y_info + 38))
        scr.blit(self.font_hint.render("2. Ensure room is well-lit for tracking", True, (150, 180, 200)), (left_x + 15, y_info + 60))
        scr.blit(self.font_hint.render("3. Complete registration to unlock therapies", True, (150, 180, 200)), (left_x + 15, y_info + 82))

        # ── Controls & Launch ──────────────────────────────────────────
        c_txt = "TAB: Switch Field | ENTER: Launch Therapy Session"
        c_surf = self.font_hint.render(c_txt, True, (80, 120, 160))
        scr.blit(c_surf, c_surf.get_rect(center=(left_x + input_w // 2, y_info + 135)))

        btn_rect = pygame.Rect(left_x, y_info + 155, input_w, 50)
        
        # Unify button rendering using CloseButton for both empty and filled states to support hover click operations
        if hasattr(self, 'quick_start_button'):
            self.quick_start_button.rect = btn_rect
            if self.patient_name and self.patient_age:
                self.quick_start_button.draw(
                    scr, self.font_medium, "INITIATE REHABILITATION", 
                    base_col=(0, 100, 70), hov_col=(0, 150, 100), border_col=(0, 255, 150)
                )
            else:
                self.quick_start_button.draw(
                    scr, self.font_medium, "QUICK START", 
                    base_col=(30, 40, 55), hov_col=(0, 120, 180), border_col=(0, 180, 220)
                )



        # Cursor
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)
    
    def _draw_age_select(self):
        """Draw age selection screen"""
        # Title
        title = self.font_large.render("SELECT YOUR AGE GROUP", True, COLOR_PRIMARY)
        title_rect = title.get_rect(center=(WINDOW_WIDTH // 2, 60))
        self.screen.blit(title, title_rect)
        
        # Subtitle
        subtitle = self.font_small.render("Choose the experience that's right for you", True, COLOR_TEXT)
        subtitle_rect = subtitle.get_rect(center=(WINDOW_WIDTH // 2, 105))
        self.screen.blit(subtitle, subtitle_rect)

        # Side Camera (Age Select)
        self._draw_camera_preview(WINDOW_WIDTH - 220, 20, 200, 150, "ACTIVE HAND")
        
        # Draw age buttons
        for button in self.age_buttons:
            button.draw(self.screen, self.font_medium)
        
        # Instructions
        inst = self.font_small.render("Hover your hand over a card to select", True, COLOR_SUCCESS)
        inst_rect = inst.get_rect(center=(WINDOW_WIDTH // 2, 600))
        self.screen.blit(inst, inst_rect)
        
        # Draw cursor for age select
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)
    
    def _get_theme(self) -> dict:
        """Return the current age theme dict, defaulting to adult."""
        if self.age_group is None:
            return AGE_THEMES["adult"]
        return AGE_THEMES.get(self.age_group.value, AGE_THEMES["adult"])

    def _draw_menu(self):
        theme = self._get_theme()
        primary = theme["primary_color"]

        # Draw Logout Button in top-left (allows returning to Registration screen)
        if hasattr(self, 'logout_button'):
            self.logout_button.draw(self.screen, self.font_small, base_col=(40, 50, 70))

        # Title
        title = self.font_medium.render("AI PHYSIOTHERAPY", True, primary)
        title_rect = title.get_rect(center=(GAME_AREA_WIDTH // 2, 50))
        
        # Soft Glow Behind Title
        glow = pygame.Surface((title_rect.width + 80, title_rect.height + 30), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (primary[0], primary[1], primary[2], 20), glow.get_rect())
        self.screen.blit(glow, glow.get_rect(center=(GAME_AREA_WIDTH // 2, 50)))
        
        # Drop Shadow
        shadow = self.font_medium.render("AI PHYSIOTHERAPY", True, (0, 0, 0))
        self.screen.blit(shadow, shadow.get_rect(center=(GAME_AREA_WIDTH // 2 + 2, 52)))
        
        self.screen.blit(title, title_rect)

        # Theme name + Welcome — compact single line
        info_parts = [f"Theme: {theme['name']}"]
        if self.patient_name:
            info_parts.append(f"Welcome, {self.patient_name}!")
        
        theme_surf = self.font_tiny.render(info_parts[0], True, theme["accent_color"])
        theme_rect = theme_surf.get_rect(center=(GAME_AREA_WIDTH // 2 - 80, 90))
        self.screen.blit(theme_surf, theme_rect)
        
        if self.patient_name:
            welcome = self.font_tiny.render(f"Welcome, {self.patient_name}!", True, COLOR_SUCCESS)
            welcome_rect = welcome.get_rect(center=(GAME_AREA_WIDTH // 2 + 80, 90))
            self.screen.blit(welcome, welcome_rect)

        # Update level button labels to clinical terminology
        clinical_labels = [
            "Wrist Flexion & Extension\n(Active ROM)",
            "Grip Strength & Coordination\n(Fruit Catch)",
            "Pinch Training\n(Seed Planting)",
            "Coordination & Tracing\n(Path Trace)",
            "Grip & Release Cycle\n(Balloon Pump)",
            "Fine Motor Tap Precision\n(Simon Tap)",
            "Forearm Pronate & Supinate\n(Rotation Orbit)",
            "Functional Spatial Coord\n(Toy Builder)"
        ]
        btn_font = pygame.font.SysFont("segoeui", 16)
        for i, button in enumerate(self.level_buttons):
            if i < len(clinical_labels):
                button.text = clinical_labels[i]
            button.draw(self.screen, btn_font)

        # Instructions
        inst = self.font_tiny.render("Hover your finger over a level to select", True, COLOR_TEXT)
        inst_rect = inst.get_rect(center=(GAME_AREA_WIDTH // 2, 575))
        self.screen.blit(inst, inst_rect)

        # History, Calibration, and Exit utility buttons
        util_font = pygame.font.SysFont("segoeui", 14, bold=True)
        self.history_button.draw(self.screen, util_font, base_col=(30, 80, 150), hov_col=(50, 120, 200))
        if hasattr(self, 'calibrate_button'):
            self.calibrate_button.draw(self.screen, util_font, base_col=(120, 60, 140), hov_col=(160, 80, 180))
        if hasattr(self, 'exit_button'):
            self.exit_button.draw(self.screen, util_font, base_col=(180, 40, 40), hov_col=(255, 60, 60))
    
    def _draw_level1(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level1_name']

        # Title (pushed down to clear HUD bar)
        title = self.font_medium.render(f"LEVEL 1: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))

        # Bubble counter
        total_bubbles = len(self.bubbles)
        remaining = sum(1 for b in self.bubbles if not b.popped)
        counter_text = self.font_hint.render(
            f"Bubbles: {remaining} / {total_bubbles}", True, (180, 210, 230))
        self.screen.blit(counter_text, (50, 115))

        # Dot row showing bubble status
        dot_x = 50
        dot_y = 142
        for bubble in self.bubbles:
            dot_color = primary if not bubble.popped else (50, 55, 75)
            pygame.draw.circle(self.screen, dot_color, (dot_x, dot_y), 6)
            pygame.draw.circle(self.screen, (255, 255, 255), (dot_x, dot_y), 6, 1)
            dot_x += 18

        # Bubbles
        for bubble in self.bubbles:
            if not bubble.popped:
                pygame.draw.circle(self.screen, bubble.color, (int(bubble.x), int(bubble.y)), bubble.radius)
                surf = pygame.Surface((bubble.radius*2, bubble.radius*2), pygame.SRCALPHA)
                pygame.draw.ellipse(surf, (255,255,255,90), (bubble.radius*0.4, bubble.radius*0.15, bubble.radius, bubble.radius*0.5))
                self.screen.blit(surf, (int(bubble.x) - bubble.radius, int(bubble.y) - bubble.radius))
                pygame.draw.circle(self.screen, primary, (int(bubble.x), int(bubble.y)), bubble.radius, 2)
    
    def _draw_level2(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level2_name']

        # Title pushed lower
        title = self.font_medium.render(f"LEVEL 2: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))

        # Timer bar lower
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        # Basket (theme-colored)
        basket_rect = pygame.Rect(int(self.basket_x - 75), self.basket_y, 150, 40)
        pygame.draw.rect(self.screen, theme["secondary_color"], basket_rect, border_radius=10)
        pygame.draw.rect(self.screen, primary, basket_rect, 3, border_radius=10)

        # Shield Effect
        if self.shield_active:
            pulse = int(5 * math.sin(time.time() * 10))
            shield_rect = basket_rect.copy()
            shield_rect.inflate_ip(20 + pulse, 20 + pulse)
            pygame.draw.ellipse(self.screen, (0, 200, 255), shield_rect, 3)
            # draw a faint inner fill via an alpha surface
            shield_surf = pygame.Surface((shield_rect.width, shield_rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(shield_surf, (0, 200, 255, 40), shield_surf.get_rect())
            self.screen.blit(shield_surf, shield_rect.topleft)

        # Freezing background tint
        if self.slow_mo:
            freeze_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            freeze_surf.fill((100, 255, 255, 15))
            self.screen.blit(freeze_surf, (0, 0))

        # Falling items
        for item in self.falling_items:
            pygame.draw.circle(self.screen, item.color,
                             (int(item.x), int(item.y)), item.radius)
            pygame.draw.circle(self.screen, COLOR_TEXT,
                             (int(item.x), int(item.y)), item.radius, 2)
    
    def _draw_level3(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level3_name']

        # Title pushed lower
        title = self.font_medium.render(f"LEVEL 3: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))

        # Timer bar lower
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        # Pot (theme-colored)
        pygame.draw.circle(self.screen, theme["secondary_color"], (self.pot_x, self.pot_y), 50)
        pygame.draw.circle(self.screen, primary, (self.pot_x, self.pot_y), 50, 3)

        # Seeds
        for seed in self.seeds:
            color = theme["accent_color"] if seed.grabbed else COLOR_SEED
            pygame.draw.circle(self.screen, color,
                             (int(seed.x), int(seed.y)), seed.radius)
            pygame.draw.circle(self.screen, COLOR_TEXT,
                             (int(seed.x), int(seed.y)), seed.radius, 2)
                             
    def _draw_level4(self):
        """Draw Tracing Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level4_name', 'Magic Trace')

        title = self.font_medium.render(f"LEVEL 4: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        
        # Draw the full Figure-8 guide path (static background)
        points = []
        for i in range(101):
            t = i * (math.pi * 2 / 100)
            px = cx + 180 * math.sin(t)
            py = cy + 90 * math.sin(2 * t)
            points.append((px, py))
            
        if len(points) > 1:
            pygame.draw.lines(self.screen, (30, 50, 70), False, points, 5)
            
        # Draw the recent path trail (active)
        if len(self.trace_path) > 1:
            pygame.draw.lines(self.screen, theme["secondary_color"], False, self.trace_path, 3)
            
        # Draw target
        pygame.draw.circle(self.screen, theme["accent_color"], (int(self.trace_target_x), int(self.trace_target_y)), 25)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(self.trace_target_x), int(self.trace_target_y)), 10)
        
        inst = self.font_small.render("Keep your finger exactly on the moving target!", True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 200)))
        
    def _draw_level5(self):
        """Draw Grip & Release Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level5_name', 'Balloon Pump')

        title = self.font_medium.render(f"LEVEL 5: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 30
        
        # Draw balloon/core
        base_r = 80
        current_r = int(base_r * self.balloon_scale)
        
        color = theme["accent_color"] if self.pump_state == 0 else theme["secondary_color"]
        pygame.draw.circle(self.screen, color, (cx, cy), current_r)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), current_r, max(1, current_r // 15))
        
        # Reps text
        reps_text = self.font_large.render(str(self.pump_reps), True, (255, 255, 255))
        self.screen.blit(reps_text, reps_text.get_rect(center=(cx, cy)))
        
        inst_txt = "Make a FIST, then OPEN your hand fully!" if self.pump_state == 0 else "OPEN your hand wide!"
        inst = self.font_small.render(inst_txt, True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + current_r + 40)))
        
    def _draw_level6(self):
        """Draw Memory Sequence Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level6_name', 'Memory Sequence')

        title = self.font_medium.render(f"LEVEL 6: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # Timer
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        pads = {
            1: (cx - 150, cy - 80),
            2: (cx + 150, cy - 80),
            3: (cx - 150, cy + 120),
            4: (cx + 150, cy + 120)
        }
        pad_colors = {
            1: (255, 100, 100), # Red
            2: (100, 255, 100), # Green
            3: (100, 100, 255), # Blue
            4: (255, 255, 100)  # Yellow
        }
        
        for p_id, (px, py) in pads.items():
            col = pad_colors[p_id]
            is_active = (getattr(self, 'simon_active_pad', None) == p_id)
            is_hovering = (self.simon_state == "PLAY" and getattr(self, '_last_hover', None) == p_id)
            
            draw_col = col if is_active else tuple(int(c * 0.4) for c in col)
            r_size = 75 if is_active else 65
            if is_hovering and not is_active:
                draw_col = tuple(int(c * 0.7) for c in col)
                r_size = 70
                # Draw hover progress
                if hasattr(self, '_hover_start'):
                    prog = min(1.0, (time.time() - self._hover_start) / 0.4)
                    pygame.draw.arc(self.screen, (255,255,255), (px-80, py-80, 160, 160), math.pi/2, math.pi/2 + 2*math.pi*prog, 4)
            
            pygame.draw.circle(self.screen, draw_col, (px, py), r_size)
            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), r_size, 3)
            
        status = "WATCH CAREFULLY!" if self.simon_state == "SHOW" else "REPEAT SEQUENCE"
        if self.simon_state == "START": status = "GET READY"
        inst = self.font_medium.render(status, True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 240)))
        
        seq_len = max(0, len(self.simon_sequence) - 1) if self.simon_state == "START" else len(self.simon_sequence)
        score_t = self.font_small.render(f"Sequence Length: {seq_len}", True, (0, 255, 200))
        self.screen.blit(score_t, score_t.get_rect(center=(cx, cy - 200)))
    
    def _draw_cursor(self, hand_data: HandData):  # noqa
        if not hand_data.index_tip:
            return

        cx, cy = hand_data.index_tip
        t = time.time()

        # --- State-based colors ---
        if hand_data.is_fist:
            core_color   = (255, 140, 0)   # Orange = fist/pause
            ring_color   = (255, 180, 60)
            glow_color   = (255, 120, 0)
        elif hand_data.is_pinching:
            core_color   = (50, 255, 150)  # Green = pinching
            ring_color   = (100, 255, 180)
            glow_color   = (0, 200, 100)
        else:
            core_color   = (0, 200, 255)   # Cyan = normal point
            ring_color   = (80, 220, 255)
            glow_color   = (0, 150, 220)

        # --- Motion trail ---
        self._cursor_trail.append((cx, cy))
        if len(self._cursor_trail) > 12:
            self._cursor_trail.pop(0)

        for i, (tx, ty) in enumerate(self._cursor_trail[:-1]):
            alpha_factor = (i + 1) / len(self._cursor_trail)
            r = int(glow_color[0] * alpha_factor)
            g = int(glow_color[1] * alpha_factor)
            b = int(glow_color[2] * alpha_factor)
            trail_r = max(2, int(8 * alpha_factor))
            pygame.draw.circle(self.screen, (r, g, b), (tx, ty), trail_r)

        # --- Outer pulsing glow ring ---
        pulse = int(5 + 4 * math.sin(t * 5))
        pygame.draw.circle(self.screen, glow_color, (cx, cy), 22 + pulse, 2)

        # --- Mid ring ---
        pygame.draw.circle(self.screen, ring_color, (cx, cy), 18, 3)

        # --- Filled inner circle ---
        pygame.draw.circle(self.screen, core_color, (cx, cy), 12)

        # --- Bright white center dot ---
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 4)

        # --- Crosshair lines for precision ---
        line_len = 8
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx - line_len - 14, cy), (cx - 14, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx + 14, cy), (cx + line_len + 14, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx, cy - line_len - 14), (cx, cy - 14), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx, cy + 14), (cx, cy + line_len + 14), 2)

        # --- Pinch line between thumb and index ---
        if hand_data.is_pinching and hand_data.thumb_tip:
            pygame.draw.line(self.screen, (50, 255, 150),
                             hand_data.index_tip, hand_data.thumb_tip, 3)
            # Small circle at thumb tip too
            pygame.draw.circle(self.screen, (50, 255, 150),
                               hand_data.thumb_tip, 8)
            pygame.draw.circle(self.screen, (255, 255, 255),
                               hand_data.thumb_tip, 3)
    
    def _spawn_bubbles(self):
        self.bubbles.clear()
        theme = self._get_theme()
        spd = theme["speed_multiplier"] * getattr(self, 'adaptive_speed_scale', 1.0)
        sz = int(60 * theme["size_multiplier"] * getattr(self, 'adaptive_target_scale', 1.0))
        bubble_color = theme["primary_color"]

        positions = [
            (200, 200), (GAME_AREA_WIDTH - 200, 200),
            (200, WINDOW_HEIGHT - 150), (GAME_AREA_WIDTH - 200, WINDOW_HEIGHT - 150),
            (GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2)
        ]
        for x, y in positions:
            is_golden = random.random() < 0.2  # 20% golden
            color = (255, 215, 0) if is_golden else bubble_color
            vx = random.uniform(-2, 2) * spd
            vy = random.uniform(-2, 2) * spd
            bubble = Bubble(x, y, sz, color)
            bubble.vx = vx
            bubble.vy = vy
            bubble.is_golden = is_golden
            self.bubbles.append(bubble)

    def _spawn_falling_item(self):
        theme = self._get_theme()
        spd = theme["speed_multiplier"] * getattr(self, 'adaptive_speed_scale', 1.0)
        sz = int(25 * theme["size_multiplier"] * getattr(self, 'adaptive_target_scale', 1.0))

        x = random.randint(100, GAME_AREA_WIDTH - 100)
        y = -30

        rand = random.random()
        if rand < 0.15:  # 15% bombs
            item = FallingItem(x, y, sz, 3 * spd, (255, 50, 50))
            item.is_bomb = True
        elif rand < 0.20:  # 5% 2x power-ups
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (255, 215, 0))
            item.is_powerup = True
        elif rand < 0.25:  # 5% shields
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (0, 200, 255))
            item.is_shield = True
        elif rand < 0.30:  # 5% freeze
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (100, 255, 255))
            item.is_freeze = True
        else:  # 70% normal
            item = FallingItem(x, y, sz, 3 * spd, theme["secondary_color"])

        self.falling_items.append(item)

    def _spawn_seed(self):
        theme = self._get_theme()
        spd = theme["speed_multiplier"] * getattr(self, 'adaptive_speed_scale', 1.0)
        sz = int(18 * theme["size_multiplier"] * getattr(self, 'adaptive_target_scale', 1.0))

        x = random.randint(100, GAME_AREA_WIDTH - 100)
        y = -30
        is_golden = random.random() < 0.25  # 25% golden
        seed = Seed(x, y, sz, 2.5 * spd, False)
        seed.is_golden = is_golden
        self.seeds.append(seed)
    

    def _draw_level7(self):
        """Draw Level 7: Rotation Orbit"""
        import math
        import pygame
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        orbit_radius = 200
        
        level_name = theme.get('level7_name', 'Rotation Orbit')
        title = getattr(self, 'font_medium').render(f"LEVEL 7: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # 1. Draw Planet (Center)
        pygame.draw.circle(self.screen, (20, 50, 100), (cx, cy), 60) # Core
        pygame.draw.circle(self.screen, primary, (cx, cy), 60, 3) # Atmosphere
        
        # 2. Draw Orbital Ring
        pygame.draw.circle(self.screen, (50, 50, 50), (cx, cy), orbit_radius, 2)
        
        # 3. Draw Target Zone (Asteroid/Space Station)
        target_rad = math.radians(self.wrist_target_angle)
        tx = cx + int(math.cos(target_rad) * orbit_radius)
        ty = cy + int(math.sin(target_rad) * orbit_radius)
        
        # Draw target zone glow based on hold time
        hold_pct = min(self.wrist_hold_time / 1.5, 1.0)
        target_color = (int(255 * hold_pct), 255, int(255 * (1-hold_pct)))
        pygame.draw.circle(self.screen, target_color, (tx, ty), 35, 4)
        pygame.draw.circle(self.screen, target_color, (tx, ty), int(35 * hold_pct)) # Fill up
        
        # 4. Draw Satellite (Patient's Forearm Rotation)
        # Using a dummy object hand_data, but we need to access it via self or pass it. 
        # _draw_level7 doesn't take hand_data, so we read it from self if available or we store current_angle in _update_level7.
        # Let's fix that by storing satellite_angle in self during _update_level7.
        # Fallback to 0 if not set.
        sat_angle = getattr(self, 'satellite_angle', 0.0)
        sat_rad = math.radians(sat_angle)
        sx = cx + int(math.cos(sat_rad) * orbit_radius)
        sy = cy + int(math.sin(sat_rad) * orbit_radius)
        
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), 15)
        pygame.draw.circle(self.screen, primary, (sx, sy), 20, 2)
        
        # Draw tether from planet to satellite
        pygame.draw.line(self.screen, (100, 100, 100), (cx, cy), (sx, sy), 1)

    def _draw_level8(self):
        """Draw Level 8: Smart Assembly"""
        theme = self._get_theme()
        primary = theme['primary_color']
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        
        level_name = theme.get('level8_name', 'Toy Builder')
        title = getattr(self, 'font_medium').render(f"LEVEL 8: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        import math
        import pygame
        
        def rotate_polygon(points, angle_deg, offset_x, offset_y):
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            rotated = []
            for px, py in points:
                rx = px * cos_a - py * sin_a
                ry = px * sin_a + py * cos_a
                rotated.append((rx + offset_x, ry + offset_y))
            return rotated

        for part in getattr(self, 'assembly_parts', []):
            blueprint_poly = rotate_polygon(part.shape, part.target_angle, part.target_pos[0], part.target_pos[1])
            pygame.draw.polygon(self.screen, (50, 50, 50), blueprint_poly, 2)
            
        for part in getattr(self, 'assembly_parts', []):
            if not part.is_locked:
                poly = rotate_polygon(part.shape, part.current_angle, part.current_pos[0], part.current_pos[1])
                color = (255,255,255) if part.is_grabbed else part.color
                pygame.draw.polygon(self.screen, color, poly)
                pygame.draw.polygon(self.screen, (200,200,200), poly, 2)
            else:
                poly = rotate_polygon(part.shape, part.target_angle, part.target_pos[0], part.target_pos[1])
                pygame.draw.polygon(self.screen, part.color, poly)
                pygame.draw.polygon(self.screen, (0, 255, 0), poly, 3)

        inst = getattr(self, 'font_small').render("PINCH to grab, ARM to move, WRIST to rotate", True, (200, 200, 200))
        self.screen.blit(inst, inst.get_rect(center=(cx, WINDOW_HEIGHT - 40)))

    def _get_level_goals(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Select a level to begin rehabilitation"
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            return "Pop all bubbles in corners to test flexibility and reach"
        elif self.state == GameState.LEVEL2_STRENGTH:
            return "Move palm to catch falling items. Build strength!"
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            return "Pinch seeds and drop them in the pot. Fine motor control!"
        elif self.state == GameState.LEVEL4_COORDINATION:
            return "Follow the moving target smoothly to test hand stability!"
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            return "Make a FIST, then OPEN fully to pump the object!"
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            return "Memorize the pattern and repeat it!"
        return ""

    def _get_current_exercise_name(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Therapy Selection"
        if self.state == GameState.CALIBRATION:
            return "ROM Diagnostics"
        return LEVEL_DISPLAY_NAMES.get(getattr(self, "current_level", 0), "Therapeutic Training")

    def _get_exercise_count(self) -> int:
        if getattr(self, "current_level", 0) == 5:
            return int(getattr(self, "pump_reps", 0))
        return int(getattr(self, "accuracy_hits", 0))

    def _get_session_elapsed(self) -> float:
        if self.session_start:
            return max(0.0, time.time() - self.session_start)
        return 0.0

    def _get_correctness_label(self, hand_data: HandData) -> str:
        warning = getattr(self, "correctness_warning", "")
        if warning:
            if "Bend" in warning:
                return "Incorrect - adjust movement"
            return "Correct - good control"
        if hand_data.index_tip is None:
            return "Incorrect - hand missing"
        return "Ready - tracking hand"

    def _get_recovery_prediction(self) -> Optional[float]:
        now = time.time()
        cache_time = getattr(self, "_recovery_prediction_time", 0.0)
        if now - cache_time > 5.0:
            try:
                self._recovery_prediction_cache = self.db.predict_recovery_progress(self.patient_name)
            except Exception:
                self._recovery_prediction_cache = -1.0
            self._recovery_prediction_time = now
        return getattr(self, "_recovery_prediction_cache", -1.0)
    
    def _end_level(self):
        try:
            pending_summary = getattr(self, "_pending_session_summary", None)
            if pending_summary is None:
                duration = time.time() - self.session_start
                avg_accuracy = (self.accuracy_hits / self.accuracy_attempts * 100) if self.accuracy_attempts > 0 else 0
                avg_hand_angle = sum(self.angle_history) / len(self.angle_history) if len(self.angle_history) > 0 else 0
                self._pending_session_summary = {
                    "duration": duration,
                    "avg_accuracy": avg_accuracy,
                    "avg_hand_angle": avg_hand_angle,
                    "score": self.score,
                    "max_extension": self.max_extension,
                    "reach_distance": self.reach_distance,
                    "accuracy_hits": self.accuracy_hits,
                    "accuracy_attempts": self.accuracy_attempts,
                    "angle_history": list(self.angle_history),
                    "pain_before_session": int(getattr(self, "pain_before_session", self.pain_level)),
                }
                self.pain_after_session = int(getattr(self, "pain_before_session", self.pain_level))
                self.state = GameState.PAIN_AFTER_SESSION
                VOICE.speak("Please rate your pain level after completing today's exercises.")
                return

            duration = pending_summary["duration"]
            avg_accuracy = pending_summary["avg_accuracy"]
            avg_hand_angle = pending_summary["avg_hand_angle"]
            self.score = pending_summary["score"]
            self.max_extension = pending_summary["max_extension"]
            self.reach_distance = pending_summary["reach_distance"]
            pain_before_session = int(pending_summary.get("pain_before_session", self.pain_level))
            pain_after_session = int(getattr(self, "pain_after_session", pain_before_session))
            pain_difference = pain_after_session - pain_before_session
            movement_smoothness = 0.7
            if isinstance(getattr(self, "forearm_assessment", None), dict):
                movement_smoothness = float(self.forearm_assessment.get("smoothness", 0.7))
            recovery_score_value = functional_recovery_score(
                avg_hand_angle,
                avg_accuracy,
                pain_after_session,
                1.0,
                movement_smoothness,
            )
            recovery_category_value = recovery_category(recovery_score_value)
            self.pain_before_session = pain_before_session
            self.pain_after_session = pain_after_session
            self.pain_difference = pain_difference
            self.functional_recovery_score = recovery_score_value
            self.recovery_category = recovery_category_value

            qm_metrics = self.quality_tracker.calculate_metrics(self.calibrated_max_angle)
            movement_quality_score = qm_metrics["overall"]
            sub_smoothness = qm_metrics["smoothness"]
            sub_accuracy = qm_metrics["accuracy"]
            sub_rom = qm_metrics["rom"]
            sub_stability = qm_metrics["stability"]

            self.db.save_session(
                self.current_level, self.score, duration,
                avg_accuracy, self.max_extension,
                self.reach_distance, avg_hand_angle,
                pain_level=pain_before_session, patient_id=self.patient_name,
                pain_before_session=pain_before_session,
                pain_after_session=pain_after_session,
                functional_recovery_score=recovery_score_value,
                recovery_category=recovery_category_value,
                movement_smoothness=movement_smoothness,
                movement_quality_score=movement_quality_score,
                sub_smoothness=sub_smoothness,
                sub_accuracy=sub_accuracy,
                sub_rom=sub_rom,
                sub_stability=sub_stability,
            )
            session_id = getattr(self.db, 'last_session_id', None)
            
            # Generate and securely store clinical summary
            self._generate_and_save_clinical_summary(
                session_id, duration, avg_accuracy, avg_hand_angle,
                pain_before_session, pain_after_session, recovery_score_value,
                qm_metrics
            )

            rotation_smoothness = 0.7
            if isinstance(getattr(self, 'forearm_assessment', None), dict):
                rotation_smoothness = float(self.forearm_assessment.get('smoothness', 0.7))
                try:
                    self.forearm_classifier.save_assessment(
                        self.db.db_path,
                        self.patient_name or "Unknown",
                        self.current_level,
                        self.forearm_assessment,
                        session_id=session_id,
                    )
                except Exception as exc:
                    print(f"Forearm assessment save failed: {exc}")

            movement_quality = movement_quality_score / 100.0
            fatigue_index = 0.0
            if duration > 0 and self.accuracy_attempts > 0:
                fatigue_index = min(1.0, max(0.0, (duration / max(getattr(self, 'session_time_limit', LEVEL_DURATION), 1.0) - 1.0) * 0.5))
            if self.pain_level >= 6:
                fatigue_index = max(fatigue_index, min(1.0, self.pain_level / 10.0))

            try:
                recovery_prediction = self._get_recovery_prediction()
                next_prescription = self.adaptive_engine.recommend(
                    self.patient_name or "Unknown",
                    self.current_level,
                    avg_accuracy,
                    avg_hand_angle,
                    self.pain_level,
                    duration,
                    self.score,
                    movement_quality=movement_quality,
                    fatigue_index=fatigue_index,
                    rotation_smoothness=rotation_smoothness,
                    session_id=session_id,
                    recovery_prediction=recovery_prediction,
                    functional_recovery_score=recovery_score_value,
                )
                self.adaptive_recommendation = next_prescription
                sensei_message = self.adaptive_engine.coaching_message(
                    self.patient_name or "Unknown",
                    self.current_level,
                    next_prescription,
                    avg_accuracy,
                    avg_hand_angle,
                    self.pain_level,
                    fatigue_index=fatigue_index,
                    recovery_prediction=recovery_prediction,
                    session_id=session_id,
                )
                self.adaptive_sensei_message = sensei_message
                VOICE.speak(sensei_message)
            except Exception as exc:
                print(f"Adaptive recommendation failed: {exc}")

            self.session_data = self.db.get_last_session()
            if not self.session_data:
                self.session_data = {
                    'level': self.current_level,
                    'score': self.score,
                    'duration': duration,
                    'avg_accuracy': avg_accuracy,
                    'max_extension': self.max_extension,
                    'reach_distance': self.reach_distance,
                    'avg_hand_angle': avg_hand_angle
                }
            if self.session_data:
                self.session_data['summary_text'] = self.current_clinical_summary
                self.session_data['ai_recommendation'] = self.current_clinical_recommendation
            self.best_data    = self.db.get_all_time_best()
            
            # Generate Session Charts (Pie/Histogram)
            self.summary_screen.generate_session_charts(
                self.accuracy_hits, self.accuracy_attempts, list(self.angle_history)
            )

            # Auto-save text, HTML, and PDF reports
            try:
                import os
                os.makedirs("reports", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                sd = self.session_data or {}
                
                # 1. Text Report Card
                fname = f"reports/report_L{self.current_level}_{ts}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"AI Hand Rehabilitation — Session Report\n")
                    f.write(f"{'='*45}\n")
                    f.write(f"Patient  : {self.patient_name or 'Unknown'}\n")
                    f.write(f"Date     : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
                    f.write(f"Level    : {self.current_level}\n")
                    f.write(f"Pain Before: {pain_before_session}/10\n")
                    f.write(f"Pain After : {pain_after_session}/10\n")
                    f.write(f"Pain Change: {pain_difference:+d}\n")
                    f.write(f"Recovery Score: {recovery_score_value:.1f}/100 ({recovery_category_value})\n")
                    f.write(f"Movement Quality: {movement_quality_score:.1f}% ({qm_metrics['rating']})\n")
                    f.write(f"  - Smoothness: {sub_smoothness:.1f}%\n")
                    f.write(f"  - Accuracy: {sub_accuracy:.1f}%\n")
                    f.write(f"  - Range of Motion: {sub_rom:.1f}%\n")
                    f.write(f"  - Stability: {sub_stability:.1f}%\n")
                    f.write(f"\n-- Clinical Summary & Recommendation --\n")
                    f.write(f"Summary: {self.current_clinical_summary}\n")
                    f.write(f"Recommendation: {self.current_clinical_recommendation}\n")
                    f.write(f"\n-- Performance --\n")
                    f.write(f"Score    : {sd.get('score', self.score)}\n")
                    f.write(f"Accuracy : {sd.get('avg_accuracy', 0):.1f}%\n")
                    f.write(f"ROM Angle: {sd.get('avg_hand_angle', 0):.1f}°\n")
                    f.write(f"Duration : {sd.get('duration', 0):.0f}s\n")
                    f.write(f"\n-- All-Time Best --\n")
                    bd = self.best_data or {}
                    f.write(f"Best Score   : {bd.get('score', 0)}\n")
                    f.write(f"Best Accuracy: {bd.get('accuracy', 0):.1f}%\n")
                    f.write(f"Best ROM     : {bd.get('angle', 0):.1f}°\n")
                print(f"Text Report saved: {fname}")

                # 2. Premium Clinical HTML Report Card
                html_fname = f"reports/session_report_L{self.current_level}_{ts}.html"
                
                LEVEL_NAMES = [
                    "Flexibility - Pop the Bubbles",
                    "Flexibility - Pop the Bubbles", 
                    "Strength & Speed - Catch the Apples", 
                    "Fine Motor - Plant the Seeds", 
                    "Coordination - Trace the Path", 
                    "Grip & Release - Balloon Pump", 
                    "Cognitive Precision - Simon Pattern Tap"
                ]
                level_name_str = LEVEL_NAMES[self.current_level] if self.current_level < len(LEVEL_NAMES) else "Therapeutic Training"
                
                acc_val = sd.get('avg_accuracy', 0)
                rom_val = sd.get('avg_hand_angle', 0)
                dur_val = sd.get('duration', 0)
                
                suggestions_list = []
                if acc_val >= 85:
                    suggestions_list.append("Patient demonstrated exceptional target accuracy. Recommend advancing to the next difficulty tier or level.")
                elif acc_val >= 60:
                    suggestions_list.append("Good neuromuscular accuracy. Continue with the current protocol to build muscle memory and control.")
                else:
                    suggestions_list.append("Target accuracy is low. Encourage slower, more deliberate hand movements. Consider a pediatric or senior mode to expand target radii.")

                if rom_val >= 45:
                    suggestions_list.append("Average finger flexion is excellent, showing deep range of motion. Joint flexibility is healthy.")
                else:
                    suggestions_list.append("Reduced range of motion (ROM) detected. Incorporate warm-up finger stretching exercises before sessions.")

                if self.pain_level >= 5:
                    suggestions_list.append("WARNING: High patient pain level reported. Shorten session duration, encourage regular pauses, and consult with the attending therapist.")
                else:
                    suggestions_list.append("Patient reported minimal pain during this session. Good tolerability of the motor exercises.")
                
                suggestions_html = "\n".join([f"<li>{s}</li>" for s in suggestions_list])
                
                html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Therapy Session Report - L{self.current_level}</title>
    <style>
        :root {{
            --bg-color: #080c16;
            --card-bg: rgba(13, 22, 42, 0.7);
            --border-color: rgba(0, 255, 204, 0.2);
            --accent-glow: #00ffcc;
            --accent-blue: #0088ff;
            --text-primary: #ffffff;
            --text-secondary: #8fa0c0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .report-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 800px;
            box-shadow: 0 8px 32px 0 rgba(0, 255, 204, 0.08);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            position: relative;
            overflow: hidden;
        }}
        .report-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-glow));
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(143, 160, 192, 0.15);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 1px;
            background: linear-gradient(90deg, #ffffff, var(--accent-glow));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-meta {{
            text-align: right;
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .patient-info {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .info-item {{
            display: flex;
            flex-direction: column;
        }}
        .info-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .info-value {{
            font-size: 18px;
            font-weight: 600;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 35px;
        }}
        .metric-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .metric-details h3 {{
            margin: 0 0 5px 0;
            font-size: 14px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}
        .metric-details .value {{
            font-size: 28px;
            font-weight: 700;
            color: var(--accent-glow);
        }}
        .radial-indicator {{
            position: relative;
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: conic-gradient(var(--accent-glow) {acc_val}%, rgba(255, 255, 255, 0.08) 0);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .radial-indicator::after {{
            content: '{acc_val:.1f}%';
            position: absolute;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #0d162a;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 600;
        }}
        .clinical-suggestions {{
            background: rgba(0, 255, 204, 0.04);
            border: 1px dashed var(--border-color);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
        }}
        .clinical-suggestions h2 {{
            margin-top: 0;
            font-size: 18px;
            color: var(--accent-glow);
            letter-spacing: 0.5px;
        }}
        .clinical-suggestions ul {{
            margin: 0;
            padding-left: 20px;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        .clinical-suggestions li {{
            margin-bottom: 8px;
        }}
        .footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 12px;
            border-top: 1px solid rgba(143, 160, 192, 0.15);
            padding-top: 20px;
        }}
        @media print {{
            body {{
                background: #fff;
                color: #000;
                padding: 0;
            }}
            .report-card {{
                border: none;
                box-shadow: none;
                background: none;
                padding: 0;
                backdrop-filter: none;
            }}
            .report-card::before {{
                display: none;
            }}
            .metric-card, .patient-info {{
                border: 1px solid #ddd;
                background: #fff;
                color: #000;
            }}
            .metric-details .value {{
                color: #000;
            }}
            .radial-indicator::after {{
                background: #fff;
                color: #000;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-card">
        <div class="header">
            <div>
                <h1>CLINICAL THERAPY REPORT</h1>
                <span style="color: var(--accent-glow); font-size: 12px; letter-spacing: 2px;">NEURAL BIO-FEEDBACK SUITE</span>
            </div>
            <div class="header-meta">
                <div>SESSION TIMESTAMP</div>
                <div>{datetime.now().strftime('%d %B %Y %H:%M')}</div>
            </div>
        </div>

        <div class="patient-info">
            <div class="info-item">
                <span class="info-label">Patient Name</span>
                <span class="info-value">{self.patient_name or 'Unknown'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Demographic</span>
                <span class="info-value">{self.age_group.value if self.age_group else 'Adult'} (Age {self.patient_age or '30'})</span>
            </div>
            <div class="info-item">
                <span class="info-label">Therapy Protocol</span>
                <span class="info-value">Level {self.current_level} - {level_name_str}</span>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Performance Score</h3>
                    <div class="value">{sd.get('score', self.score)}</div>
                </div>
                <div style="font-size: 24px;">🏆</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Target Accuracy</h3>
                    <div class="value">{acc_val:.1f}%</div>
                </div>
                <div class="radial-indicator"></div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Range of Motion (ROM)</h3>
                    <div class="value">{rom_val:.1f}°</div>
                </div>
                <div style="font-size: 24px; color: var(--accent-glow);">📐</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Pain Before / After</h3>
                    <div class="value">{pain_before_session}/10 to {pain_after_session}/10 <span style="font-size: 16px; font-weight: normal; color: var(--text-secondary);">({pain_difference:+d})</span></div>
                </div>
                <div style="font-size: 24px;">⚡</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Movement Quality</h3>
                    <div class="value">{movement_quality_score:.1f}%</div>
                    <div style="font-size: 11px; color: var(--text-secondary); line-height: 1.4; margin-top: 4px;">
                        Smoothness: {sub_smoothness:.1f}% | ROM: {sub_rom:.1f}%<br>
                        Accuracy: {sub_accuracy:.1f}% | Stability: {sub_stability:.1f}%
                    </div>
                </div>
                <div style="font-size: 24px; color: var(--accent-glow);">⭐</div>
            </div>
        </div>

        <div class="clinical-suggestions">
            <h2>CLINICAL OBSERVATIONS & SUGGESTIONS</h2>
            <ul>
                {suggestions_html}
            </ul>
        </div>

        <div class="clinical-suggestions" style="background: rgba(0, 136, 255, 0.04); border-color: rgba(0, 136, 255, 0.2);">
            <h2>AI CLINICAL SUMMARY</h2>
            <p style="color: var(--text-secondary); line-height: 1.6; margin-bottom: 15px;">{self.current_clinical_summary}</p>
            <h2 style="color: var(--accent-blue);">THERAPEUTIC RECOMMENDATION</h2>
            <p style="color: var(--text-primary); font-weight: 600; margin: 0;">{self.current_clinical_recommendation}</p>
        </div>

        <div class="footer">
            Generated by Zero-Keyboard AI Hand Rehabilitation System | Confidential Medical Record
        </div>
    </div>
</body>
</html>"""
                with open(html_fname, "w", encoding="utf-8") as f:
                    f.write(html_template)
                print(f"HTML Report saved: {html_fname}")
                VOICE.speak("Clinical report exported to reports folder.")
                
                # 3. PDF Generation (with fixed imports and variables)
                try:
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter
                    pdf_fname = f"reports/report_L{self.current_level}_{ts}.pdf"
                    c = canvas.Canvas(pdf_fname, pagesize=letter)
                    c.setFont("Helvetica-Bold", 24)
                    c.setFillColorRGB(0, 0.4, 0.6)
                    c.drawString(50, 750, "AI Hand Rehabilitation - Clinical Report")
                    
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(50, 710, f"Patient Name: {self.patient_name or 'Unknown'}")
                    c.drawString(50, 690, f"Date: {datetime.now().strftime('%d %B %Y  %H:%M')}")
                    c.drawString(50, 670, f"Diagnostic Level: {self.current_level}")
                    c.drawString(50, 650, f"Pain Before Session: {pain_before_session}/10")
                    c.drawString(50, 632, f"Pain After Session: {pain_after_session}/10")
                    c.drawString(50, 614, f"Pain Difference: {pain_difference:+d}")
                    
                    c.setFont("Helvetica-Bold", 16)
                    c.setFillColorRGB(0, 0.3, 0.5)
                    c.drawString(50, 585, "Session Telemetry")
                    
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(50, 565, f"Final Score: {sd.get('score', self.score)}")
                    c.drawString(50, 545, f"Target Accuracy: {acc_val:.1f}%")
                    c.drawString(50, 525, f"Average Range of Motion: {rom_val:.1f} degrees")
                    c.drawString(50, 505, f"Therapy Duration: {dur_val:.0f} seconds")
                    c.drawString(50, 485, f"Functional Recovery Score: {recovery_score_value:.1f}/100 ({recovery_category_value})")
                    c.drawString(50, 465, f"Movement Quality Score: {movement_quality_score:.1f}% ({qm_metrics['rating']})")
                    c.setFont("Helvetica-Oblique", 10)
                    c.drawString(70, 448, f"Smoothness: {sub_smoothness:.1f}% | Hold Stability: {sub_stability:.1f}% | Accuracy: {sub_accuracy:.1f}% | ROM: {sub_rom:.1f}%")
                    
                    c.setFont("Helvetica-Bold", 14)
                    c.setFillColorRGB(0, 0.3, 0.5)
                    c.drawString(50, 420, "AI Clinical Summary & Recommendation")
                    
                    c.setFont("Helvetica-Oblique", 11)
                    c.setFillColorRGB(0.15, 0.15, 0.15)
                    summary_lines = []
                    words = self.current_clinical_summary.split()
                    line = ""
                    for w in words:
                        test_line = line + w + " "
                        if len(test_line) > 85:
                            summary_lines.append(line)
                            line = w + " "
                        else:
                            line = test_line
                    if line:
                        summary_lines.append(line)
                        
                    curr_y = 402
                    for sl in summary_lines:
                        c.drawString(50, curr_y, sl)
                        curr_y -= 15
                        
                    curr_y -= 5
                    c.setFont("Helvetica-Bold", 11)
                    c.setFillColorRGB(0.1, 0.5, 0.3)
                    c.drawString(50, curr_y, "Therapeutic Recommendation:")
                    curr_y -= 15
                    c.setFont("Helvetica", 11)
                    c.setFillColorRGB(0, 0, 0)
                    
                    rec_lines = []
                    words = self.current_clinical_recommendation.split()
                    line = ""
                    for w in words:
                        test_line = line + w + " "
                        if len(test_line) > 85:
                            rec_lines.append(line)
                            line = w + " "
                        else:
                            line = test_line
                    if line:
                        rec_lines.append(line)
                        
                    for rl in rec_lines:
                        c.drawString(50, curr_y, rl)
                        curr_y -= 15
                    
                    c.save()
                    print(f"PDF Report saved: {pdf_fname}")
                except Exception as pdf_e:
                    print(f"PDF save warning: {pdf_e}")
                    
            except Exception as re:
                print(f"Report save warning: {re}")

            # Big celebration burst

            cx = GAME_AREA_WIDTH // 2
            for _ in range(5):
                self.particles.emit(cx + random.randint(-200, 200),
                                    WINDOW_HEIGHT // 2,
                                    random.choice([(255,215,0),(0,220,120),(0,200,255),(255,100,150)]),
                                    30)

            # Go to LEVEL_COMPLETE celebration screen first
            self._pending_session_summary = None
            self._level_complete_time = time.time()
            self.state = GameState.LEVEL_COMPLETE
            self.sounds.play('level_complete')
            self.screen_shake = 25

        except Exception as e:
            print(f"Error in _end_level: {e}")
            self.state = GameState.MAIN_MENU
            self._reset_game()

    def _generate_and_save_clinical_summary(self, session_id, duration, avg_accuracy, avg_hand_angle, pain_before, pain_after, recovery_score, qm_metrics):
        try:
            # Gather compensation events
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT compensation_type, severity FROM compensation_events WHERE session_id = ?", (session_id,))
            comp_rows = cursor.fetchall()
            conn.close()
            
            comp_summary = ""
            if comp_rows:
                comp_counts = {}
                for r in comp_rows:
                    comp_counts[r[0]] = comp_counts.get(r[0], 0) + 1
                comp_summary = " Compensations: " + ", ".join([f"{k} (x{v})" for k, v in comp_counts.items()]) + "."
            else:
                comp_summary = " No significant compensation detected."
                
            pain_delta = pain_after - pain_before
            pain_text = f"Pain was stable at {pain_after}/10." if pain_delta == 0 else (
                f"Pain increased by {pain_delta} to {pain_after}/10." if pain_delta > 0 else
                f"Pain decreased by {abs(pain_delta)} to {pain_after}/10."
            )
            
            summary_text = (
                f"Completed Level {self.current_level} in {duration:.1f}s. "
                f"Movement Quality was {qm_metrics['overall']:.1f}% ({qm_metrics['rating']}), "
                f"featuring {qm_metrics['smoothness']:.1f}% smoothness, {qm_metrics['stability']:.1f}% hold stability. "
                f"Average joint flexion reached {avg_hand_angle:.1f}° with {avg_accuracy:.1f}% target hit accuracy."
                f"{comp_summary} {pain_text} Functional Recovery Score: {recovery_score:.1f}%."
            )
            
            # Formulate AI Recommendation
            if qm_metrics['overall'] >= 85 and pain_after <= 3:
                ai_rec = f"Increase difficulty. Patient displays high compliance and stable joint control. Recommend advancing to Level {min(8, self.current_level + 1)}."
            elif pain_after >= 6:
                ai_rec = "Reduce intensity. Elevated pain scores detected. Incorporate warm-up stretches and longer pause intervals."
            else:
                ai_rec = "Maintain current training pace. Continue tracking range of motion and focus on smoothness to reduce compensatory patterns."
                
            # Encrypt securely using non-deterministic encryption
            enc_summary = security_utils.encrypt_non_deterministic(summary_text)
            enc_rec = security_utils.encrypt_non_deterministic(ai_rec)
            
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO clinical_summaries (session_id, summary_text, ai_recommendation)
                VALUES (?, ?, ?)
            """, (session_id, enc_summary, enc_rec))
            conn.commit()
            conn.close()
            
            self.current_clinical_summary = summary_text
            self.current_clinical_recommendation = ai_rec
            print("[SUCCESS] Clinical summary generated and stored securely.")
        except Exception as e:
            print(f"Error generating clinical summary: {e}")
            self.current_clinical_summary = "Report summary telemetry compilation in progress."
            self.current_clinical_recommendation = "Maintain standard recovery protocol."

    def _run_clinical_analysis(self, hand_data):
        gameplay_states = [
            GameState.LEVEL1_FLEXIBILITY,
            GameState.LEVEL2_STRENGTH,
            GameState.LEVEL3_FINEMOTOR,
            GameState.LEVEL4_COORDINATION,
            GameState.LEVEL5_GRIP_RELEASE,
            GameState.LEVEL6_FINGER_TAPS,
            GameState.LEVEL7_WRIST_MECHANICS,
            GameState.LEVEL8_SMART_ASSEMBLY
        ]
        if self.state in gameplay_states and hand_data and hand_data.index_tip is not None:
            active_hold = False
            if self.state == GameState.LEVEL3_FINEMOTOR and hand_data.is_pinching:
                active_hold = True
            elif self.state == GameState.LEVEL5_GRIP_RELEASE and hand_data.is_fist:
                active_hold = True
            elif self.state == GameState.LEVEL7_WRIST_MECHANICS and hasattr(self, 'hold_timer') and getattr(self, 'hold_timer', 0) > 0:
                active_hold = True
                
            self.quality_tracker.update(hand_data, is_active_session=True, active_hold=active_hold)
            self.quality_tracker.record_accuracy(self.accuracy_hits, self.accuracy_attempts)
            
            # Analyze compensation
            detected, comp_type, desc, severity = self.compensation_detector.analyze(hand_data, self.current_level)
            if detected:
                self.sounds.play('select')
                self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 100, WINDOW_HEIGHT // 2, "COMPENSATION DETECTED!", (255, 50, 50)))
                session_id = getattr(self.db, 'last_session_id', None)
                try:
                    conn = sqlite3.connect(self.db.db_path)
                    cursor = conn.cursor()
                    enc_patient = security_utils.encrypt_deterministic(self.patient_name or "Unknown")
                    cursor.execute("""
                        INSERT INTO compensation_events (patient_id, session_id, exercise, compensation_type, severity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (enc_patient, session_id, LEVEL_DISPLAY_NAMES.get(self.current_level, "Unknown"), comp_type, severity))
                    conn.commit()
                    conn.close()
                except Exception as exc:
                    print(f"Failed to log compensation event: {exc}")

    def _update_readiness_and_difficulty(self):
        if not self.patient_name:
            self.readiness_score = 50.0
            self.recommended_difficulty = "Moderate"
            self.recommended_difficulty_explanation = "Ready for baseline therapy."
            return
            
        try:
            enc_name = security_utils.encrypt_deterministic(self.patient_name)
            conn = sqlite3.connect(self.db.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT avg_accuracy, avg_hand_angle, pain_after_session, movement_quality_score, duration
                FROM sessions WHERE patient_id = ? ORDER BY id DESC LIMIT 5
            """, (enc_name,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                self.readiness_score = 65.0
                self.recommended_difficulty = "Moderate"
                self.recommended_difficulty_explanation = "Initial baseline. Calibrated ROM will adjust game scale."
                return
                
            avg_acc = sum(r[0] for r in rows) / len(rows)
            avg_rom = sum(r[1] for r in rows) / len(rows)
            avg_pain = sum(r[2] for r in rows) / len(rows)
            avg_mq = sum(r[3] for r in rows) / len(rows) * 100.0 if rows[0][3] is not None else 75.0
            avg_dur = sum(r[4] for r in rows) / len(rows)
            
            fatigue = min(100.0, max(0.0, (avg_dur / 45.0) * 20.0 + avg_pain * 5.0))
            
            rom_factor = min(100.0, (avg_rom / 90.0) * 100.0)
            acc_factor = avg_acc
            mq_factor = avg_mq
            pain_penalty = avg_pain * 8.0
            fatigue_penalty = fatigue * 0.4
            
            readiness = (rom_factor * 0.4 + acc_factor * 0.3 + mq_factor * 0.3) - pain_penalty - fatigue_penalty
            readiness = max(10.0, min(100.0, readiness))
            self.readiness_score = round(readiness, 1)
            
            if readiness >= 80.0:
                self.recommended_difficulty = "Hard"
                self.recommended_difficulty_explanation = f"Patient shows excellent coordination ({avg_acc:.0f}% accuracy) and high ROM ({avg_rom:.0f}°) with low pain ({avg_pain:.1f}/10). Recommended to increase challenge."
            elif readiness >= 50.0:
                self.recommended_difficulty = "Moderate"
                self.recommended_difficulty_explanation = f"Patient is stable with moderate ROM ({avg_rom:.0f}°) and tolerable pain ({avg_pain:.1f}/10). Recommended to maintain current difficulty pace."
            else:
                self.recommended_difficulty = "Easy"
                self.recommended_difficulty_explanation = f"Low readiness ({readiness:.1f}) detected due to high pain ({avg_pain:.1f}/10) or limited movement quality. Recommended easy setting for clinical safety."
                
        except Exception as e:
            print(f"Error calculating readiness: {e}")
            self.readiness_score = 55.0
            self.recommended_difficulty = "Moderate"
            self.recommended_difficulty_explanation = "Maintained moderate baseline due to telemetry calculation fallback."


    
    def _run_virtual_sensei(self, hand_data: HandData):
        """AI-driven therapeutic coaching"""
        if self.state not in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, GameState.LEVEL3_FINEMOTOR, GameState.LEVEL4_COORDINATION, GameState.LEVEL5_GRIP_RELEASE, GameState.LEVEL6_FINGER_TAPS]:
            return
            
        now = time.time()
        if now - self.last_coach_time < self.coaching_cooldown:
            return
            
        # 1. Performance Feedback
        accuracy = (self.accuracy_hits / self.accuracy_attempts * 100) if self.accuracy_attempts > 0 else 100
        
        # Check for poor ROM
        if hand_data.finger_extension > 0 and hand_data.finger_extension < 120:
            VOICE.speak("Try to open your hand fully to improve range of motion.")
            self.last_coach_time = now
            return

        # Check for poor accuracy
        if self.accuracy_attempts > 10 and accuracy < 50:
            VOICE.speak("Slow down and focus on the center of the targets.")
            self.last_coach_time = now
            return

        # Check for great performance (encouragement)
        if self.combo > 8:
            VOICE.speak("Excellent control! Your motor precision is improving.")
            self.last_coach_time = now
            return

        # Check for steady progress
        if now - self.session_start > 20:
            VOICE.speak("Stay focused. You are doing a great job today.")
            self.last_coach_time = now

    def _reset_game(self):
        self.bubbles.clear()
        self.falling_items.clear()
        self.seeds.clear()
        self.score = 0
        self.max_extension = 0
        self.reach_distance = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.angle_history.clear()
        self.combo = 0
        self.feedback_text = None
        self.feedback_timer = 0
        if hasattr(self, 'quality_tracker'):
            self.quality_tracker.reset()
        if hasattr(self, 'compensation_detector'):
            self.compensation_detector.reset()
    
    def _trigger_feedback(self):
        """Trigger visual feedback based on combo"""
        if self.combo >= 15 and "combo15" not in self.achievements_unlocked:
            self.achievements_unlocked.add("combo15")
            self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, 120, "ACHIEVEMENT: 15 COMBO!"))
            self.sounds.play('level_complete')
            
        if self.combo >= 10:
            if "combo10" not in self.achievements_unlocked:
                self.achievements_unlocked.add("combo10")
                self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, 120, "ACHIEVEMENT: 10 COMBO!"))
                self.sounds.play('level_complete')
            self.feedback_text = "AMAZING!"
            self.feedback_timer = 60
        elif self.combo >= 7:
            self.feedback_text = "EXCELLENT!"
            self.feedback_timer = 50
        elif self.combo >= 4:
            self.feedback_text = "GREAT!"
            self.feedback_timer = 40
            self.sounds.play('combo')
        elif self.combo >= 2:
            self.feedback_text = "GOOD!"
            self.feedback_timer = 30
            
    def _adjust_pacing(self, change_type: str):
        """Dynamic pacing adjustment with sound cues and visual popup HUD alerts."""
        now = time.time()
        should_speak = (now - getattr(self, 'last_pacing_voice_time', 0.0)) > 10.0

        if change_type == "slow":
            self.pacing_multiplier = max(0.5, self.pacing_multiplier - 0.15)
            self.sounds.play('select')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 80, WINDOW_HEIGHT // 2, "PACING: SLOWER", (255, 128, 0)))
            if should_speak:
                VOICE.speak("Pacing adjusted. Let's take it slow and steady.")
                self.last_pacing_voice_time = now
        elif change_type == "fast":
            self.pacing_multiplier = min(1.4, self.pacing_multiplier + 0.1)
            self.sounds.play('level_complete')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 80, WINDOW_HEIGHT // 2, "PACING: FASTER!", COLOR_SUCCESS))
            if should_speak:
                VOICE.speak("Excellent coordination! Pacing up slightly.")
                self.last_pacing_voice_time = now
    
    def _update_results(self, hand_data: HandData):
        """Update results screen"""
        # Debounce safeguard for hand lost tracking in results screen
        if hand_data.index_tip is None:
            if not hasattr(self, '_results_lost_t') or self._results_lost_t is None:
                self._results_lost_t = time.time()
            if time.time() - self._results_lost_t > 0.8:
                self.results_mirror_active = True
        else:
            self._results_lost_t = None
            self.results_mirror_active = False

        if self.close_button.update(hand_data.index_tip):
            self.running = False
        
        # PLAY AGAIN
        if self.menu_button.update(hand_data.index_tip):
            # Replay current level
            self.pending_level = self.current_level
            self._reset_game()
            self._start_level()
            self.sounds.play('select')
        
        # MAIN MENU (Via Cloud Sync)
        if self.home_button.update(hand_data.index_tip):
            self.state = GameState.CLOUD_SYNC
            self.sync_start = time.time()
            self.sounds.play('select')
            self.home_button.hover_start = None
            self.menu_button.hover_start = None
            self.close_button.hover_start = None
            if hasattr(self, 'next_button'):
                self.next_button.hover_start = None
                
        # NEXT GAME
        if hasattr(self, 'next_button') and getattr(self, 'current_level', 1) < 8 and self.next_button.update(hand_data.index_tip):
            self.pending_level = min(8, self.current_level + 1)
            self.sounds.play('select')
            self.menu_button.hover_start = None
            self.close_button.hover_start = None
            self.next_button.hover_start = None
            self.home_button.hover_start = None
            if not getattr(self, 'pain_checked', False):
                self.pain_level = 0
                self.state = GameState.PAIN_SCALE
            else:
                self._start_level()

    # ── Pain scale helpers ──────────────────────────────────────────────
    def _start_level(self):
        """Actually start the pending level after pain score captured"""
        self.game_has_started = False
        lv = self.pending_level or 1
        self.current_level = lv
        self.session_start = time.time()
        self.level_wall_start = time.time()
        self.score = 0
        self.max_extension = 0
        self.reach_distance = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.pacing_multiplier = 1.0
        self.consecutive_misses = 0
        self.last_pacing_voice_time = 0.0
        self.recent_tracing_attempts = 0
        self.recent_tracing_hits = 0
        self._apply_adaptive_prescription(lv)
        if lv == 1:
            self.state = GameState.LEVEL1_FLEXIBILITY
            self._spawn_bubbles()
            VOICE.speak("Level 1: Bubble Pop. Extend your index finger and touch the moving bubbles to pop them and improve flexibility.")
        elif lv == 2:
            self.state = GameState.LEVEL2_STRENGTH
            VOICE.speak("Level 2: Fruit Catch. Move your hand left and right to catch the falling apples in the basket.")
        elif lv == 3:
            self.state = GameState.LEVEL3_FINEMOTOR
            VOICE.speak("Level 3: Fine Motor. Close your index and thumb to pinch and pick up seeds, then drop them in the pot.")
        elif lv == 4:
            self.state = GameState.LEVEL4_COORDINATION
            self.trace_t = 0.0
            self.trace_path = []
            VOICE.speak("Level 4: Trace the Path. Move your index finger along the dotted line to trace the medical pattern.")
        elif lv == 5:
            self.state = GameState.LEVEL5_GRIP_RELEASE
            self.pump_state = 0
            self.pump_reps = 0
            self.balloon_scale = 1.0
            VOICE.speak("Level 5: Balloon Pump. Close your hand into a fist, then open it fully to pump up the balloon.")
        elif lv == 6:
            self.state = GameState.LEVEL6_FINGER_TAPS
            self.simon_sequence = []
            self.simon_state = "START"
            VOICE.speak("Level 6: Pattern Tap. Memorize the blinking pattern, then hover over the colored pads in correct order.")
        elif lv == 7:
            self.state = GameState.LEVEL7_WRIST_MECHANICS
            self.wrist_target_angle = 45.0
            self.wrist_hold_time = 0.0
            self.wrist_mode = "rotation"
            self.wrist_rotation_baseline = None
            VOICE.speak("Level 7: Rotation Orbit. Rotate your forearm to align the satellite with the orbital target.")
        elif lv == 8:
            self.state = GameState.LEVEL8_SMART_ASSEMBLY
            cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
            
            base_shape = [(-50, -50), (50, -50), (50, 50), (-50, 50)]
            roof_shape = [(-60, 40), (60, 40), (0, -40)]
            
            import random
            self.assembly_parts = [
                AssemblyPart("Base", (cx, cy+50), 0.0, [150.0, 200.0], random.uniform(-45, 45), (100, 150, 200), base_shape),
                AssemblyPart("Roof", (cx, cy-40), 0.0, [GAME_AREA_WIDTH-150.0, 200.0], random.uniform(-45, 45), (200, 100, 100), roof_shape)
            ]
            VOICE.speak("Level 8: Smart Assembly. Pinch a piece to grab it, drag it to the blueprint, and rotate your wrist to fit it.")
        self.sounds.play('select')
        self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, WINDOW_HEIGHT//2 - 60, "POSTURE FIX: Sit up & keep shoulders relaxed!"))

    def _apply_adaptive_prescription(self, level: int):
        """Load the latest AI prescription and map it onto game parameters."""
        try:
            prescription = self.adaptive_engine.latest_prescription(self.patient_name or "Unknown", level)
        except Exception as exc:
            print(f"Adaptive prescription unavailable: {exc}")
            prescription = None

        self.active_prescription = prescription
        self.adaptive_target_scale = getattr(prescription, "target_scale", 1.0)
        self.adaptive_speed_scale = getattr(prescription, "speed_scale", 1.0)
        self.session_time_limit = getattr(prescription, "time_limit", LEVEL_DURATION)
        self.adaptive_guidance_level = getattr(prescription, "guidance_level", "standard")
        self.rotation_tolerance = getattr(prescription, "rotation_tolerance", 25.0)
        self.rotation_hold_required = getattr(prescription, "hold_seconds", 1.5)
        self.assembly_position_tolerance = getattr(prescription, "assembly_position_tolerance", 50.0)
        self.assembly_angle_tolerance = getattr(prescription, "assembly_angle_tolerance", 30.0)
        self.forearm_angle_history.clear()
        self.forearm_assessment = None

        if prescription:
            print(
                "[ADAPTIVE] "
                f"L{level} tier {prescription.difficulty_tier}: "
                f"{prescription.progression} | {prescription.rationale}"
            )
            if prescription.guidance_level == "high":
                VOICE.speak("Adaptive support is active. Targets are easier and pacing is slower for safer control.")
            elif prescription.progression == "advance":
                VOICE.speak("Adaptive challenge is active. The next task will be slightly harder.")

    def _update_pain_scale(self, hand_data: HandData):
        """Select a pain dot (0-10) using either hands-free hover (1.5s) or physical mouse click"""
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        dot_spacing = 90
        total_w = 10 * dot_spacing
        start_x = cx - total_w // 2
        dy = cy - 60

        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]

        # 1. Physical Mouse Click Support (Instant Selection for high accessibility)
        if m_clicked:
            for i in range(11):
                dx = start_x + i * dot_spacing
                dist = math.sqrt((m_pos[0] - dx)**2 + (m_pos[1] - dy)**2)
                if dist < 32:  # Expanded hit radius to 32px for easy touch clicks
                    self._accept_pain_score(i)
                    # Clear hover cache
                    if hasattr(self, '_pain_hover'):
                        del self._pain_hover
                        del self._pain_hover_t
                    return

        # 2. Hands-Free Hover Support
        if hand_data.index_tip:
            for i in range(11):
                dx = start_x + i * dot_spacing
                dist = math.sqrt((hand_data.index_tip[0] - dx)**2 +
                                 (hand_data.index_tip[1] - dy)**2)
                if dist < 28:
                    if not hasattr(self, '_pain_hover') or self._pain_hover != i:
                        self._pain_hover    = i
                        self._pain_hover_t  = time.time()
                    elif time.time() - self._pain_hover_t > 1.5:
                        self._accept_pain_score(i)
                    return

        # No dot hovered
        if hasattr(self, '_pain_hover'):
            del self._pain_hover
            del self._pain_hover_t

    def _accept_pain_score(self, score: int):
        if self.state == GameState.PAIN_AFTER_SESSION:
            self.pain_after_session = int(score)
            self._end_level()
            return
        self.pain_level = int(score)
        self.pain_before_session = int(score)
        self.pain_after_session = int(score)
        self.pain_difference = 0
        self.pain_checked = True
        VOICE.speak("Pain score recorded. Starting your rehabilitation exercise.")
        self._start_level()

    def _draw_pain_scale(self):
        """Full-screen NRS 0-10 pain scale with visual indicators"""
        t  = time.time()
        cy = WINDOW_HEIGHT // 2
        cx = WINDOW_WIDTH  // 2

        self.screen.fill((8, 14, 30))

        # Header
        pygame.draw.rect(self.screen, (15, 25, 55),
                         pygame.Rect(0, 0, WINDOW_WIDTH, 80))
        after_session = self.state == GameState.PAIN_AFTER_SESSION
        title = "Post-Session Pain Assessment" if after_session else "Pain Level Assessment"
        h1 = self.font_large.render(title, True, (0, 200, 255))
        self.screen.blit(h1, h1.get_rect(center=(cx, 40)))

        prompt = (
            "Please rate your pain level after completing today's exercises.  (0 = No Pain   10 = Worst Pain)"
            if after_session
            else "Please rate your current pain level from 0 to 10.  (0 = No Pain   10 = Worst Pain)"
        )
        sub = self.font_small.render(prompt, True, (130, 160, 200))
        self.screen.blit(sub, sub.get_rect(center=(cx, cy - 160)))

        # WHO NRS descriptors
        descriptors = {0:"None", 1:"Min", 2:"Mild", 3:"Mild",
                       4:"Mod", 5:"Mod", 6:"Mod",
                       7:"High", 8:"High", 9:"V.High", 10:"Extreme"}
        colors_nrs = [(50,220,120),(100,230,130),(160,230,100),(200,230,80),
                      (255,220,0),(255,190,0),(255,150,0),(255,100,0),
                      (240,60,60),(220,30,30),(200,0,0)]
        dot_spacing = 90
        total_w = 10 * dot_spacing
        start_x = cx - total_w // 2
        hover_i  = getattr(self, '_pain_hover', -1)
        hover_t  = getattr(self, '_pain_hover_t', t)

        for i in range(11):
            dx = start_x + i * dot_spacing
            dy = cy - 60
            col = colors_nrs[i]
            r   = 22 if i != hover_i else 30

            # Ring progress if hovered
            if i == hover_i:
                progress = min((t - hover_t) / 1.5, 1.0)
                pygame.draw.circle(self.screen, col, (dx, dy), r + 6, 5)
                arc_r = r + 10
                # Draw progress arc by drawing segments
                segs = int(progress * 36)
                for s in range(segs):
                    a1 = math.radians(-90 + s * 10)
                    a2 = math.radians(-90 + (s+1) * 10)
                    p1 = (int(dx + arc_r * math.cos(a1)), int(dy + arc_r * math.sin(a1)))
                    p2 = (int(dx + arc_r * math.cos(a2)), int(dy + arc_r * math.sin(a2)))
                    pygame.draw.line(self.screen, (255,255,255), p1, p2, 3)
            else:
                pygame.draw.circle(self.screen, tuple(int(c*0.5) for c in col), (dx, dy), r)

            pygame.draw.circle(self.screen, col, (dx, dy), r, 3)

            # Number
            nm = self.font_medium.render(str(i), True, col if i != hover_i else (255,255,255))
            self.screen.blit(nm, nm.get_rect(center=(dx, dy)))

            # Descriptor below
            dc = self.font_hint.render(descriptors[i], True, col)
            self.screen.blit(dc, dc.get_rect(center=(dx, dy + 50)))

        # Selected pain label
        if hover_i >= 0:
            lbl = self.font_medium.render(
                f"Pain: {hover_i}/10 — {descriptors[hover_i]}   Hold 1.5s to confirm",
                True, colors_nrs[hover_i])
            self.screen.blit(lbl, lbl.get_rect(center=(cx, cy + 35)))
        else:
            hint = self.font_small.render(
                "Point your index finger at a number to select",
                True, (80, 120, 160))
            self.screen.blit(hint, hint.get_rect(center=(cx, cy + 35)))

        # Floating PIP Hand Alignment Camera
        pip_w, pip_h = 320, 240
        pip_x = cx - pip_w // 2
        pip_y = 425
        self._draw_camera_preview(pip_x, pip_y, pip_w, pip_h, label="PAIN ASSESS HAND ALIGNMENT")

        # Clinical note
        note = self.font_hint.render(
            "NRS Scale — Even with 0 (No Pain), repetitive coordination and ROM exercises are critical to rebuild neural motor pathways.",
            True, (60, 90, 130))
        self.screen.blit(note, note.get_rect(center=(cx, WINDOW_HEIGHT - 22)))

        # Cursor
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)

    def _update_history(self, hand_data: HandData):
        """Fist 2s returns to menu; otherwise just idle"""
        # Purge button logic
        if self.purge_button.update(hand_data.index_tip):
            self.db.clear_all_history()
            self.dashboard_surf = None # Force chart redraw
            self.dashboard_loading = True
            
            def load_async():
                try:
                    surf = self.db.render_matplotlib_dashboard(self.patient_name)
                    self.dashboard_surf = surf
                except Exception as e:
                    print(f"Failed loading async chart on purge: {e}")
                finally:
                    self.dashboard_loading = False

            threading.Thread(target=load_async, daemon=True).start()
            self.purge_button.hover_start = None
            self.sounds.play('pop')

        # Back button logic
        if self.history_back_button.update(hand_data.index_tip):
            self.state = GameState.MAIN_MENU
            self.sounds.play('pop')

        # Use home_icon fist detection to return
        if hand_data.is_fist:
            if not hasattr(self, '_hist_fist_t'):
                self._hist_fist_t = time.time()
            elif time.time() - self._hist_fist_t > 1.5:
                self.state = GameState.MAIN_MENU
                del self._hist_fist_t
        else:
            if hasattr(self, '_hist_fist_t'):
                del self._hist_fist_t

    def _draw_history(self):
        """Full-screen session history + ROM trend line chart"""
        self.screen.fill((8, 14, 30))
        cx = WINDOW_WIDTH // 2

        # Header
        pygame.draw.rect(self.screen, (10, 20, 50),
                         pygame.Rect(0, 0, WINDOW_WIDTH, 70))
        p_name = self.patient_name.upper() if self.patient_name else "UNKNOWN"
        h1 = self.font_large.render(f"SESSION HISTORY: {p_name}", True, (0, 200, 255))
        self.screen.blit(h1, h1.get_rect(center=(cx, 35)))

        sessions = self.db.get_session_history(15, patient_id=self.patient_name)
        rom_data  = self.db.get_rom_trend(10, patient_id=self.patient_name)

        # ── Left: Session Table ──────────────────────────────────────
        table_x = 20
        table_y = 80
        col_w   = [40, 160, 40, 70, 70, 70, 60, 50]  # id,date,lvl,score,acc,rom,dur,pain
        headers = ["ID", "Date/Time", "Lv", "Score", "Acc%", "ROM°", "Sec", "Pain"]
        header_col = (0, 255, 180)

        # Table background (CRT Terminal Style)
        pygame.draw.rect(self.screen, (5, 10, 20), pygame.Rect(table_x - 10, table_y - 10, sum(col_w) + 20, WINDOW_HEIGHT - 120), border_radius=5)
        pygame.draw.rect(self.screen, (0, 120, 100), pygame.Rect(table_x - 10, table_y - 10, sum(col_w) + 20, WINDOW_HEIGHT - 120), 1, border_radius=5)

        header_col = (0, 255, 180)
        x = table_x
        for h, w in zip(headers, col_w):
            hs = self.font_hint.render(h, True, header_col)
            self.screen.blit(hs, (x, table_y))
            x += w
        pygame.draw.line(self.screen, (0, 100, 80),
                         (table_x, table_y + 18),
                         (table_x + sum(col_w), table_y + 18), 1)

        pain_colors = [(50,220,120),(80,220,100),(130,220,80),(180,220,60),
                       (220,220,40),(255,200,0),(255,160,0),(255,100,0),
                       (240,60,60),(220,30,30),(200,0,0)]

        for row_i, row in enumerate(sessions):
            try:
                sid, dt, level, score, acc, rom, dur, pain = row
                def safe_float(v, default=0.0):
                    try: return float(v)
                    except (ValueError, TypeError): return default

                acc_val = safe_float(acc)
                rom_val = safe_float(rom)
                dur_val = safe_float(dur)
                pain_val = int(safe_float(pain))

                dt = dt or "Unknown"
                score = score or 0
                level = level or 1
                
                ry = table_y + 25 + row_i * 24
                if ry > WINDOW_HEIGHT - 60:
                    break
                # Alternating bg
                if row_i % 2 == 0:
                    pygame.draw.rect(self.screen, (15, 22, 40),
                                     pygame.Rect(table_x, ry - 2, sum(col_w), 22))
                acc_c  = (50,220,120) if acc_val >= 75 else (255,180,0) if acc_val >= 50 else (220,60,60)
                pain_c = pain_colors[min(pain_val, 10)]
                vals   = [str(sid), str(dt)[:16], str(level),
                          str(score), f"{acc_val:.0f}%", f"{rom_val:.0f}°",
                          f"{dur_val:.0f}s", str(pain_val)]
                cols_v = [(200,200,200),(180,180,180),(180,200,255),
                          (255,255,255), acc_c, (100,200,255),
                          (160,160,160), pain_c]
                x = table_x
                for v, vc, w in zip(vals, cols_v, col_w):
                    vs = self.font_hint.render(v, True, vc)
                    self.screen.blit(vs, (x, ry))
                    x += w
            except Exception as e:
                print(f"Error drawing history row {row}: {e}")

        # ── Right: Matplotlib Therapist Dashboard ──────────────────────
        chart_x = 600
        chart_y = 90
        chart_w = WINDOW_WIDTH - chart_x - 20
        chart_h = WINDOW_HEIGHT - 160

        pygame.draw.rect(self.screen, (12, 20, 40),
                         pygame.Rect(chart_x, chart_y, chart_w, chart_h), border_radius=8)
        pygame.draw.rect(self.screen, (0, 100, 160),
                         pygame.Rect(chart_x, chart_y, chart_w, chart_h), 2, border_radius=8)

        if getattr(self, "dashboard_surf", None):
            scaled_dash = pygame.transform.scale(self.dashboard_surf, (chart_w - 4, chart_h - 4))
            self.screen.blit(scaled_dash, (chart_x + 2, chart_y + 2))
        elif getattr(self, "dashboard_loading", False):
            # Pulsing loader text for high contrast and dynamic feedback (clamping values to 0-255)
            pulse = int(127 + 127 * math.sin(time.time() * 5))
            c_r = max(0, min(pulse, 255))
            c_g = max(0, min(pulse + 50, 255))
            c_b = max(0, min(pulse + 128, 255))
            no_data = self.font_medium.render("Generating Dashboard... Please wait.", True, (c_r, c_g, c_b))
            self.screen.blit(no_data, no_data.get_rect(
                center=(chart_x + chart_w//2, chart_y + chart_h//2)))
        else:
            no_data = self.font_medium.render("Awaiting Patient Data for Clinical Dashboard", True, (100, 120, 150))
            self.screen.blit(no_data, no_data.get_rect(
                center=(chart_x + chart_w//2, chart_y + chart_h//2)))
        
        # Display ML Progress Prediction below chart
        pred_pct = self.db.predict_recovery_progress(self.patient_name)
        if pred_pct < 0:
            pred_text = self.font_hud.render("Collecting more data...", True, (255, 200, 100))
        else:
            pred_text = self.font_hud.render(f"7-Day ML Prediction: {pred_pct:.1f}% Recovery", True, (255, 200, 100))
        self.screen.blit(pred_text, (chart_x + 20, chart_y + chart_h + 10))

        # CRT Static / Scanlines for History
        scan_y = int((time.time() * 150) % WINDOW_HEIGHT)
        pygame.draw.line(self.screen, (0, 255, 150, 30), (0, scan_y), (WINDOW_WIDTH, scan_y), 1)

        # Back instruction
        inst = self.font_small.render("Make a FIST for 1.5s to return to Main Menu", True, (120, 160, 200))
        self.screen.blit(inst, inst.get_rect(center=(cx, WINDOW_HEIGHT - 22)))

        # Cursor
        hand_data = self.hand_engine.get_hand_data()
        self.purge_button.draw(self.screen, self.font_tiny)
        self.history_back_button.draw(self.screen, self.font_tiny)
        self._draw_cursor(hand_data)

    def _init_calibration(self):
        self.calibration_stage = "START"
        self.calibration_timer = 0
        self.calibration_countdown = 3.0
        self.calibration_stage_start = time.time()
        self.cal_finger_extensions = []
        self.cal_knuckle_angles = []
        self.cal_fist_distances = []
        VOICE.speak("Welcome to the Hand Diagnostics and Range of Motion Calibration Test.")

    def _update_calibration(self, hand_data: HandData):
        """Update loop for ROM Diagnostics & Calibration"""
        if self.calibration_stage == "START":
            if self.cal_start_button.update(hand_data.index_tip):
                self.calibration_stage = "OPEN_HAND"
                self.calibration_stage_start = time.time()
                self.cal_finger_extensions.clear()
                self.cal_knuckle_angles.clear()
                VOICE.speak("Stage 1: Open your hand as wide as possible and hold.")
                self.cal_start_button.hover_start = None
                
        elif self.calibration_stage == "OPEN_HAND":
            elapsed = time.time() - self.calibration_stage_start
            if hand_data.finger_extension > 0:
                self.cal_finger_extensions.append(hand_data.finger_extension)
            if hand_data.knuckle_angles and len(hand_data.knuckle_angles) > 0:
                self.cal_knuckle_angles.append(hand_data.knuckle_angles[0])
                
            if elapsed >= 3.5:
                if self.cal_finger_extensions:
                    self.temp_max_extension = np.percentile(self.cal_finger_extensions, 90)
                else:
                    self.temp_max_extension = 170.0
                    
                if self.cal_knuckle_angles:
                    self.temp_max_angle = np.percentile(self.cal_knuckle_angles, 90)
                else:
                    self.temp_max_angle = 90.0
                    
                self.calibration_stage = "MAKE_FIST"
                self.calibration_stage_start = time.time()
                self.cal_fist_distances.clear()
                self.cal_knuckle_angles.clear()
                VOICE.speak("Stage 2: Now, close your hand into a tight fist.")
                
        elif self.calibration_stage == "MAKE_FIST":
            elapsed = time.time() - self.calibration_stage_start
            
            # Read landmarks from hand engine for precise fist closeness
            with self.hand_engine.lock:
                frame_landmarks = self.hand_engine.hand_data.landmarks
            if frame_landmarks and len(frame_landmarks) > 0 and frame_landmarks[0] is not None:
                landmarks = frame_landmarks[0]
                wrist = landmarks.landmark[0]
                middle_mcp = landmarks.landmark[9]
                index_tip = landmarks.landmark[8]
                middle_tip = landmarks.landmark[12]
                ring_tip = landmarks.landmark[16]
                pinky_tip = landmarks.landmark[20]
                avg_finger_y = (index_tip.y + middle_tip.y + ring_tip.y + pinky_tip.y) / 4
                palm_y = (wrist.y + middle_mcp.y) / 2
                fist_dist = abs(avg_finger_y - palm_y)
                self.cal_fist_distances.append(fist_dist)
                
            if hand_data.knuckle_angles and len(hand_data.knuckle_angles) > 0:
                self.cal_knuckle_angles.append(hand_data.knuckle_angles[0])
                
            if elapsed >= 3.5:
                if self.cal_fist_distances:
                    raw_val = np.percentile(self.cal_fist_distances, 15)
                    self.calibrated_fist_val = float(np.clip(raw_val, 0.08, 0.18))
                else:
                    self.calibrated_fist_val = 0.12
                    
                if self.cal_knuckle_angles:
                    self.calibrated_min_angle = float(np.percentile(self.cal_knuckle_angles, 15))
                else:
                    self.calibrated_min_angle = 15.0
                    
                self.calibrated_max_extension = float(max(120.0, self.temp_max_extension))
                self.calibrated_max_angle = float(max(100.0, self.temp_max_angle))
                
                # Apply new thresholds to HandEngine
                self.hand_engine.fist_threshold = self.calibrated_fist_val
                self.hand_engine.calibration_active = True
                self.hand_engine.calibrated_max_extension = self.calibrated_max_extension
                self.calibration_active = True
                
                # Persist calibrated thresholds to DB Patient profile
                if self.patient_name:
                    self.db.save_patient(
                        name=self.patient_name,
                        age=int(self.patient_age) if self.patient_age.isdigit() else 30,
                        age_group=self.age_group.value if self.age_group else "adult",
                        cal_fist_val=self.calibrated_fist_val,
                        cal_max_ext=self.calibrated_max_extension,
                        cal_min_ang=self.calibrated_min_angle,
                        cal_max_ang=self.calibrated_max_angle,
                        cal_active=1
                    )
                    # Refresh profile directory buttons to include any updates
                    self._refresh_patient_profiles()
                    print(f"[SUCCESS] Saved calibration for {self.patient_name} in DB.")
                
                self.calibration_stage = "COMPLETE"
                VOICE.speak("Diagnostics complete. Game difficulty dynamically scaled to match your mobility.")
                
        elif self.calibration_stage == "COMPLETE":
            if self.cal_finish_button.update(hand_data.index_tip):
                self.state = GameState.MAIN_MENU
                self.cal_finish_button.hover_start = None
                self.sounds.play('pop')

    def _draw_calibration(self):
        """Draw ROM Calibration and Diagnostics interface"""
        self.screen.fill((8, 14, 30))
        cx = GAME_AREA_WIDTH // 2
        
        # Draw tech background grids
        self._draw_cyber_grid()
        
        title_surf = self.font_medium.render("HAND DIAGNOSTICS & CALIBRATION", True, (0, 200, 255))
        self.screen.blit(title_surf, title_surf.get_rect(midleft=(40, 45)))
        pygame.draw.line(self.screen, (0, 150, 200), (0, 80), (GAME_AREA_WIDTH, 80), 2)
        
        prev_x, prev_y = GAME_AREA_WIDTH - 360, 100
        prev_w, prev_h = 340, 260
        self._draw_camera_preview(prev_x, prev_y, prev_w, prev_h, label="DIAGNOSTIC SCANNER")
        
        panel_rect = pygame.Rect(20, 100, GAME_AREA_WIDTH - 400, WINDOW_HEIGHT - 130)
        pygame.draw.rect(self.screen, (10, 20, 45), panel_rect, border_radius=12)
        pygame.draw.rect(self.screen, (0, 120, 200), panel_rect, 2, border_radius=12)
        
        hand_data = self.hand_engine.get_hand_data()
        
        if self.calibration_stage == "START":
            y = 130
            text_1 = self.font_head.render("DAILY MOBILITY BASELINE TEST", True, COLOR_SUCCESS)
            self.screen.blit(text_1, (50, y))
            y += 45
            
            desc_lines = [
                "This assessment calibrates the computer vision engine",
                "to match your hand's exact flexibility.",
                "",
                "By measuring your individual range of motion, the system:",
                " 1. Dynamically scales game reach zones.",
                " 2. Calibrates gesture detection sensitivity.",
                " 3. Adapts speed to minimize fatigue.",
                "",
                "Recommended at the start of each daily session."
            ]
            for line in desc_lines:
                ts = self.font_hint.render(line, True, (180, 200, 220))
                self.screen.blit(ts, (50, y))
                y += 24
                
            self.cal_start_button.draw(self.screen, self.font_small, text="BEGIN ASSESSMENT", base_col=(25,45,35), hov_col=(40,90,60))
            
        elif self.calibration_stage in ["OPEN_HAND", "MAKE_FIST"]:
            elapsed = time.time() - self.calibration_stage_start
            countdown = max(0.0, 3.0 - elapsed)
            
            y = 130
            title_text = "STAGE 1: EXTENSION ASSESSMENT" if self.calibration_stage == "OPEN_HAND" else "STAGE 2: FLEXION ASSESSMENT"
            instruct_text = "Spread your fingers and open hand fully!" if self.calibration_stage == "OPEN_HAND" else "Make a tight fist!"
            icon_char = "OPEN HAND" if self.calibration_stage == "OPEN_HAND" else "CLOSED FIST"
            
            tx = self.font_head.render(title_text, True, COLOR_PRIMARY)
            self.screen.blit(tx, (50, y))
            y += 50
            
            ix = self.font_medium.render(icon_char, True, (255, 255, 255))
            self.screen.blit(ix, (50, y))
            
            inst_surf = self.font_small.render(instruct_text, True, (200, 220, 240))
            self.screen.blit(inst_surf, (50, y + 45))
            y += 85
            
            if hand_data.knuckle_angles and len(hand_data.knuckle_angles) > 0:
                angle_val = hand_data.knuckle_angles[0]
            else:
                angle_val = 0.0
                
            val_str = f"Extension Reach: {hand_data.finger_extension:.0f}px" if self.calibration_stage == "OPEN_HAND" else f"Knuckle Flexion: {angle_val:.1f}°"
            vx = self.font_hud.render(val_str, True, COLOR_WARNING)
            self.screen.blit(vx, (50, y))
            y += 40
            
            cx_gauge = panel_rect.x + panel_rect.width // 2
            cy_gauge = y + 80
            pygame.draw.circle(self.screen, (25, 35, 60), (cx_gauge, cy_gauge), 70, 6)
            
            time_prog = min(elapsed / 3.0, 1.0)
            start_a = math.radians(-90)
            end_a = math.radians(-90 + 360 * time_prog)
            arc_s = pygame.Surface((140, 140), pygame.SRCALPHA)
            pygame.draw.arc(arc_s, COLOR_SUCCESS, (0, 0, 140, 140), start_a, end_a, 8)
            self.screen.blit(arc_s, (cx_gauge - 70, cy_gauge - 70))
            
            cd_surf = self.font_large.render(f"{int(countdown)+1}", True, (255, 255, 255))
            self.screen.blit(cd_surf, cd_surf.get_rect(center=(cx_gauge, cy_gauge)))
            
            sub_t = self.font_tiny.render("RECORDING LIVE LANDMARKS...", True, (120, 150, 180))
            self.screen.blit(sub_t, sub_t.get_rect(center=(cx_gauge, cy_gauge + 95)))
            
        elif self.calibration_stage == "COMPLETE":
            y = 130
            rx = self.font_head.render("Clinical Mobility Summary", True, COLOR_SUCCESS)
            self.screen.blit(rx, (50, y))
            y += 45
            
            rom_val = self.calibrated_max_angle - self.calibrated_min_angle
            
            if rom_val >= 75:
                grade = "Excellent 🌟"
                grade_col = COLOR_SUCCESS
            elif rom_val >= 55:
                grade = "Good 👍"
                grade_col = COLOR_PRIMARY
            elif rom_val >= 35:
                grade = "Fair 🧘"
                grade_col = COLOR_WARNING
            else:
                grade = "Limited 🩹"
                grade_col = (255, 100, 100)
                
            metrics = [
                ("Active Joint ROM:", f"{rom_val:.1f}°", (255, 255, 255)),
                ("Flexibility Grade:", grade, grade_col),
                ("Max Extension Reach:", f"{self.calibrated_max_extension:.0f} pixels", (200, 220, 240)),
                ("Calibrated Fist Value:", f"{self.calibrated_fist_val:.3f}", (200, 220, 240)),
                ("Dynamic Difficulty Scaling:", f"{int(min(1.0, self.calibrated_max_extension/170.0)*100)}% ACTIVE", COLOR_SUCCESS)
            ]
            
            for label, value, val_col in metrics:
                lx = self.font_hud.render(label, True, (160, 180, 200))
                self.screen.blit(lx, (50, y))
                vx = self.font_hud.render(value, True, val_col)
                self.screen.blit(vx, (310, y))
                y += 34
                
            y += 20
            rec_box = pygame.Rect(40, y, panel_rect.width - 80, 80)
            pygame.draw.rect(self.screen, (20, 35, 65), rec_box, border_radius=8)
            pygame.draw.rect(self.screen, COLOR_SUCCESS, rec_box, 1, border_radius=8)
            
            rec_text = "System adapted to limited reach. Perfect for recovery!" if rom_val < 55 else "Standard reach active. Excellent joint flexibility!"
            rt = self.font_hint.render(rec_text, True, (255, 220, 150))
            self.screen.blit(rt, rt.get_rect(center=rec_box.center))
            
            self.cal_finish_button.draw(self.screen, self.font_small, text="FINISH ASSESSMENT", base_col=(25,45,35), hov_col=(40,90,60))
            
        self._draw_cursor(hand_data)

    def _draw_level_complete(self):
        """Full-screen 2.5-second celebration screen between gameplay and report"""
        t   = time.time()
        cx  = GAME_AREA_WIDTH // 2
        cy  = WINDOW_HEIGHT // 2
        elapsed = t - self._level_complete_time

        # Dark overlay
        self.screen.fill((5, 12, 28))

        # Spinning confetti ring
        n_dots = 24
        ring_r = 180 + int(20 * math.sin(t * 4))
        for i in range(n_dots):
            angle = (2 * math.pi * i / n_dots) + t * 2
            dx = int(cx + ring_r * math.cos(angle))
            dy = int(cy + ring_r * math.sin(angle))
            col = [
                (255, 215, 0), (0, 220, 120), (0, 200, 255),
                (255, 100, 180), (200, 160, 255)
            ][i % 5]
            pygame.draw.circle(self.screen, col, (dx, dy), 8)

        # Inner glow
        glow = int(60 + 30 * abs(math.sin(t * 3)))
        pygame.draw.circle(self.screen, (0, glow, glow // 2), (cx, cy), 130)
        pygame.draw.circle(self.screen, (0, 180, 220), (cx, cy), 130, 3)

        # Level complete text
        lc1 = self.font_large.render("LEVEL COMPLETE!", True, (50, 220, 120))
        self.screen.blit(lc1, lc1.get_rect(center=(cx, cy - 60)))

        # Stars
        acc = (self.accuracy_hits / max(self.accuracy_attempts, 1)) * 100
        stars = 3 if acc >= 80 else (2 if acc >= 55 else 1)
        star_col = [(220,60,60),(255,180,0),(50,220,120)][stars-1]
        star_str = "★" * stars + "☆" * (3 - stars)
        ss = self.font_large.render(star_str, True, star_col)
        self.screen.blit(ss, ss.get_rect(center=(cx, cy)))

        # Score
        sc = self.font_medium.render(f"Score: {self.score}", True, (255, 255, 255))
        self.screen.blit(sc, sc.get_rect(center=(cx, cy + 60)))

        # Countdown
        remaining = max(0, 2.5 - elapsed)
        cd_col = (100, 200, 255) if remaining > 1.0 else (255, 180, 0)
        cd = self.font_small.render(f"Report in {remaining:.1f}s ...", True, cd_col)
        self.screen.blit(cd, cd.get_rect(center=(cx, cy + 110)))

        # Particle burst every 0.3s
        if int(elapsed * 10) % 3 == 0:
            self.particles.emit(
                cx + random.randint(-150, 150),
                cy + random.randint(-100, 100),
                random.choice([(255,215,0),(0,220,120),(0,200,255),(255,100,150)]),
                8
            )
        self.particles.update()
        self.particles.draw(self.screen)

    def _draw_progress_chart(self):
        """Draws a compact 'Last 6 Sessions' progress bar chart in the sidebar area"""
        sessions = self.db.get_recent_sessions(6)
        if not sessions:
            return

        # Panel sits in the right sidebar strip, below camera & hand status (starting at panel_y=352)
        panel_x = GAME_AREA_WIDTH + 4
        panel_y = 352
        panel_w = SIDEBAR_WIDTH - 8
        panel_h = WINDOW_HEIGHT - panel_y - 12

        # Background
        pygame.draw.rect(self.screen, (5, 12, 24),
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h), border_radius=8)
        pygame.draw.rect(self.screen, (0, 180, 220),
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h), 1, border_radius=8)

        # CRT Grid in chart area
        chart_x = panel_x + 14
        chart_y = panel_y + 45
        chart_w = panel_w - 28
        chart_h = 130
        
        pygame.draw.rect(self.screen, (2, 8, 15),
                         pygame.Rect(chart_x, chart_y, chart_w, chart_h), border_radius=4)
        
        for gy in range(chart_y, chart_y + chart_h, 20):
            pygame.draw.line(self.screen, (10, 25, 40), (chart_x, gy), (chart_x + chart_w, gy))
        for gx in range(chart_x, chart_x + chart_w, 25):
            pygame.draw.line(self.screen, (10, 25, 40), (gx, chart_y), (gx, chart_y + chart_h))

        # Header
        hdr = self.font_hud.render("ANALYTICS MONITOR", True, (0, 255, 180))
        self.screen.blit(hdr, hdr.get_rect(center=(panel_x + panel_w // 2, panel_y + 14)))
        sub = self.font_tiny.render("PATIENT PERFORMANCE HISTORY", True, (0, 150, 120))
        self.screen.blit(sub, sub.get_rect(center=(panel_x + panel_w // 2, panel_y + 30)))

        n = len(sessions)
        bar_w = (chart_w - (n - 1) * 6) // n

        for i, (level, acc, angle, score, date) in enumerate(sessions):
            bx = chart_x + i * (bar_w + 6)
            bar_h = int(chart_h * min(acc / 100, 1.0))
            by = chart_y + chart_h - bar_h

            # CRT Phosphorus Green for all bars, highlight latest
            base_green = (0, 200, 100)
            if i == n - 1:
                pygame.draw.rect(self.screen, (0, 255, 150), pygame.Rect(bx, by, bar_w, bar_h), border_radius=2)
                pygame.draw.rect(self.screen, (255, 255, 255), pygame.Rect(bx, by, bar_w, bar_h), 1, border_radius=2)
            else:
                pygame.draw.rect(self.screen, (0, 120, 60), pygame.Rect(bx, by, bar_w, bar_h), border_radius=2)
            
            # Glow effect for bars
            if bar_h > 5:
                pygame.draw.line(self.screen, (100, 255, 200), (bx, by), (bx + bar_w, by), 1)

            # Accuracy label on bar
            if bar_h > 20:
                lbl = self.font_hint.render(f"{acc:.0f}%", True, (255, 255, 255))
                self.screen.blit(lbl, lbl.get_rect(center=(bx + bar_w // 2, by + 10)))

            # Date label below
            dl = self.font_hint.render(date or f"S{i+1}", True, (100, 130, 170))
            self.screen.blit(dl, dl.get_rect(center=(bx + bar_w // 2,
                                                      chart_y + chart_h + 10)))

        # 75% goal line
        goal_y = chart_y + chart_h - int(chart_h * 0.75)
        pygame.draw.line(self.screen, (255, 200, 60),
                         (chart_x, goal_y), (chart_x + chart_w, goal_y), 1)
        gl = self.font_hint.render("75% goal", True, (255, 200, 60))
        self.screen.blit(gl, (chart_x + 2, goal_y - 14))

        # Level trend info below chart
        y2 = chart_y + chart_h + 24
        if len(sessions) >= 2:
            latest_acc  = sessions[-1][1]
            prev_acc    = sessions[-2][1]
            delta       = latest_acc - prev_acc
            trend_str   = f"Trend: {'+' if delta >= 0 else ''}{delta:.1f}% vs last"
            trend_col   = (50, 220, 120) if delta >= 0 else (255, 120, 80)
            ts = self.font_hint.render(trend_str, True, trend_col)
            self.screen.blit(ts, ts.get_rect(center=(panel_x + panel_w // 2, y2)))
            y2 += 16

        # Sessions per level breakdown
        level_counts = {}
        for s in sessions:
            level_counts[s[0]] = level_counts.get(s[0], 0) + 1
        for lv, cnt in sorted(level_counts.items()):
            lcolors = [(100,160,255),(0,220,120),(255,150,80)]
            lc = self.font_hint.render(f"L{lv}: {cnt} session{'s' if cnt>1 else ''}",
                                        True, lcolors[min(lv-1, 2)])
            self.screen.blit(lc, (chart_x, y2))
            y2 += 16

    def _draw_results(self):
        """Draw post-game clinical report screen"""
        if self.session_data:
            self.summary_screen.draw(
                self.screen, self.session_data, self.best_data,
                patient_name=self.patient_name or "Patient"
            )
            
            # PLAY AGAIN, NEXT, MAIN MENU, CLOSE buttons
            self.menu_button.draw(self.screen, self.font_small, text="PLAY AGAIN", base_col=(25,40,25), hov_col=(40,80,40))
            if hasattr(self, 'next_button') and getattr(self, 'current_level', 1) < 8:
                self.next_button.draw(self.screen, self.font_small, text="NEXT GAME", base_col=(25,25,50), hov_col=(40,40,80))
            self.home_button.draw(self.screen, self.font_small, text="MAIN MENU", base_col=(60,30,90), hov_col=(100,50,150))
            self.close_button.draw(self.screen, self.font_small)

    def _draw_cloud_sync(self):
        """Draw fake cloud sync animation"""
        self.screen.fill((10, 15, 25))
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        
        t = time.time()
        elapsed = t - getattr(self, 'sync_start', t)
        progress = min(elapsed / 2.0, 1.0)
        
        # Draw rotating rings
        for i in range(3):
            radius = 100 + i * 30
            angle = t * (2 + i)
            pygame.draw.arc(self.screen, (0, 200, 255), 
                            (cx - radius, cy - radius, radius*2, radius*2),
                            angle, angle + math.pi, 4)
                            
        # Text
        txt = self.font_large.render("Syncing Securely to Medical Database...", True, (255, 255, 255))
        self.screen.blit(txt, txt.get_rect(center=(cx, cy + 180)))
        
        # Progress Bar
        bar_w = 400
        bar_x = cx - bar_w // 2
        pygame.draw.rect(self.screen, (40, 50, 70), (bar_x, cy + 240, bar_w, 10), border_radius=5)
        if progress > 0:
            pygame.draw.rect(self.screen, (50, 255, 150), (bar_x, cy + 240, int(bar_w * progress), 10), border_radius=5)
            
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)

    def _update_therapist_dashboard(self, hand_data):
        global LEVEL_DURATION
        if not hasattr(self, 'admin_back_button'):
            self.admin_back_button = LevelButton(50, 150, 250, 80, "EXIT ADMIN", 0)
            self.admin_purge_button = LevelButton(50, 270, 350, 80, "PURGE ALL PATIENT DATA", 99)
            self.admin_timer_button = LevelButton(50, 390, 350, 80, f"LEVEL DURATION: {LEVEL_DURATION}s", 88)
            
        if self.admin_purge_button.update(hand_data.index_tip):
            try:
                self.db.cursor.execute("DELETE FROM sessions")
                self.db.conn.commit()
                self.sounds.play('level_complete')
            except: pass
            
        if self.admin_timer_button.update(hand_data.index_tip):
            LEVEL_DURATION = 60 if LEVEL_DURATION == 30 else 30
            self.admin_timer_button.text = f"LEVEL DURATION: {LEVEL_DURATION}s"
            self.sounds.play('select')

    def _draw_therapist_dashboard(self):
        self.screen.fill((20, 10, 15)) # Dark red/black to indicate admin mode
        title = self.font_large.render("THERAPIST CONFIGURATION PANEL", True, (255, 100, 100))
        self.screen.blit(title, (50, 50))
        
        self.admin_back_button.draw(self.screen, self.font_medium, base_col=(100, 40, 40), hov_col=(150, 50, 50))
        self.admin_purge_button.draw(self.screen, self.font_medium, base_col=(180, 20, 20), hov_col=(255, 40, 40))
        self.admin_timer_button.draw(self.screen, self.font_medium, base_col=(40, 100, 40), hov_col=(60, 150, 60))
        
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    print("=" * 70)
    print("ZERO-KEYBOARD AI PHYSIOTHERAPY SYSTEM")
    print("=" * 70)
    print("\nFeatures:")
    print("  * Split-screen layout (75% game, 25% medical sidebar)")
    print("  * Total hand control - no keyboard/mouse needed")
    print("  * Hover-to-click with selection rings")
    print("  * Fist-hold to pause/quit (2 seconds)")
    print("  * Threaded camera for 60 FPS performance")
    print("  * Weighted average smoothing")
    print("  * Real-time joint angles and analytics")
    print("\nLevels:")
    print("  1. Flexibility - Pop bubbles in corners")
    print("  2. Strength - Catch falling items with palm")
    print("  3. Fine Motor - Pinch seeds and drop in pot")
    print("\nStarting system...")
    print("=" * 70)
    
    app = PhysioSystem()
    app.run()
    
    print("\n* System closed successfully")

if __name__ == "__main__":
    main()
