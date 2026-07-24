"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class RegistrationScreenMixin:
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
        # Keep every element on an explicit vertical rhythm.  The previous
        # values placed the first label over the card subtitle at 768px high.
        field_x, field_w = left.x + 30, left.width - 60
        field_h = max(44, min(50, int(h * .065)))
        id_y = left.y + 101
        self._draw_portal_input(pygame.Rect(field_x, id_y, field_w, field_h), "CLINICAL ID LOGIN", "◉", self.patient_id_str, "Enter Clinical ID...", self.input_active == "id", now)
        divider_y = id_y + field_h + 18
        divider_cx = field_x + field_w // 2
        pygame.draw.line(scr, (48, 83, 112), (field_x, divider_y), (divider_cx - 22, divider_y), 1)
        pygame.draw.line(scr, (48, 83, 112), (divider_cx + 22, divider_y), (left.right - 30, divider_y), 1)
        or_surf = self.font_tiny.render("OR", True, (143, 167, 194))
        scr.blit(or_surf, or_surf.get_rect(center=(divider_cx, divider_y)))

        name_y = divider_y + 41
        self._draw_portal_input(pygame.Rect(field_x, name_y, field_w, field_h), "GUEST REGISTRATION", "◉", self.patient_name, "Enter Patient Name", self.input_active == "name", now)
        age_y, age_w = name_y + field_h + 39, int(field_w * .40)
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

        protocol = pygame.Rect(field_x, age_y + field_h + 22, field_w, 72)
        self._draw_glass_card(protocol, (10, 26, 39, 225), 12)
        scr.blit(self.font_tiny.render("▣  DIAGNOSTIC PROTOCOL", True, (0, 229, 255)), (protocol.x + 14, protocol.y + 10))
        for i, text in enumerate(("Stand 1–2 meters from camera", "Ensure proper room lighting", "Complete registration to unlock therapy")):
            scr.blit(self.font_tiny.render(f"✓  {text}", True, (183, 205, 224)), (protocol.x + 15, protocol.y + 29 + i * 16))

        shortcuts_y = protocol.bottom + 10
        scr.blit(self.font_tiny.render("⌨  TAB", True, (143, 167, 194)), (field_x, shortcuts_y))
        scr.blit(self.font_tiny.render("Switch Field", True, (143, 167, 194)), (field_x + 58, shortcuts_y))
        scr.blit(self.font_tiny.render("⌨  ENTER", True, (143, 167, 194)), (field_x + field_w // 2, shortcuts_y))
        scr.blit(self.font_tiny.render("Launch Therapy", True, (143, 167, 194)), (field_x + field_w // 2 + 74, shortcuts_y))
        button_rect = pygame.Rect(field_x, shortcuts_y + 25, field_w, field_h)
        self.quick_start_button.rect = button_rect
        ready = bool(self.patient_name and self.patient_age)
        base, hover, border = ((16, 128, 84), (24, 192, 120), (24, 224, 143)) if ready else ((12, 86, 125), (0, 145, 190), (0, 229, 255))
        self.quick_start_button.draw(scr, self.font_small, "▶  Start Rehabilitation" if ready else "▶  Quick Start", base_col=base, hov_col=hover, border_col=border)

        # Live sensor feed.
        scr.blit(self.font_head.render("Live Sensor Feed", True, (244, 248, 252)), (right.x + 24, right.y + 22))
        scr.blit(self.font_tiny.render("HIGH-RESOLUTION NEURAL SENSOR", True, (143, 167, 194)), (right.x + 25, right.y + 51))
        camera = pygame.Rect(right.x + 24, right.y + 86, right.width - 48, min(int((right.width - 48) * .56), int(right.height * .52)))
        self._draw_camera_preview(camera.x, camera.y, camera.width, camera.height, "LIVE CAMERA PREVIEW")
        hand_data = self.hand_engine.get_hand_data()
        detected = hand_data.hand_label != "Unknown"
        status, status_col = ("Hand detected — calibration ready", (24, 224, 143)) if detected else ("Awaiting hand calibration...", (255, 176, 0))
        # Reserve room for the camera caption and status marker below the feed.
        telemetry = pygame.Rect(right.x + 24, camera.bottom + 36, right.width - 48, right.bottom - camera.bottom - 60)
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

