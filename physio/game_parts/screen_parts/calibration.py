"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class CalibrationScreenMixin:
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
        
        title_surf = self.font_large.render("HAND DIAGNOSTICS & CALIBRATION", True, (0, 200, 255))
        self.screen.blit(title_surf, title_surf.get_rect(center=(cx, 45)))
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

