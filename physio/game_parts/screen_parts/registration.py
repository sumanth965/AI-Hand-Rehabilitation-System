"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class RegistrationScreenMixin:
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

    # ── Drawing helpers ────────────────────────────────────────────────────────

    def _draw_glass_card(self, rect, fill=(13, 22, 34, 235), radius=18):
        """Draw a frosted-glass card with a subtle cyan border."""
        surface = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(surface, fill, surface.get_rect(), border_radius=radius)
        pygame.draw.rect(surface, (0, 229, 255, 55), surface.get_rect(), 1, border_radius=radius)
        self.screen.blit(surface, rect.topleft)

    def _draw_portal_input(self, rect, label, icon, value, placeholder, active, now):
        """Draw a labelled input field with vertically-centred icon and text."""
        # Label — 22 px above the field top
        label_color = (0, 229, 255) if active else (143, 167, 194)
        lbl_surf = self.font_tiny.render(label, True, label_color)
        self.screen.blit(lbl_surf, (rect.x, rect.y - 22))

        # Active glow halo
        if active:
            halo = pygame.Surface((rect.width + 8, rect.height + 8), pygame.SRCALPHA)
            pygame.draw.rect(halo, (0, 229, 255, 45), halo.get_rect(), 3, border_radius=12)
            self.screen.blit(halo, (rect.x - 4, rect.y - 4))

        # Field background + border
        pygame.draw.rect(self.screen, (8, 17, 28), rect, border_radius=10)
        border_col = (0, 229, 255) if active else (48, 83, 112)
        pygame.draw.rect(self.screen, border_col, rect, 2 if active else 1, border_radius=10)

        # Icon — vertically centred inside the field
        icon_surf = self.font_hint.render(icon, True, (0, 229, 255))
        self.screen.blit(icon_surf, (rect.x + 14, rect.centery - icon_surf.get_height() // 2))

        # Text / placeholder — vertically centred
        cursor = "|" if active and int(now * 2) % 2 == 0 else ""
        display_text = f"{value}{cursor}" if value else placeholder
        text_col = (244, 248, 252) if value else (143, 167, 194)
        text_surf = self.font_hint.render(display_text, True, text_col)
        self.screen.blit(text_surf, (rect.x + 46, rect.centery - text_surf.get_height() // 2))

    def _draw_keyboard_chip(self, chip_cx, y, key_label, action_label):
        """Draw a single styled keyboard-shortcut chip centred at chip_cx."""
        key_surf  = self.font_tiny.render(key_label,    True, (0, 229, 255))
        act_surf  = self.font_tiny.render(action_label, True, (183, 205, 224))
        chip_w    = key_surf.get_width() + act_surf.get_width() + 36
        chip_h    = 30
        chip_rect = pygame.Rect(chip_cx - chip_w // 2, y, chip_w, chip_h)
        # Background + border
        bg = pygame.Surface(chip_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (18, 34, 52, 230), bg.get_rect(), border_radius=8)
        pygame.draw.rect(bg, (0, 229, 255, 80),  bg.get_rect(), 1, border_radius=8)
        self.screen.blit(bg, chip_rect.topleft)
        # Key label (cyan)
        kx = chip_rect.x + 12
        ky = chip_rect.centery - key_surf.get_height() // 2
        self.screen.blit(key_surf, (kx, ky))
        # Action label (secondary)
        self.screen.blit(act_surf, (kx + key_surf.get_width() + 8,
                                    chip_rect.centery - act_surf.get_height() // 2))

    def _draw_portal_shortcuts(self, field_x, field_w, y):
        """Draw two keyboard shortcut chips, evenly placed within field_w."""
        quarter = field_w // 4
        self._draw_keyboard_chip(field_x + quarter,             y, "[TAB]",   "Switch Field")
        self._draw_keyboard_chip(field_x + field_w - quarter,   y, "[ENTER]", "Launch Therapy")

    def _draw_sensor_status(self, rect, status, status_col, now, detected):
        """Draw the live-feed telemetry panel with evenly spaced status items."""
        pad = 16
        self._draw_glass_card(rect, (10, 26, 39, 225), 12)

        # Row 1 — sensor header
        title_surf = self.font_tiny.render("✦  HIGH RESOLUTION NEURAL SENSOR", True, (244, 248, 252))
        self.screen.blit(title_surf, (rect.x + pad, rect.y + pad))

        # Row 2 — calibration status
        status_y = rect.y + pad + title_surf.get_height() + 8
        status_surf = self.font_tiny.render(status, True, status_col)
        self.screen.blit(status_surf, (rect.x + pad, status_y))

        # Row 3 — progress bar
        bar_y = status_y + status_surf.get_height() + 10
        bar = pygame.Rect(rect.x + pad, bar_y, rect.width - pad * 2, 8)
        pygame.draw.rect(self.screen, (30, 55, 75), bar, border_radius=4)
        progress = 0.78 if detected else 0.28 + 0.12 * (0.5 + 0.5 * math.sin(now * 1.5))
        pygame.draw.rect(
            self.screen, status_col,
            (bar.x, bar.y, int(bar.width * progress), bar.height),
            border_radius=4,
        )

        # Row 4 — three evenly-spaced status badges, bottom-anchored
        labels   = ("● Secure Connection", "◌ Real-time Tracking", "▣ Privacy Mode")
        rendered = [self.font_tiny.render(lbl, True, (24, 224, 143)) for lbl in labels]
        total_w  = sum(s.get_width() for s in rendered)
        gap      = max(8, (rect.width - pad * 2 - total_w) // max(1, len(rendered) - 1))
        bx       = rect.x + pad
        badge_y  = rect.bottom - rendered[0].get_height() - pad
        for s in rendered:
            self.screen.blit(s, (bx, badge_y))
            bx += s.get_width() + gap

    # ── Main registration screen ───────────────────────────────────────────────

    def _draw_patient_registration(self):
        """Responsive 2026 clinical portal; functionality is unchanged."""
        now  = time.time()
        scr  = self.screen
        w, h = scr.get_size()
        cx   = w // 2

        # ── Layout constants ──────────────────────────────────────────────
        MARGIN    = max(20, int(w * 0.022))
        HEADER_H  = max(52, int(h * 0.08))
        TOP       = HEADER_H + 14
        BOTTOM    = h - MARGIN                        # extend to full height (feature bar removed)
        PANEL_GAP = 14
        PAD       = max(20, min(28, int(w * 0.022))) # card-internal padding, scales with width
        FIELD_H   = max(40, min(52, int(h * 0.068))) # input height, scales with screen height

        # ── Adaptive vertical rhythm ──────────────────────────────────────
        # Measure all fixed-height content (no gaps included)
        _th      = self.font_head.size("A")[1]        # heading row  (~32 px)
        _sh      = self.font_tiny.size("A")[1]        # small row    (~18 px)
        _diag_h  = 14 + _sh + 3 * (_sh + 5) + 12    # diagnostic card
        _fixed   = (_th + _sh                        # heading + subtitle
                    + (22 + FIELD_H) * 3             # label+field × 3
                    + _diag_h                        # diagnostic card
                    + 30                             # chips row
                    + FIELD_H + 4)                   # button
        _avail   = (BOTTOM - TOP) - PAD * 2          # usable interior height
        # Spread remaining space across 8 gap slots; clamp between 4 and 30 px
        _gap     = max(4, min(30, (_avail - _fixed) // 8))
        V_SM     = max(3, _gap // 2)
        V_MD     = _gap
        V_LG     = max(_gap, _gap + _gap // 3)

        # ── Background: gradient + grid ───────────────────────────────────
        for y in range(0, h, 4):
            blend = y / max(h, 1)
            pygame.draw.rect(scr,
                (6 + int(5 * blend), 11 + int(9 * blend), 20 + int(16 * blend)),
                (0, y, w, 4))
        for x in range(0, w, 48):
            pygame.draw.line(scr, (14, 35, 51), (x, HEADER_H), (x, BOTTOM), 1)
        for y in range(HEADER_H, BOTTOM, 48):
            pygame.draw.line(scr, (14, 35, 51), (0, y), (w, y), 1)

        # ── Header / title bar ────────────────────────────────────────────
        title_surf = self.font_head.render("CLINICAL REGISTRATION PORTAL", True, (244, 248, 252))
        scr.blit(title_surf, title_surf.get_rect(center=(cx, HEADER_H // 2 - 2)))
        line_hw = 130
        pygame.draw.line(scr, (0, 229, 255),
                         (cx - line_hw, HEADER_H - 8), (cx + line_hw, HEADER_H - 8), 2)

        # ── Two-column panels ─────────────────────────────────────────────
        content_w = w - 2 * MARGIN
        left_w    = int(content_w * 0.55)
        right_w   = content_w - left_w - PANEL_GAP
        left      = pygame.Rect(MARGIN,                    TOP, left_w,  BOTTOM - TOP)
        right     = pygame.Rect(MARGIN + left_w + PANEL_GAP, TOP, right_w, BOTTOM - TOP)
        self._draw_glass_card(left)
        self._draw_glass_card(right)

        # ══════════════════════════════════════════════════════════════════
        # LEFT PANEL — vertical rhythm cursor cy_l
        # ══════════════════════════════════════════════════════════════════
        field_x = left.x + PAD
        field_w = left.width - PAD * 2
        cy_l    = left.y + PAD

        # Section heading
        scr.blit(self.font_head.render("Registration Portal", True, (244, 248, 252)),
                 (field_x, cy_l))
        cy_l += self.font_head.size("A")[1] + V_SM
        scr.blit(self.font_tiny.render("PATIENT ACCESS & THERAPY INTAKE", True, (143, 167, 194)),
                 (field_x, cy_l))
        cy_l += self.font_tiny.size("A")[1] + V_MD

        # Thin section separator
        pygame.draw.line(scr, (48, 83, 112), (field_x, cy_l), (left.right - PAD, cy_l), 1)
        cy_l += V_MD

        # Clinical ID field (label sits 22 px above the rect top → add 22 to cy_l)
        id_rect = pygame.Rect(field_x, cy_l + 22, field_w, FIELD_H)
        self._draw_portal_input(id_rect, "CLINICAL ID LOGIN", "◉",
                                self.patient_id_str, "Enter Clinical ID...",
                                self.input_active == "id", now)
        cy_l = id_rect.bottom + V_MD

        # OR divider
        div_cx  = field_x + field_w // 2
        or_surf = self.font_tiny.render("OR", True, (143, 167, 194))
        pygame.draw.line(scr, (48, 83, 112), (field_x, cy_l), (div_cx - 18, cy_l), 1)
        pygame.draw.line(scr, (48, 83, 112), (div_cx + 18, cy_l), (field_x + field_w, cy_l), 1)
        scr.blit(or_surf, or_surf.get_rect(center=(div_cx, cy_l)))
        cy_l += V_MD

        # Guest name field
        name_rect = pygame.Rect(field_x, cy_l + 22, field_w, FIELD_H)
        self._draw_portal_input(name_rect, "GUEST REGISTRATION", "◉",
                                self.patient_name, "Enter Patient Name",
                                self.input_active == "name", now)
        cy_l = name_rect.bottom + V_MD

        # Age field + badge
        age_w    = int(field_w * 0.40)
        age_rect = pygame.Rect(field_x, cy_l + 22, age_w, FIELD_H)
        self._draw_portal_input(age_rect, "PATIENT AGE", "□",
                                self.patient_age, "00",
                                self.input_active == "age", now)
        if self.patient_age.isdigit():
            age = int(self.patient_age)
            badge, b_col = ("Adult Rehabilitation", (24, 224, 143))
            if age <= 12:  badge, b_col = ("Pediatric Mode", (255, 146, 187))
            elif age > 60: badge, b_col = ("Geriatric Care", (255, 176,   0))
            badge_surf = self.font_tiny.render(f"✦  {badge}", True, b_col)
            badge_rect = badge_surf.get_rect(midleft=(field_x + age_w + 18, age_rect.centery))
            pygame.draw.rect(scr, (13, 31, 44), badge_rect.inflate(20, 12), border_radius=13)
            scr.blit(badge_surf, badge_rect)
        cy_l = age_rect.bottom + V_LG

        # Diagnostic Protocol card (dynamic height)
        items    = ("Stand 1–2 meters from camera",
                    "Ensure proper room lighting",
                    "Complete registration to unlock therapy")
        row_h    = self.font_tiny.size("A")[1]
        diag_h   = 14 + row_h + len(items) * (row_h + 6) + 14
        diag_rect = pygame.Rect(field_x, cy_l, field_w, diag_h)
        self._draw_glass_card(diag_rect, (10, 26, 39, 225), 12)
        dy = diag_rect.y + 14
        scr.blit(self.font_tiny.render("▣  DIAGNOSTIC PROTOCOL", True, (0, 229, 255)),
                 (diag_rect.x + 16, dy))
        dy += row_h + 10
        for item in items:
            scr.blit(self.font_tiny.render(f"✓  {item}", True, (183, 205, 224)),
                     (diag_rect.x + 16, dy))
            dy += row_h + 6
        cy_l = diag_rect.bottom + V_MD

        # Keyboard shortcut chips
        self._draw_portal_shortcuts(field_x, field_w, cy_l)
        cy_l += 30 + V_MD

        # Quick Start / Start Rehabilitation button
        button_rect = pygame.Rect(field_x, cy_l, field_w, FIELD_H + 4)
        self.quick_start_button.rect = button_rect
        ready = bool(self.patient_name and self.patient_age)
        base, hover, border = ((16, 128, 84), (24, 192, 120), (24, 224, 143)) if ready \
                         else ((12, 86, 125), (0, 145, 190), (0, 229, 255))
        button_text = "▶  Start Rehabilitation" if ready else "▶  Quick Start"
        self.quick_start_button.draw(scr, self.font_small, button_text,
                                     base_col=base, hov_col=hover, border_col=border)

        # ══════════════════════════════════════════════════════════════════
        # RIGHT PANEL — vertical rhythm cursor cy_r
        # ══════════════════════════════════════════════════════════════════
        rx   = right.x + PAD
        cy_r = right.y + PAD

        # Section heading
        scr.blit(self.font_head.render("Live Sensor Feed", True, (244, 248, 252)), (rx, cy_r))
        cy_r += self.font_head.size("A")[1] + V_SM
        scr.blit(self.font_tiny.render("HIGH-RESOLUTION NEURAL SENSOR", True, (143, 167, 194)),
                 (rx, cy_r))
        cy_r += self.font_tiny.size("A")[1] + V_MD

        # Camera preview — ~65% of available right-panel height
        cam_w = right.width - PAD * 2
        cam_h = min(int(cam_w * 0.56), int(right.height * 0.60))
        camera = pygame.Rect(rx, cy_r, cam_w, cam_h)
        self._draw_camera_preview(camera.x, camera.y, camera.width, camera.height,
                                  "LIVE CAMERA PREVIEW")
        cy_r = camera.bottom + V_MD

        # Sensor / telemetry panel — fills remaining space
        hand_data = self.hand_engine.get_hand_data()
        detected  = hand_data.hand_label != "Unknown"
        status, status_col = (
            ("Hand detected — calibration ready", (24, 224, 143))
            if detected
            else ("Awaiting hand calibration...", (255, 176, 0))
        )
        telemetry_h = right.bottom - cy_r - 8
        if telemetry_h > 40:
            telemetry = pygame.Rect(rx, cy_r, cam_w, telemetry_h)
            self._draw_sensor_status(telemetry, status, status_col, now, detected)

        self._draw_cursor(hand_data)
