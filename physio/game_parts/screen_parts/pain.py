"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class PainScreenMixin:
    def _update_pain_scale(self, hand_data: HandData):
        """Select a pain dot (0-10) using either hands-free hover (1.5s) or physical mouse click"""
        cx = WINDOW_WIDTH // 2
        box_w, box_h = 60, 75
        box_gap = 25
        total_w = 11 * box_w + 10 * box_gap
        start_x = cx - total_w // 2
        dy = 155

        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]

        # 1. Physical Mouse Click Support (Instant Selection for high accessibility)
        if m_clicked:
            for i in range(11):
                rect = pygame.Rect(start_x + i * (box_w + box_gap), dy, box_w, box_h)
                # Expand hit rect slightly for easier touch clicks
                hit_rect = rect.inflate(20, 20)
                if hit_rect.collidepoint(m_pos):
                    self._accept_pain_score(i)
                    if hasattr(self, '_pain_hover'):
                        del self._pain_hover
                        del self._pain_hover_t
                    return

        # 2. Hands-Free Hover Support
        if hand_data.index_tip:
            for i in range(11):
                rect = pygame.Rect(start_x + i * (box_w + box_gap), dy, box_w, box_h)
                # Expand hit rect for easier hover targeting
                hit_rect = rect.inflate(20, 20)
                if hit_rect.collidepoint(hand_data.index_tip):
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
                         pygame.Rect(0, 0, WINDOW_WIDTH, 70))
        after_session = self.state == GameState.PAIN_AFTER_SESSION
        title = "Post-Session Pain Assessment" if after_session else "Pain Level Assessment"
        h1 = self.font_large.render(title, True, (0, 200, 255))
        self.screen.blit(h1, h1.get_rect(center=(cx, 35)))

        prompt = (
            "Please rate your pain level after completing today's exercises.  (0 = No Pain   10 = Worst Pain)"
            if after_session
            else "Please rate your current pain level from 0 to 10.  (0 = No Pain   10 = Worst Pain)"
        )
        sub = self.font_small.render(prompt, True, (130, 160, 200))
        self.screen.blit(sub, sub.get_rect(center=(cx, 110)))

        # WHO NRS descriptors
        descriptors = {0:"None", 1:"Min", 2:"Mild", 3:"Mild",
                       4:"Mod", 5:"Mod", 6:"Mod",
                       7:"High", 8:"High", 9:"V.High", 10:"Extreme"}
        colors_nrs = [(50,220,120),(100,230,130),(160,230,100),(200,230,80),
                      (255,220,0),(255,190,0),(255,150,0),(255,100,0),
                      (240,60,60),(220,30,30),(200,0,0)]
        box_w, box_h = 60, 75
        box_gap = 25
        total_w = 11 * box_w + 10 * box_gap
        start_x = cx - total_w // 2
        hover_i  = getattr(self, '_pain_hover', -1)
        hover_t  = getattr(self, '_pain_hover_t', t)

        dy = 155

        for i in range(11):
            dx = start_x + i * (box_w + box_gap)
            col = colors_nrs[i]
            rect = pygame.Rect(dx, dy, box_w, box_h)

            if i == hover_i:
                progress = min((t - hover_t) / 1.5, 1.0)
                
                # Subtle dark background
                pygame.draw.rect(self.screen, tuple(int(c*0.15) for c in col), rect, border_radius=10)
                
                # Cool bottom-up fill loader effect
                fill_h = int(box_h * progress)
                if fill_h > 0:
                    fill_rect = pygame.Rect(dx, dy + box_h - fill_h, box_w, fill_h)
                    old_clip = self.screen.get_clip()
                    self.screen.set_clip(fill_rect.clip(old_clip))
                    # Draw solid rounded rect; only the bottom fill_rect part is visible!
                    pygame.draw.rect(self.screen, tuple(int(c*0.6) for c in col), rect, border_radius=10)
                    self.screen.set_clip(old_clip)

                # Glowing border that expands
                pygame.draw.rect(self.screen, col, rect, max(2, int(7 * progress)), border_radius=10)
                
                # Text turns white as it fills
                nm_col = (255, 255, 255) if progress > 0.5 else col
            else:
                # Normal state: empty background with solid thin colored border
                pygame.draw.rect(self.screen, tuple(int(c*0.05) for c in col), rect, border_radius=10)
                pygame.draw.rect(self.screen, col, rect, 2, border_radius=10)
                nm_col = col

            # Number
            nm = self.font_large.render(str(i), True, nm_col)
            self.screen.blit(nm, nm.get_rect(center=rect.center))

            # Descriptor below
            dc = self.font_hint.render(descriptors[i], True, col)
            self.screen.blit(dc, dc.get_rect(center=(rect.centerx, rect.bottom + 16)))

        # Selected pain label / Feedback (placed safely above camera PIP)
        hint_y = 285
        if hover_i >= 0:
            lbl = self.font_medium.render(
                f"Pain: {hover_i}/10 — {descriptors[hover_i]}   Hold 1.5s to confirm",
                True, colors_nrs[hover_i])
            self.screen.blit(lbl, lbl.get_rect(center=(cx, hint_y)))
        else:
            hint = self.font_small.render(
                "Point your index finger at a number to select",
                True, (140, 160, 180))
            self.screen.blit(hint, hint.get_rect(center=(cx, hint_y)))

        # Floating PIP Hand Alignment Camera
        pip_w, pip_h = 320, 240
        pip_x = cx - pip_w // 2
        pip_y = 325
        
        # Draw camera with cyan rounded border matching the mockup
        border_col = (0, 180, 220)
        pygame.draw.rect(self.screen, (10, 15, 25), (pip_x - 2, pip_y - 2, pip_w + 4, pip_h + 4), border_radius=8)
        pygame.draw.rect(self.screen, border_col, (pip_x - 2, pip_y - 2, pip_w + 4, pip_h + 4), 2, border_radius=8)
        self._draw_camera_preview(pip_x, pip_y, pip_w, pip_h, label="")
        
        lbl_pip = self.font_tiny.render("PAIN ASSESS HAND ALIGNMENT", True, border_col)
        self.screen.blit(lbl_pip, lbl_pip.get_rect(center=(cx, pip_y + pip_h + 16)))

        # Clinical note
        note = self.font_hint.render(
            "NRS Scale — Even with 0 (No Pain), repetitive coordination and ROM exercises are critical to rebuild neural motor pathways.",
            True, (60, 90, 130))
        self.screen.blit(note, note.get_rect(center=(cx, WINDOW_HEIGHT - 25)))

        # Cursor
        hand_data = self.hand_engine.get_hand_data()
        self._draw_cursor(hand_data)

