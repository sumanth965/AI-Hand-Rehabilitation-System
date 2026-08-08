"""RuntimeMixin implementation for PhysioSystem."""

from .shared import *


class RuntimeMixin:
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
                GameState.LEVEL8_SMART_ASSEMBLY,
                GameState.LEVEL9_PRECISION_PATH,
                GameState.LEVEL10_PRECISION_PATHWAY
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
                                    GameState.LEVEL5_GRIP_RELEASE, GameState.LEVEL6_FINGER_TAPS,
                                    GameState.LEVEL9_PRECISION_PATH, GameState.LEVEL10_PRECISION_PATHWAY]
        
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
        elif self.state == GameState.LEVEL9_PRECISION_PATH:
            if not getattr(self, 'tracking_lost', False):
                self._update_level9(hand_data)
        elif self.state == GameState.LEVEL10_PRECISION_PATHWAY:
            if not getattr(self, 'tracking_lost', False):
                self._update_level10(hand_data)
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
        elif self.state == GameState.LEVEL9_PRECISION_PATH:
            self._draw_level9()
        elif self.state == GameState.LEVEL10_PRECISION_PATHWAY:
            self._draw_level10()
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
                       GameState.THERAPIST_DASHBOARD, GameState.PAIN_AFTER_SESSION]
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
                           GameState.LEVEL6_FINGER_TAPS,
                           GameState.LEVEL7_WRIST_MECHANICS,
                           GameState.LEVEL8_SMART_ASSEMBLY,
                           GameState.LEVEL9_PRECISION_PATH,
                           GameState.LEVEL10_PRECISION_PATHWAY]
        if self.state in gameplay_states:
            hud_y = 15
            hud_h = 60
            hud_w = GAME_AREA_WIDTH - 275
            hud_rect = pygame.Rect(10, hud_y, hud_w, hud_h)

            # Modern flat HUD background matching HomeIcon
            hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
            hud_surf.fill((20, 22, 35, 230))
            self.screen.blit(hud_surf, (10, hud_y))
            pygame.draw.rect(self.screen, (0, 180, 220), hud_rect, 2, border_radius=15)

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
            self.screen.blit(sc, (30, hud_y + (hud_h - sc.get_height()) // 2))

            # Accuracy
            acc = (self.accuracy_hits / self.accuracy_attempts * 100) \
                  if self.accuracy_attempts > 0 else 0.0
            acc_color = (50, 220, 120) if acc >= 70 else \
                        (255, 180, 0)  if acc >= 40 else (220, 80, 80)
            acc_str = f"ACC: {acc:.0f}%"
            ac = hud_font.render(acc_str, True, acc_color)
            self.screen.blit(ac, (200, hud_y + (hud_h - ac.get_height()) // 2))

            # Combo
            if self.combo > 1:
                combo_color = (255, 215, 0) if self.combo >= 5 else (255, 180, 60)
                co = hud_font.render(f"x{self.combo} COMBO", True, combo_color)
                self.screen.blit(co, (350, hud_y + (hud_h - co.get_height()) // 2))

            # Multiplier badge
            if self.score_multiplier > 1.0:
                mx = hud_font.render(f"{self.score_multiplier:.0f}x BOOST", True, (255, 100, 255))
                self.screen.blit(mx, (530, hud_y + (hud_h - mx.get_height()) // 2))
        
        # Draw feedback text (center screen) — use cached font to avoid per-frame allocation
        if self.feedback_text and self.feedback_timer > 0:
            feedback_surf = self.font_large.render(self.feedback_text, True, COLOR_SUCCESS)
            feedback_rect = feedback_surf.get_rect(center=(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 3))
            shadow = self.font_large.render(self.feedback_text, True, (0, 0, 0))
            self.screen.blit(shadow, shadow.get_rect(center=(GAME_AREA_WIDTH // 2 + 3, WINDOW_HEIGHT // 3 + 3)))
            self.screen.blit(feedback_surf, feedback_rect)
            
        # Draw correctness warning (floating toast below timer bar)
        if getattr(self, 'correctness_warning', "") and getattr(self, 'state', None) in gameplay_states:
            c_color = (255, 100, 100) if "Bend" in self.correctness_warning else (100, 255, 100)
            warning_surf = self.font_hud.render(self.correctness_warning, True, c_color)
            
            toast_w = warning_surf.get_width() + 40
            toast_h = warning_surf.get_height() + 16
            toast_x = (GAME_AREA_WIDTH - toast_w) // 2
            toast_y = 165
            
            toast_bg = pygame.Surface((toast_w, toast_h), pygame.SRCALPHA)
            toast_bg.fill((20, 22, 35, 230))
            self.screen.blit(toast_bg, (toast_x, toast_y))
            pygame.draw.rect(self.screen, c_color, (toast_x, toast_y, toast_w, toast_h), 2, border_radius=12)
            
            self.screen.blit(warning_surf, warning_surf.get_rect(center=(GAME_AREA_WIDTH // 2, toast_y + toast_h // 2)))
        
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
    
    
    

