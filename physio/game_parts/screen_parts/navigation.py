"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class NavigationScreenMixin:
    def _update_age_select(self, hand_data: HandData):
        """Handle age-group selection from the welcome screen."""
        age_groups = [
            AgeGroup.CHILD,
            AgeGroup.YOUNG_ADULT,
            AgeGroup.ADULT,
            AgeGroup.SENIOR,
        ]
        for age_group, button in zip(age_groups, self.age_buttons):
            if button.update(hand_data.index_tip):
                self.age_group = age_group
                self.state = GameState.MAIN_MENU
                self.sounds.play("select")
                print(f"Selected age group: {self.age_group.value}")
                break

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
            "Functional Spatial Coord\n(Toy Builder)",
            "Precision Path - Dots\n(Hand Trace)",
            "Precision Pathway\n(Fine Motor Control)"
        ]
        btn_font = pygame.font.SysFont("segoeui", 16)
        for i, button in enumerate(self.level_buttons):
            if i < len(clinical_labels):
                button.text = clinical_labels[i]
            button.draw(self.screen, btn_font)

        # Instructions
        inst = self.font_tiny.render("Hover your finger over a level to select", True, COLOR_TEXT)
        inst_rect = inst.get_rect(center=(GAME_AREA_WIDTH // 2, 595))
        self.screen.blit(inst, inst_rect)

        # History, Calibration, and Exit utility buttons
        util_font = pygame.font.SysFont("segoeui", 14, bold=True)
        self.history_button.draw(self.screen, util_font, base_col=(30, 80, 150), hov_col=(50, 120, 200))
        if hasattr(self, 'calibrate_button'):
            self.calibrate_button.draw(self.screen, util_font, base_col=(120, 60, 140), hov_col=(160, 80, 180))
        if hasattr(self, 'exit_button'):
            self.exit_button.draw(self.screen, util_font, base_col=(180, 40, 40), hov_col=(255, 60, 60))
    
