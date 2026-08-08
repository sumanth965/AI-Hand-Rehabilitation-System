"""SetupMixin implementation for PhysioSystem."""

from .shared import *


class SetupMixin:
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
        h = 75
        self.level_buttons = [
            LevelButton(col1_x, 150, bw, h, "LEVEL 1", 1, ring_radius=30),
            LevelButton(col2_x, 150, bw, h, "LEVEL 2", 2, ring_radius=30),
            LevelButton(col1_x, 235, bw, h, "LEVEL 3", 3, ring_radius=30),
            LevelButton(col2_x, 235, bw, h, "LEVEL 4", 4, ring_radius=30),
            LevelButton(col1_x, 320, bw, h, "LEVEL 5", 5, ring_radius=30),
            LevelButton(col2_x, 320, bw, h, "LEVEL 6", 6, ring_radius=30),
            LevelButton(col1_x, 405, bw, h, "LEVEL 7", 7, ring_radius=30),
            LevelButton(col2_x, 405, bw, h, "LEVEL 8", 8, ring_radius=30),
            LevelButton(col1_x, 490, bw, h, "LEVEL 9", 9, ring_radius=30),
            LevelButton(col2_x, 490, bw, h, "LEVEL 10", 10, ring_radius=30)
        ]
        # Bottom utility buttons — evenly spaced with smaller rings
        btn_w = 210
        btn_gap = 12
        total_w = btn_w * 3 + btn_gap * 2
        start_x = cx - total_w // 2
        self.history_button = LevelButton(start_x, 620, btn_w, 50, "RECOVERY HISTORY", "", ring_radius=20)
        self.calibrate_button = LevelButton(start_x + btn_w + btn_gap, 620, btn_w, 50, "ROM DIAGNOSTICS", "", ring_radius=20)
        self.exit_button = LevelButton(start_x + (btn_w + btn_gap) * 2, 620, btn_w, 50, "EXIT SYSTEM", "", ring_radius=20)
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
        
        # Level 9 Precision Path state
        self.precision_dots = []
        self.precision_current_dot = 0
        self.precision_path_points = []
        
        # Level 10 Precision Pathway state
        self.pathway_config = None
        self.pathway_boundary_violations = 0
        self.pathway_total_deviation = 0.0
        self.pathway_samples = 0
        self.pathway_started = False
        
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
        
        # Repositioned buttons to prevent footer overlap
        btn_y = 495
        bw, bh = 170, 44
        cx = GAME_AREA_WIDTH // 2
        
        self.menu_button  = CloseButton(cx - 360, btn_y, bw, bh)
        self.next_button  = CloseButton(cx - 180, btn_y, bw, bh)
        self.home_button  = CloseButton(cx + 0,   btn_y, bw, bh)
        self.close_button = CloseButton(cx + 180, btn_y, bw, bh)
        
        # Calibration buttons
        self.cal_start_button = CloseButton(GAME_AREA_WIDTH // 2 - 130, 460, 260, 60)
        self.cal_start_button.duration = 1.5
        self.cal_finish_button = CloseButton(GAME_AREA_WIDTH // 2 - 130, 540, 260, 60)
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
        

