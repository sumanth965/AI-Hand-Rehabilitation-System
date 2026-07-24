"""ScreenMixin implementation for PhysioSystem."""

from .shared import *


class ScreenMixin:
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
    
    # The helpers below are presentation-only; they deliberately do not touch
    # registration state, event handling, hover timing, or camera integration.
    def _draw_glass_card(self, rect, fill=(13, 22, 34, 235), radius=18):
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, fill, surface.get_rect(), border_radius=radius)
        pygame.draw.rect(surface, (0, 229, 255, 65), surface.get_rect(), 1, border_radius=radius)
        self.screen.blit(surface, rect.topleft)

    def _draw_portal_input(self, rect, label, icon, value, placeholder, active, now):
        label_color = (0, 229, 255) if active else (143, 167, 194)
        self.screen.blit(self.font_tiny.render(label, True, label_color), (rect.x, rect.y - 20))
        if active:
            halo = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
            pygame.draw.rect(halo, (0, 229, 255, 32), halo.get_rect(), 3, border_radius=12)
            self.screen.blit(halo, (rect.x - 4, rect.y - 4))
        pygame.draw.rect(self.screen, (8, 17, 28), rect, border_radius=9)
        pygame.draw.rect(self.screen, (0, 229, 255) if active else (48, 83, 112), rect, 2 if active else 1, border_radius=9)
        self.screen.blit(self.font_hint.render(icon, True, (0, 229, 255)), (rect.x + 14, rect.y + 15))
        cursor = "|" if active and int(now * 2) % 2 == 0 else ""
        text = f"{value}{cursor}" if value else placeholder
        color = (244, 248, 252) if value else (143, 167, 194)
        self.screen.blit(self.font_hint.render(text, True, color), (rect.x + 45, rect.y + 15))

    def _draw_patient_registration(self):
        """Responsive 2026 clinical portal; functionality is unchanged."""
        now = time.time()
        scr = self.screen
        w, h = scr.get_size()
        cx = w // 2
        margin = max(24, int(w * 0.028))
        header_h = max(76, int(h * 0.11))
        feature_h = max(52, int(h * 0.075))
        feature_y = h - feature_h - margin // 2
        top, bottom = header_h + 18, feature_y - 18

        # Subtle dark healthcare gradient and grid.
        for y in range(0, h, 4):
            blend = y / max(h, 1)
            pygame.draw.rect(scr, (6 + int(5 * blend), 11 + int(9 * blend), 20 + int(16 * blend)), (0, y, w, 4))
        for x in range(0, w, 48):
            pygame.draw.line(scr, (14, 35, 51), (x, header_h), (x, feature_y), 1)
        for y in range(header_h, feature_y, 48):
            pygame.draw.line(scr, (14, 35, 51), (0, y), (w, y), 1)

        title = self.font_large.render("CLINICAL REGISTRATION PORTAL", True, (244, 248, 252))
        scr.blit(title, title.get_rect(center=(cx, header_h // 2 - 4)))
        pygame.draw.line(scr, (0, 229, 255), (cx - 145, header_h - 13), (cx + 145, header_h - 13), 2)

        gap = max(18, int(w * .018))
        left_w = int((w - 2 * margin - gap) * .56)
        left = pygame.Rect(margin, top, left_w, bottom - top)
        right = pygame.Rect(left.right + gap, top, w - margin - left.right - gap, bottom - top)
        self._draw_glass_card(left)
        self._draw_glass_card(right)

        # Registration card.
        scr.blit(self.font_head.render("Registration Portal", True, (244, 248, 252)), (left.x + 28, left.y + 22))
        scr.blit(self.font_tiny.render("PATIENT ACCESS & THERAPY INTAKE", True, (143, 167, 194)), (left.x + 29, left.y + 51))
        field_x, field_w = left.x + 30, left.width - 60
        field_h = max(46, min(54, int(h * .07)))
        id_y = left.y + 84
        self._draw_portal_input(pygame.Rect(field_x, id_y, field_w, field_h), "CLINICAL ID LOGIN", "◉", self.patient_id_str, "Enter Clinical ID...", self.input_active == "id", now)
        divider_y = id_y + field_h + 27
        pygame.draw.line(scr, (48, 83, 112), (field_x, divider_y), (cx - 22, divider_y), 1)
        pygame.draw.line(scr, (48, 83, 112), (cx + 22, divider_y), (left.right - 30, divider_y), 1)
        scr.blit(self.font_tiny.render("OR", True, (143, 167, 194)), self.font_tiny.render("OR", True, (143, 167, 194)).get_rect(center=(cx, divider_y)))

        name_y = divider_y + 38
        self._draw_portal_input(pygame.Rect(field_x, name_y, field_w, field_h), "GUEST REGISTRATION", "◉", self.patient_name, "Enter Patient Name", self.input_active == "name", now)
        age_y, age_w = name_y + field_h + 30, int(field_w * .40)
        self._draw_portal_input(pygame.Rect(field_x, age_y, age_w, field_h), "PATIENT AGE", "□", self.patient_age, "00", self.input_active == "age", now)
        if self.patient_age.isdigit():
            age = int(self.patient_age)
            badge, color = ("Adult Rehabilitation", (24, 224, 143))
            if age <= 12: badge, color = ("Pediatric Mode", (255, 146, 187))
            elif age > 60: badge, color = ("Geriatric Care", (255, 176, 0))
            badge_surf = self.font_tiny.render(f"✦  {badge}", True, color)
            badge_rect = badge_surf.get_rect(midleft=(field_x + age_w + 18, age_y + field_h // 2))
            pygame.draw.rect(scr, (13, 31, 44), badge_rect.inflate(20, 12), border_radius=13)
            scr.blit(badge_surf, badge_rect)

        protocol = pygame.Rect(field_x, age_y + field_h + 25, field_w, 76)
        self._draw_glass_card(protocol, (10, 26, 39, 225), 12)
        scr.blit(self.font_tiny.render("▣  DIAGNOSTIC PROTOCOL", True, (0, 229, 255)), (protocol.x + 14, protocol.y + 10))
        for i, text in enumerate(("Stand 1–2 meters from camera", "Ensure proper room lighting", "Complete registration to unlock therapy")):
            scr.blit(self.font_tiny.render(f"✓  {text}", True, (183, 205, 224)), (protocol.x + 15, protocol.y + 29 + i * 16))

        shortcuts_y = protocol.bottom + 11
        scr.blit(self.font_tiny.render("⌨  TAB", True, (143, 167, 194)), (field_x, shortcuts_y))
        scr.blit(self.font_tiny.render("Switch Field", True, (143, 167, 194)), (field_x + 58, shortcuts_y))
        scr.blit(self.font_tiny.render("⌨  ENTER", True, (143, 167, 194)), (field_x + field_w // 2, shortcuts_y))
        scr.blit(self.font_tiny.render("Launch Therapy", True, (143, 167, 194)), (field_x + field_w // 2 + 74, shortcuts_y))
        button_rect = pygame.Rect(field_x, shortcuts_y + 26, field_w, field_h)
        self.quick_start_button.rect = button_rect
        ready = bool(self.patient_name and self.patient_age)
        base, hover, border = ((16, 128, 84), (24, 192, 120), (24, 224, 143)) if ready else ((12, 86, 125), (0, 145, 190), (0, 229, 255))
        self.quick_start_button.draw(scr, self.font_small, "▶  Start Rehabilitation" if ready else "▶  Quick Start", base_col=base, hov_col=hover, border_col=border)

        # Live sensor feed.
        scr.blit(self.font_head.render("Live Sensor Feed", True, (244, 248, 252)), (right.x + 24, right.y + 22))
        scr.blit(self.font_tiny.render("HIGH-RESOLUTION NEURAL SENSOR", True, (143, 167, 194)), (right.x + 25, right.y + 51))
        camera = pygame.Rect(right.x + 24, right.y + 78, right.width - 48, min(int((right.width - 48) * .56), int(right.height * .52)))
        self._draw_camera_preview(camera.x, camera.y, camera.width, camera.height, "LIVE CAMERA PREVIEW")
        hand_data = self.hand_engine.get_hand_data()
        detected = hand_data.hand_label != "Unknown"
        status, status_col = ("Hand detected — calibration ready", (24, 224, 143)) if detected else ("Awaiting hand calibration...", (255, 176, 0))
        telemetry = pygame.Rect(right.x + 24, camera.bottom + 18, right.width - 48, right.bottom - camera.bottom - 42)
        self._draw_glass_card(telemetry, (10, 26, 39, 225), 12)
        scr.blit(self.font_tiny.render("✦  HIGH RESOLUTION NEURAL SENSOR", True, (244, 248, 252)), (telemetry.x + 14, telemetry.y + 11))
        scr.blit(self.font_tiny.render(status, True, status_col), (telemetry.x + 14, telemetry.y + 33))
        bar = pygame.Rect(telemetry.x + 14, telemetry.y + 56, telemetry.width - 28, 7)
        pygame.draw.rect(scr, (30, 55, 75), bar, border_radius=4)
        progress = .78 if detected else .28 + .12 * (0.5 + .5 * math.sin(now * 1.5))
        pygame.draw.rect(scr, status_col, (bar.x, bar.y, int(bar.width * progress), bar.height), border_radius=4)
        scr.blit(self.font_tiny.render("● Secure Connection     ◌ Real-time Tracking     ▣ Privacy Mode Enabled", True, (24, 224, 143)), (telemetry.x + 14, telemetry.y + 75))

        features = (("▣", "Clinical Grade", "Secure & Reliable"), ("AI", "AI Powered", "Computer Vision Tracking"), ("☝", "Zero Keyboard", "Touchless Interaction"), ("▣", "Privacy First", "Encrypted Patient Data"))
        feature_gap = 12
        feature_w = (w - margin * 2 - feature_gap * 3) // 4
        for i, (icon, title_text, subtitle) in enumerate(features):
            rect = pygame.Rect(margin + i * (feature_w + feature_gap), feature_y, feature_w, feature_h)
            self._draw_glass_card(rect, (12, 26, 40, 225), 12)
            scr.blit(self.font_hint.render(icon, True, (0, 229, 255)), (rect.x + 13, rect.y + 11))
            scr.blit(self.font_tiny.render(title_text, True, (244, 248, 252)), (rect.x + 45, rect.y + 9))
            scr.blit(self.font_tiny.render(subtitle, True, (143, 167, 194)), (rect.x + 45, rect.y + 29))

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
        if not hasattr(self, 'admin_back_button'):
            self.admin_back_button = LevelButton(50, 150, 250, 80, "EXIT ADMIN", 0)
            self.admin_purge_button = LevelButton(50, 270, 350, 80, "PURGE ALL PATIENT DATA", 99)
            self.admin_timer_button = LevelButton(50, 390, 350, 80, f"LEVEL DURATION: {self.session_time_limit}s", 88)
            
        if self.admin_purge_button.update(hand_data.index_tip):
            try:
                self.db.cursor.execute("DELETE FROM sessions")
                self.db.conn.commit()
                self.sounds.play('level_complete')
            except: pass
            
        if self.admin_timer_button.update(hand_data.index_tip):
            self.session_time_limit = 60 if self.session_time_limit == 30 else 30
            self.admin_timer_button.text = f"LEVEL DURATION: {self.session_time_limit}s"
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

