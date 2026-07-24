"""Screen rendering and interaction helpers for PhysioSystem."""

from ..shared import *


class PainScreenMixin:
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

