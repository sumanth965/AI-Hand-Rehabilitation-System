"""
Medical Sidebars and Post-Game Summary for the Zero-Keyboard AI Physiotherapy System.
"""

import cv2
import math
import pygame
import io
from typing import Optional, Tuple

from physio.constants import (
    GAME_AREA_WIDTH, SIDEBAR_WIDTH, WINDOW_HEIGHT,
    COLOR_MED_TEXT, COLOR_MED_MUTED, COLOR_MED_PANEL,
    COLOR_MED_PRIMARY, COLOR_MED_SUCCESS, COLOR_MED_WARNING,
    COLOR_DANGER
)
from physio.models import HandData

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class MedicalSidebar:
    """Right sidebar with camera feed and clinical analytics — upgraded"""

    def __init__(self):
        self.x = GAME_AREA_WIDTH
        self.width = SIDEBAR_WIDTH
        self.font_title  = pygame.font.SysFont("segoeui", 22)
        self.font_label  = pygame.font.SysFont("segoeui", 18)
        self.font_data   = pygame.font.SysFont("segoeui", 22)
        self.font_big    = pygame.font.SysFont("segoeui", 26)

    # ------------------------------------------------------------------
    def _section_header(self, screen, text, y, color):
        """Draw a colored section header bar"""
        bar_rect = pygame.Rect(self.x + 6, y, self.width - 12, 24)
        pygame.draw.rect(screen, color, bar_rect, border_radius=5)
        lbl = self.font_label.render(text, True, (0, 0, 0))
        lbl_rect = lbl.get_rect(midleft=(bar_rect.x + 8, bar_rect.centery))
        screen.blit(lbl, lbl_rect)
        return y + 30

    def _rom_bar(self, screen, label, angle_deg, max_deg, y):
        """Draw a labeled ROM progress bar"""
        # Label
        lbl = self.font_label.render(label, True, (180, 200, 220))
        screen.blit(lbl, (self.x + 8, y))
        # Angle value
        val_str = f"{angle_deg:.0f}°"
        val = self.font_label.render(val_str, True, (255, 255, 255))
        screen.blit(val, (self.x + self.width - val.get_width() - 8, y))
        y += 18
        # Bar background
        bar_w = self.width - 16
        pygame.draw.rect(screen, (40, 45, 65),
                         (self.x + 8, y, bar_w, 10), border_radius=5)
        # Bar fill — color by ROM quality
        ratio = min(angle_deg / max_deg, 1.0)
        if ratio < 0.4:
            bar_color = (220, 60, 60)    # Red — low ROM
        elif ratio < 0.7:
            bar_color = (255, 180, 0)    # Amber — moderate
        else:
            bar_color = (50, 220, 120)   # Green — good ROM
        filled = int(bar_w * ratio)
        if filled > 0:
            pygame.draw.rect(screen, bar_color,
                             (self.x + 8, y, filled, 10), border_radius=5)
        return y + 18

    # ------------------------------------------------------------------
    def draw(self, screen, camera_frame, hand_data: HandData,
             level_goals: str, accuracy_hits: int = 0,
             accuracy_attempts: int = 0, is_results: bool = False,
             is_calibration: bool = False, is_mirror_active: bool = False,
             is_paused: bool = False):
        """Draw sidebar with camera and clinical stats"""

        # ── Background ──────────────────────────────────────────────
        # Use a sleek dark blue/gray instead of flat color
        pygame.draw.rect(screen, (8, 12, 20),
                         (self.x, 0, self.width, WINDOW_HEIGHT))
        
        # Tech Grid overlay
        for i in range(0, self.width, 20):
            pygame.draw.line(screen, (15, 25, 35), (self.x + i, 0), (self.x + i, WINDOW_HEIGHT), 1)
        for i in range(0, WINDOW_HEIGHT, 20):
            pygame.draw.line(screen, (15, 25, 35), (self.x, i), (self.x + self.width, i), 1)

        # Glowing left border
        pygame.draw.line(screen, (0, 255, 200),
                         (self.x, 0), (self.x, WINDOW_HEIGHT), 2)
        pygame.draw.line(screen, (0, 150, 120),
                         (self.x+2, 0), (self.x+2, WINDOW_HEIGHT), 1)

        # ── Title bar ───────────────────────────────────────────────
        title_bar = pygame.Rect(self.x, 0, self.width, 40)
        pygame.draw.rect(screen, (4, 18, 30), title_bar)
        pygame.draw.line(screen, (0, 200, 255), (self.x, 40), (self.x + self.width, 40), 1)
        
        title = self.font_big.render("CLINICAL TELEMETRY", True, (0, 255, 200))
        screen.blit(title, (self.x + 12, 10))

        # ── Camera feed ─────────────────────────────────────────────
        cam_y = 55
        cam_drawn = False
        
        # Prevent duplicate camera feed in Diagnostics screen when the central diagnostic camera is active.
        # On all other screens, the camera feed stays active permanently in the sidebar.
        redirected = is_calibration
        
        if redirected:
            try:
                feed_h = int(self.width * 0.75)
                cam_rect = pygame.Rect(self.x + 10, cam_y - 2, self.width - 20, feed_h + 4)
                pygame.draw.rect(screen, (15, 20, 30), cam_rect, border_radius=6)
                pygame.draw.rect(screen, (0, 200, 255) if is_calibration else (255, 80, 80), cam_rect, 1, border_radius=6)
                
                if is_calibration:
                    nc_txt1 = self.font_label.render("DIAGNOSTICS ACTIVE", True, (0, 200, 255))
                    nc_txt2 = self.font_label.render("REFER TO CENTER SCANNER", True, (150, 170, 190))
                else:
                    nc_txt1 = self.font_label.render("MIRROR MODE REDIRECTED", True, (255, 80, 80))
                    nc_txt2 = self.font_label.render("REFER TO CENTER SCREEN", True, (150, 170, 190))
                
                screen.blit(nc_txt1, nc_txt1.get_rect(center=(cam_rect.centerx, cam_rect.centery - 12)))
                screen.blit(nc_txt2, nc_txt2.get_rect(center=(cam_rect.centerx, cam_rect.centery + 12)))
                
                y_offset = cam_y + feed_h + 20
                cam_drawn = True
            except Exception:
                pass
        elif camera_frame is not None:
            try:
                feed_h = int(self.width * 0.75)
                frame_resized = cv2.resize(camera_frame, (self.width - 24, feed_h))
                frame_rgb     = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                frame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                
                # Check if hand tracking is lost (turns border red and overlays warning banner inside sidebar feed)
                is_hand_lost = (hand_data.index_tip is None)
                
                # Draw high-tech camera border (color turns red when hand is lost)
                cam_rect = pygame.Rect(self.x + 10, cam_y - 2, self.width - 20, feed_h + 4)
                pygame.draw.rect(screen, (10, 20, 30), cam_rect, border_radius=6)
                
                border_color = (255, 80, 80) if is_hand_lost else (0, 150, 255)
                pygame.draw.rect(screen, border_color, cam_rect, 2, border_radius=6)
                
                screen.blit(frame_surface, (self.x + 12, cam_y))
                
                # Tech corners
                l = 15
                c = (255, 80, 80) if is_hand_lost else (0, 255, 150)
                px, py = self.x + 12, cam_y
                pw, ph = self.width - 24, feed_h
                pygame.draw.line(screen, c, (px, py), (px+l, py), 2)
                pygame.draw.line(screen, c, (px, py), (px, py+l), 2)
                pygame.draw.line(screen, c, (px+pw, py), (px+pw-l, py), 2)
                pygame.draw.line(screen, c, (px+pw, py), (px+pw, py+l), 2)
                
                # Overlay warning banner on camera feed when hand is lost
                if is_hand_lost:
                    warn_surface = pygame.Surface((self.width - 24, 32), pygame.SRCALPHA)
                    warn_surface.fill((255, 40, 40, 160)) # semi-transparent red
                    screen.blit(warn_surface, (self.x + 12, cam_y + feed_h - 32))
                    warn_txt = self.font_label.render("ALIGN HAND IN FEED", True, (255, 255, 255))
                    screen.blit(warn_txt, warn_txt.get_rect(center=(self.x + self.width // 2, cam_y + feed_h - 16)))
                
                y_offset = cam_y + feed_h + 20
                cam_drawn = True
            except Exception:
                pass
        if not cam_drawn:
            no_cam = pygame.Rect(self.x + 12, cam_y, self.width - 24, 120)
            pygame.draw.rect(screen, (15, 20, 30), no_cam, border_radius=6)
            pygame.draw.rect(screen, (100, 40, 40), no_cam, 1, border_radius=6)
            nc_txt = self.font_label.render("CAMERA OFFLINE", True, (255, 80, 80))
            screen.blit(nc_txt, nc_txt.get_rect(center=no_cam.center))
            y_offset = cam_y + 140

        # ── Hand detection status ────────────────────────────────────
        has_hand = hand_data.index_tip is not None
        status_color  = (0, 255, 150) if has_hand else (255, 80, 80)
        status_text   = "NEURAL LINK ESTABLISHED" if has_hand else "SEARCHING FOR HAND..."
        
        status_rect = pygame.Rect(self.x + 12, y_offset, self.width - 24, 28)
        pygame.draw.rect(screen, (status_color[0]//4, status_color[1]//4, status_color[2]//4), status_rect, border_radius=4)
        pygame.draw.rect(screen, status_color, status_rect, 1, border_radius=4)
        
        st = self.font_label.render(status_text, True, status_color)
        screen.blit(st, st.get_rect(center=status_rect.center))
        y_offset += 40

        if is_results:
            return

        # ── ROM / Joint Angles ───────────────────────────────────────
        y_offset = self._section_header(screen, "RANGE OF MOTION", y_offset,
                                         (0, 140, 180))
        if hand_data.knuckle_angles:
            finger_names = ["Index", "Middle", "Ring", "Pinky"]
            for i, ang in enumerate(hand_data.knuckle_angles[:4]):
                name = finger_names[i] if i < len(finger_names) else f"F{i+1}"
                y_offset = self._rom_bar(screen, name, ang, 90.0, y_offset)
                y_offset += 2
        else:
            no_data = self.font_label.render("Move fingers to measure", True,
                                              (100, 120, 150))
            screen.blit(no_data, (self.x + 8, y_offset))
            y_offset += 25

        # Extension value
        ext_lbl = self.font_label.render(
            f"Extension: {hand_data.finger_extension:.0f}px", True, (160, 200, 220))
        screen.blit(ext_lbl, (self.x + 8, y_offset))
        y_offset += 30

        # ── Gestures ────────────────────────────────────────────────
        y_offset = self._section_header(screen, "GESTURES", y_offset,
                                         (120, 80, 0))

        def _pill(text, active, y):
            pill = pygame.Rect(self.x + 8, y, self.width - 16, 22)
            pygame.draw.rect(screen, (30, 180, 80) if active else (50, 55, 75),
                             pill, border_radius=11)
            pygame.draw.rect(screen, (50, 220, 120) if active else (80, 90, 110),
                             pill, 1, border_radius=11)
            pt = self.font_label.render(text, True,
                                         (255, 255, 255) if active else (130, 150, 170))
            screen.blit(pt, pt.get_rect(center=pill.center))
            return y + 26

        y_offset = _pill("PINCH" + (" ACTIVE" if hand_data.is_pinching else ""),
                          hand_data.is_pinching, y_offset)
        y_offset = _pill("FIST"  + (" ACTIVE" if hand_data.is_fist    else ""),
                          hand_data.is_fist,    y_offset)
        y_offset += 15

        # ── Live Accuracy ────────────────────────────────────────────
        y_offset = self._section_header(screen, "SESSION STATS", y_offset,
                                         (60, 30, 120))
        acc = (accuracy_hits / accuracy_attempts * 100) \
              if accuracy_attempts > 0 else 0.0
        acc_str = f"Accuracy: {acc:.0f}%"
        acc_color = (50, 220, 120) if acc >= 70 else \
                    (255, 180, 0)  if acc >= 40 else (220, 60, 60)
        acc_surf = self.font_data.render(acc_str, True, acc_color)
        screen.blit(acc_surf, (self.x + 8, y_offset))
        y_offset += 30

        # Accuracy bar
        bar_w = self.width - 16
        pygame.draw.rect(screen, (40, 45, 65),
                         (self.x + 8, y_offset, bar_w, 10), border_radius=5)
        filled = int(bar_w * acc / 100)
        if filled > 0:
            pygame.draw.rect(screen, acc_color,
                             (self.x + 8, y_offset, filled, 10), border_radius=5)
        y_offset += 18

        # ── Level Goals ──────────────────────────────────────────────
        y_offset = self._section_header(screen, "LEVEL GOALS", y_offset,
                                         (30, 100, 60))
        words = level_goals.split()
        line  = ""
        for word in words:
            test = line + word + " "
            if len(test) > 22:
                gl = self.font_label.render(line.strip(), True, (180, 210, 190))
                screen.blit(gl, (self.x + 8, y_offset))
                y_offset += 20
                line = word + " "
            else:
                line = test
        if line:
            gl = self.font_label.render(line.strip(), True, (180, 210, 190))
            screen.blit(gl, (self.x + 8, y_offset))


class MedicalSidebarV2:
    """Professional clinical telemetry sidebar for Phase 2."""

    def __init__(self):
        self.x = GAME_AREA_WIDTH
        self.width = SIDEBAR_WIDTH
        self.font_title = pygame.font.SysFont("segoeui", 21, bold=True)
        self.font_label = pygame.font.SysFont("segoeui", 14)
        self.font_data = pygame.font.SysFont("segoeui", 20, bold=True)
        self.font_small = pygame.font.SysFont("segoeui", 13)

    def _draw_text(self, screen, text, font, color, pos):
        screen.blit(font.render(str(text), True, color), pos)

    def _panel(self, screen, rect, border=None):
        pygame.draw.rect(screen, (255, 255, 255), rect, border_radius=12)
        border_col = border if border else (226, 232, 240)
        pygame.draw.rect(screen, border_col, rect, 1, border_radius=12)

    def _metric(self, screen, rect, label, value, color=COLOR_MED_TEXT):
        pygame.draw.rect(screen, (248, 250, 252), rect, border_radius=12)
        pygame.draw.rect(screen, (226, 232, 240), rect, 1, border_radius=12)
        self._draw_text(screen, label.upper(), self.font_small, (100, 116, 139), (rect.x + 14, rect.y + 12))
        value_surf = self.font_data.render(str(value), True, color)
        screen.blit(value_surf, (rect.x + 14, rect.y + 32))

    def _status_pill(self, screen, rect, text, color):
        bg = tuple(max(0, min(255, int(c * 0.15 + 255 * 0.85))) for c in color)
        pygame.draw.rect(screen, bg, rect, border_radius=rect.height // 2)
        txt = self.font_label.render(text, True, color)
        screen.blit(txt, txt.get_rect(center=rect.center))

    def _bar(self, screen, x, y, w, ratio, color):
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(screen, (220, 229, 238), (x, y, w, 8), border_radius=4)
        if ratio > 0:
            pygame.draw.rect(screen, color, (x, y, int(w * ratio), 8), border_radius=4)

    def _wrap(self, screen, text, x, y, max_chars, color=COLOR_MED_TEXT):
        line = ""
        for word in text.split():
            test = f"{line}{word} "
            if len(test) > max_chars:
                self._draw_text(screen, line.strip(), self.font_small, color, (x, y))
                y += 16
                line = f"{word} "
            else:
                line = test
        if line:
            self._draw_text(screen, line.strip(), self.font_small, color, (x, y))
            y += 16
        return y

    def draw(self, screen, camera_frame, hand_data: HandData,
             level_goals: str, accuracy_hits: int = 0,
             accuracy_attempts: int = 0, is_results: bool = False,
             is_calibration: bool = False, is_mirror_active: bool = False,
             is_paused: bool = False, score: int = 0,
             exercise_name: str = "Session",
             exercise_count: int = 0, session_elapsed: float = 0.0,
             pain_level: int = 0, recovery_prediction: Optional[float] = None,
             correctness_text: str = "Ready",
             is_menu: bool = False,
             readiness_score: float = 50.0,
             rec_difficulty: str = "Moderate",
             rec_explanation: str = "Baseline therapy."):
        pygame.draw.rect(screen, (248, 250, 252), (self.x, 0, self.width, WINDOW_HEIGHT))
        pygame.draw.line(screen, (226, 232, 240), (self.x, 0), (self.x, WINDOW_HEIGHT), 1)

        # Clean header text (No background box)
        self._draw_text(screen, "AI Rehabilitation Monitor", self.font_title, (15, 23, 42),
                        (self.x + 24, 26))
        self._draw_text(screen, "Live clinical session", self.font_small, (100, 116, 139),
                        (self.x + 24, 54))

        cam_y = 96
        feed_h = 184
        cam_rect = pygame.Rect(self.x + 12, cam_y, self.width - 24, feed_h)
        cam_drawn = False

        if is_calibration:
            self._panel(screen, cam_rect, border=(120, 180, 215))
            msg = self.font_label.render("Diagnostics scanner active", True, COLOR_MED_PRIMARY)
            screen.blit(msg, msg.get_rect(center=(cam_rect.centerx, cam_rect.centery - 10)))
            sub = self.font_small.render("Use the central camera preview", True, COLOR_MED_MUTED)
            screen.blit(sub, sub.get_rect(center=(cam_rect.centerx, cam_rect.centery + 12)))
            cam_drawn = True
        elif camera_frame is not None:
            try:
                frame_resized = cv2.resize(camera_frame, (cam_rect.width, cam_rect.height))
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                frame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                screen.blit(frame_surface, cam_rect.topleft)
                border = COLOR_DANGER if hand_data.index_tip is None else COLOR_MED_PRIMARY
                pygame.draw.rect(screen, border, cam_rect, 2, border_radius=8)
                overlay = pygame.Surface((cam_rect.width, 24), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 105))
                screen.blit(overlay, (cam_rect.x, cam_rect.bottom - 24))
                self._draw_text(screen, "Hand skeleton overlay", self.font_small,
                                (255, 255, 255), (cam_rect.x + 8, cam_rect.bottom - 20))
                cam_drawn = True
            except Exception:
                pass

        if not cam_drawn:
            self._panel(screen, cam_rect, border=(230, 170, 175))
            off = self.font_label.render("Camera unavailable", True, COLOR_DANGER)
            screen.blit(off, off.get_rect(center=cam_rect.center))

        y = cam_rect.bottom + 16

        if is_menu:
            # Render menu-specific sidebar (Readiness & Recommended Difficulty)
            self._status_pill(screen, pygame.Rect(self.x + 12, y, self.width - 24, 36),
                              f"Readiness Score: {readiness_score:.1f}/100", COLOR_MED_PRIMARY)
            y += 48
            
            diff_col = COLOR_MED_SUCCESS if rec_difficulty == "Easy" else COLOR_MED_WARNING if rec_difficulty == "Moderate" else COLOR_DANGER
            self._status_pill(screen, pygame.Rect(self.x + 12, y, self.width - 24, 36),
                              f"Recommended Diff: {rec_difficulty}", diff_col)
            y += 52
            
            panel = pygame.Rect(self.x + 12, y, self.width - 24, 240)
            self._panel(screen, panel)
            self._draw_text(screen, "CLINICAL RATIONALE", self.font_small, COLOR_MED_MUTED, (panel.x + 14, panel.y + 12))
            self._wrap(screen, rec_explanation, panel.x + 14, panel.y + 38, 32, COLOR_MED_TEXT)
            return

        has_hand = hand_data.index_tip is not None
        status = "Tracking stable" if has_hand else "Hand not detected"
        self._status_pill(screen, pygame.Rect(self.x + 12, y, self.width - 24, 36),
                          status, COLOR_MED_SUCCESS if has_hand else COLOR_DANGER)
        y += 48

        if is_results:
            return

        correctness_lower = correctness_text.lower()
        correct_col = COLOR_MED_SUCCESS if correctness_lower.startswith(("correct", "good", "ready")) else COLOR_DANGER
        self._status_pill(screen, pygame.Rect(self.x + 12, y, self.width - 24, 36),
                          correctness_text, correct_col)
        y += 48

        acc = (accuracy_hits / accuracy_attempts * 100) if accuracy_attempts > 0 else 0.0
        acc_col = COLOR_MED_SUCCESS if acc >= 70 else COLOR_MED_WARNING if acc >= 40 else COLOR_DANGER
        rom = sum(hand_data.knuckle_angles[:4]) / len(hand_data.knuckle_angles[:4]) if hand_data.knuckle_angles else 0.0
        card_w = (self.width - 34) // 2

        self._metric(screen, pygame.Rect(self.x + 12, y, card_w, 64), "Score", score)
        self._metric(screen, pygame.Rect(self.x + 22 + card_w, y, card_w, 64), "Accuracy", f"{acc:.0f}%", acc_col)
        y += 74
        self._metric(screen, pygame.Rect(self.x + 12, y, card_w, 64), "Exercises", exercise_count)
        mins = int(session_elapsed // 60)
        secs = int(session_elapsed % 60)
        self._metric(screen, pygame.Rect(self.x + 22 + card_w, y, card_w, 64), "Timer", f"{mins:02d}:{secs:02d}")
        y += 74
        self._metric(screen, pygame.Rect(self.x + 12, y, card_w, 64), "Current ROM", f"{rom:.0f} deg", COLOR_MED_PRIMARY)
        pain_col = COLOR_MED_SUCCESS if pain_level <= 3 else COLOR_MED_WARNING if pain_level <= 6 else COLOR_DANGER
        self._metric(screen, pygame.Rect(self.x + 22 + card_w, y, card_w, 64), "Pain Score", f"{pain_level}/10", pain_col)
        y += 74

        panel = pygame.Rect(self.x + 12, y, self.width - 24, 72)
        self._panel(screen, panel)
        self._draw_text(screen, "EXERCISE NAME", self.font_small, COLOR_MED_MUTED, (panel.x + 14, panel.y + 12))
        self._draw_text(screen, exercise_name, self.font_data, COLOR_MED_TEXT, (panel.x + 14, panel.y + 36))
        y = panel.bottom + 16

        pred_text = "Need more data"
        pred_col = COLOR_MED_MUTED
        if recovery_prediction is not None and recovery_prediction >= 0:
            pred_text = f"{recovery_prediction:.1f}% predicted recovery"
            pred_col = COLOR_MED_PRIMARY
        panel = pygame.Rect(self.x + 12, y, self.width - 24, 68)
        self._panel(screen, panel)
        self._draw_text(screen, "RECOVERY PREDICTION", self.font_small, COLOR_MED_MUTED, (panel.x + 14, panel.y + 12))
        self._draw_text(screen, pred_text, self.font_label, pred_col, (panel.x + 14, panel.y + 36))
        y = panel.bottom + 16

        panel = pygame.Rect(self.x + 12, y, self.width - 24, 114)
        self._panel(screen, panel)
        self._draw_text(screen, "STATUS MESSAGE", self.font_small, COLOR_MED_MUTED, (panel.x + 14, panel.y + 12))
        next_y = self._wrap(screen, level_goals or "Ready for guided rehabilitation.",
                            panel.x + 14, panel.y + 38, 34, COLOR_MED_TEXT)
        if hand_data.is_pinching or hand_data.is_fist:
            gesture = "Pinch active" if hand_data.is_pinching else "Fist active"
            self._draw_text(screen, gesture, self.font_small, COLOR_MED_PRIMARY,
                            (panel.x + 14, min(next_y + 4, panel.bottom - 22)))
        self._bar(screen, panel.x + 14, panel.bottom - 16, panel.width - 28, acc / 100.0, acc_col)


class PostGameSummary:
    """
    Doctor-style clinical report for:
    AI-Based Gamified Physiotherapy Assistant for Post-Injury Hand Rehabilitation
    """

    ROM_NORMAL = 90.0  # MCP full flexion target (degrees)
    ROM_GOOD   = 65.0
    ROM_FAIR   = 40.0

    LEVEL_FOCUS = {
        1: ("Finger Flexibility & Reach",   "wrist flexion/extension"),
        2: ("Grip Strength & Coordination", "power grip / catch reflex"),
        3: ("Fine Motor & Pinch Control",   "lateral pinch / precision"),
        4: ("Hand Stability & Tracing",     "tremor reduction / smooth pursuit"),
        5: ("Spasticity & Grip Release",    "fist to open hand transition"),
        6: ("Cognitive & Motor Sequencing", "memory and targeted reach"),
    }

    # Exercise prescription per level per performance tier
    EXERCISES = {
        1: {
            "low":  [("Passive Wrist Stretch",    "Hold 30s",   "3×/day"),
                     ("Fist-to-Open Hand Cycle",   "20 reps",    "4 sets/day"),
                     ("Finger Tendon Glide",        "10 reps",    "3 sets/day")],
            "mid":  [("Active Wrist Flexion/Ext.", "15 reps",    "3 sets/day"),
                     ("Fist-to-Open + Spread",     "15 reps",    "3 sets/day"),
                     ("Tabletop Reach Exercise",    "10 reps",    "3 sets/day")],
            "high": [("Dynamic Wrist Circles",     "20 reps",    "2 sets/day"),
                     ("Finger Walking on Table",    "2 min",      "3×/day"),
                     ("Maintain current level",     "—",          "daily")],
        },
        2: {
            "low":  [("Stress Ball Squeeze",       "10s hold",   "10 reps/set × 3 sets"),
                     ("Wrist Pronation/Supination", "15 reps",    "3 sets/day"),
                     ("Clothespin Pinch",           "20 reps",    "2 sets/day")],
            "mid":  [("Grip Strengthener (light)",  "12 reps",    "3 sets/day"),
                     ("Wrist Rotation with weight", "10 reps",    "2 sets/day"),
                     ("Catching Drill (small ball)","2 min",      "2×/day")],
            "high": [("Medium Grip Strengthener",   "15 reps",    "3 sets/day"),
                     ("Coin Pick-Up Drill",          "1 min",      "3×/day"),
                     ("Advance to fine motor tasks", "—",          "daily")],
        },
        3: {
            "low":  [("Thumb Opposition (each finger)","10 reps", "3 sets/day"),
                     ("Pinch Peg Board Drill",       "2 min",      "2×/day"),
                     ("Rubber Band Extension",        "20 reps",    "3 sets/day")],
            "mid":  [("Lateral Pinch with Coins",    "20 reps",    "3 sets/day"),
                     ("Tripod Pinch Drill",           "15 reps",    "3 sets/day"),
                     ("Typing Coordination Exercise", "2 min",      "2×/day")],
            "high": [("Fine Pinch with Paper",        "30 reps",    "2 sets/day"),
                     ("Thread/Button Fastening",      "5 min",      "daily"),
                     ("Maintain precision task rotation","—",       "daily")],
        },
        4: {
            "low":  [("Supported Table Tracing",    "2 min",   "3×/day"),
                     ("Wrist Stabilization",        "10 reps", "3 sets/day"),
                     ("Slow Finger Tracking",       "1 min",   "3 sets/day")],
            "mid":  [("Freehand Air Tracing",       "2 min",   "3 sets/day"),
                     ("Shoulder Stabilization",     "15 reps", "2 sets/day"),
                     ("Figure-8 Pen Practice",      "2 min",   "2×/day")],
            "high": [("Complex Shape Tracing",      "3 min",   "2 sets/day"),
                     ("Unsupported Arm Hold",       "30 sec",  "3 sets/day"),
                     ("Maintain smooth control",    "—",       "daily")],
        },
        5: {
            "low":  [("Assisted Hand Opening",      "10 reps", "4 sets/day"),
                     ("Gentle Fist Squeezes",       "15 reps", "3 sets/day"),
                     ("Wrist Flexion Stretch",      "30 sec",  "3×/day")],
            "mid":  [("Power Grip & Fast Release",  "15 reps", "3 sets/day"),
                     ("Sponge Squeeze in Water",    "2 min",   "2×/day"),
                     ("Rubber Band Hand Opening",   "10 reps", "2 sets/day")],
            "high": [("Max Speed Open/Close",       "30 reps", "2 sets/day"),
                     ("Heavy Putty Squeeze",        "2 min",   "1×/day"),
                     ("Maintain explosive release", "—",       "daily")],
        },
        6: {
            "low":  [("Sequence Card Matching",        "5 min",   "2 sets/day"),
                     ("Touch targets on table",        "2 min",   "2×/day"),
                     ("Basic Simon Says game",         "10 reps", "3 sets/day")],
            "mid":  [("Follow therapist finger paths", "3 min",   "3 sets/day"),
                     ("Multi-step cooking tasks",      "10 min",  "1×/day"),
                     ("Cross-body reaching to targets","15 reps", "2 sets/day")],
            "high": [("Complex dance/arm sequences",   "5 min",   "2 sets/day"),
                     ("Juggling practice (1 or 2 items)","5 min", "1×/day"),
                     ("Maintain cognitive-motor speed","—",       "daily")],
        },
    }

    def __init__(self):
        self.font_title = pygame.font.SysFont("segoeui", 32, bold=True)
        self.font_head  = pygame.font.SysFont("segoeui", 26, bold=True)
        self.font_body  = pygame.font.SysFont("segoeui", 22)
        self.font_small = pygame.font.SysFont("segoeui", 17)
        self.font_tiny  = pygame.font.SysFont("segoeui", 15)
        self.font_label = pygame.font.SysFont("segoeui", 14, bold=True)
        self.session_chart = None

    # ── Helpers ───────────────────────────────────────────────────────
    def _tier(self, accuracy):
        if accuracy >= 75: return "high"
        if accuracy >= 50: return "mid"
        return "low"

    def _stars(self, accuracy):
        if accuracy >= 80: return 3
        if accuracy >= 55: return 2
        return 1

    def _rom_grade(self, angle):
        if angle >= self.ROM_NORMAL * 0.85: return "EXCELLENT", (50, 220, 120)
        if angle >= self.ROM_GOOD:           return "GOOD",      (100, 200, 255)
        if angle >= self.ROM_FAIR:           return "FAIR",      (255, 180, 0)
        return "POOR",                                            (220, 60, 60)

    def _section_bar(self, screen, title, x, y, w, col=(0, 130, 180)):
        pygame.draw.rect(screen, col,
                         pygame.Rect(x, y, w, 26), border_radius=5)
        t = self.font_label.render(f"  {title}", True, (255, 255, 255))
        screen.blit(t, (x + 6, y + 6))
        return y + 34

    def _line(self, screen, txt, y, col=(200, 215, 230), indent=24):
        s = self.font_small.render(txt, True, col)
        screen.blit(s, (indent, y))
        return y + 22

    def _draw_star(self, screen, x, y, r, filled, color):
        """Draw a 5-pointed star"""
        pts = []
        for i in range(10):
            rad = r if i % 2 == 0 else r // 2
            angle = math.radians(i * 36 - 90)
            pts.append((x + rad * math.cos(angle), y + rad * math.sin(angle)))
        if filled:
            pygame.draw.polygon(screen, color, pts)
        pygame.draw.polygon(screen, color, pts, 2)

    # ── One-Line Report ───────────────────────────────────────────────
    def _one_liner(self, level, accuracy, angle):
        if accuracy >= 80 and angle >= self.ROM_GOOD:
            return "CLINICAL SUMMARY: Excellent motor control and ROM; proceed to next challenge."
        if accuracy >= 60:
            return "CLINICAL SUMMARY: Good progress; continue focusing on finger precision and grip."
        return "CLINICAL SUMMARY: Functional recovery in progress; suggest more repetitions at slow speed."

    def generate_session_charts(self, hits, attempts, angles):
        """Generate a Pie Chart (Accuracy) and Histogram (ROM) for this session"""
        try:
            # Create a compact figure with two subplots
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6, 3), dpi=80)
            fig.patch.set_facecolor('#081224') # Match dashboard bg
            
            # 1. Pie Chart for Accuracy
            misses = max(0, attempts - hits)
            colors = ['#32dc78', '#dc3c3c'] # Success Green, Error Red
            labels = ['Hits', 'Misses']
            ax1.pie([hits if hits > 0 else 0.1, misses if misses > 0 else 0.1], 
                    labels=labels, autopct='%1.0f%%', 
                    startangle=90, colors=colors, textprops={'color':"w", 'size':8})
            ax1.set_title("Session Accuracy", color='w', size=10)
            
            # 2. Histogram for ROM
            if angles and len(angles) > 1:
                ax2.hist(angles, bins=10, color='#00c8f5', alpha=0.7)
                ax2.set_title("ROM Distribution", color='w', size=10)
            else:
                ax2.text(0.5, 0.5, "No ROM Data", color='w', ha='center')
                
            ax2.set_facecolor('#101828')
            ax2.tick_params(colors='w', labelsize=7)
            
            plt.tight_layout()
            
            buf = io.BytesIO()
            fig.savefig(buf, format='png', facecolor='#081224')
            buf.seek(0)
            plt.close(fig)
            self.session_chart = pygame.image.load(buf, 'png')
        except Exception as e:
            print(f"Chart generation error: {e}")
            self.session_chart = None

    # ── Main draw ─────────────────────────────────────────────────────
    def draw(self, screen, session_data: dict, best_data: dict,
             patient_name: str = "Patient"):
        if not session_data:
            return

        level    = session_data.get('level', 1)
        score    = session_data.get('score', 0)
        accuracy = session_data.get('avg_accuracy', 0.0)
        angle    = session_data.get('avg_hand_angle', 0.0)
        mq       = session_data.get('movement_quality_score', 80.0)
        summary_text = session_data.get('summary_text', 'Rehabilitation diagnostics successfully processed.')
        ai_recommendation = session_data.get('ai_recommendation', 'Maintain current level parameters.')

        cx  = GAME_AREA_WIDTH // 2
        grade_str, grade_col = self._rom_grade(angle)
        stars  = self._stars(accuracy)
        tier   = self._tier(accuracy)
        exs    = self.EXERCISES.get(level, {}).get(tier, [])

        # ── BACKGROUND PLATE ──────────────────────────────────────────
        plate = pygame.Rect(10, 70, GAME_AREA_WIDTH - 20, WINDOW_HEIGHT - 110)
        pygame.draw.rect(screen, (8, 12, 25), plate, border_radius=12)
        pygame.draw.rect(screen, (0, 90, 140), plate, 1, border_radius=12)

        # ── HEADER ────────────────────────────────────────────────────
        header_rect = pygame.Rect(0, 0, GAME_AREA_WIDTH, 65)
        pygame.draw.rect(screen, (10, 18, 35), header_rect)
        pygame.draw.line(screen, (0, 170, 220), (0, 65), (GAME_AREA_WIDTH, 65), 2)

        title_surf = self.font_title.render("SESSION PERFORMANCE REPORT", True, (0, 200, 255))
        screen.blit(title_surf, title_surf.get_rect(center=(cx, 33)))

        y_top = 78

        # ── CLINICAL SUMMARY (One-liner) ─────────────────────────────
        one_line = self._one_liner(level, accuracy, angle)
        ol_bg = pygame.Rect(20, y_top, GAME_AREA_WIDTH - 40, 30)
        pygame.draw.rect(screen, (18, 30, 55), ol_bg, border_radius=6)
        pygame.draw.rect(screen, (40, 65, 100), ol_bg, 1, border_radius=6)
        ol_surf = self.font_small.render(one_line, True, (255, 215, 130))
        screen.blit(ol_surf, ol_surf.get_rect(center=ol_bg.center))

        # ── COLUMNS ───────────────────────────────────────────────────
        col1_x, col2_x = 22, 492
        col_w = 448
        y = y_top + 40

        # --- LEFT: PERFORMANCE ---
        ly = y
        ly = self._section_bar(screen, "SESSION METRICS", col1_x, ly, col_w, (0, 120, 180))

        # Star visualization
        sy = ly + 8
        star_col = [(220,60,60),(255,200,0),(50,220,120)][stars-1]
        for i in range(3):
            self._draw_star(screen, col1_x + 25 + i*35, sy, 14, i < stars, star_col)
        ly += 38

        ly = self._line(screen, f"Accuracy:            {accuracy:.0f}%", ly, (190, 230, 190), indent=col1_x + 12)
        ly = self._line(screen, f"Joint Angle:         {angle:.1f}°", ly, grade_col, indent=col1_x + 12)
        ly = self._line(screen, f"ROM Grade:           {grade_str}", ly, grade_col, indent=col1_x + 12)
        ly = self._line(screen, f"Movement Quality:    {mq:.1f}%", ly, (0, 200, 255), indent=col1_x + 12)

        ly += 12
        ly = self._section_bar(screen, "DAILY EXERCISES", col1_x, ly, col_w, (120, 75, 0))
        for i, (ex, dose, freq) in enumerate(exs[:3]):
            ly = self._line(screen, f"{i+1}. {ex}", ly, (200, 220, 240), indent=col1_x + 8)
            ly = self._line(screen, f"   {dose} | {freq}", ly, (130, 150, 175), indent=col1_x + 18)
            ly += 3

        # --- RIGHT: ANALYTICS ---
        ry = y
        ry = self._section_bar(screen, "RECOVERY VISUALIZATION", col2_x, ry, col_w, (60, 35, 130))

        if self.session_chart:
            scaled_chart = pygame.transform.smoothscale(self.session_chart, (col_w - 10, 170))
            screen.blit(scaled_chart, (col2_x + 5, ry + 5))
            ry += 185
        else:
            ry += 40

        ry = self._section_bar(screen, "FLEXIBILITY PROGRESS", col2_x, ry, col_w, (0, 110, 140))
        bar_x = col2_x + 10
        bar_w = col_w - 20
        ry += 8
        pygame.draw.rect(screen, (25, 35, 55), pygame.Rect(bar_x, ry, bar_w, 20), border_radius=5)
        fill = int(bar_w * min(angle / self.ROM_NORMAL, 1.0))
        if fill > 0:
            pygame.draw.rect(screen, grade_col, pygame.Rect(bar_x, ry, fill, 20), border_radius=5)
        # ROM percentage text on bar
        rom_pct_txt = self.font_label.render(f"{min(angle / self.ROM_NORMAL * 100, 100):.0f}%", True, (255, 255, 255))
        screen.blit(rom_pct_txt, (bar_x + bar_w // 2 - rom_pct_txt.get_width() // 2, ry + 3))
        ry += 32

        # ── AI CLINICAL SUMMARY PANEL ─────────────────────────────────
        by = max(ly, ry) + 6
        bh = WINDOW_HEIGHT - by - 50
        bw = GAME_AREA_WIDTH - 44
        panel_rect = pygame.Rect(22, by, bw, bh)
        pygame.draw.rect(screen, (12, 22, 48), panel_rect, border_radius=10)
        pygame.draw.rect(screen, (0, 130, 170), panel_rect, 1, border_radius=10)

        # Accent stripe
        pygame.draw.rect(screen, (0, 160, 200), pygame.Rect(22, by, 4, bh), border_radius=2)

        # Heading
        h_surf = self.font_small.render("AI CLINICAL SUMMARY & RECOMMENDATION", True, (0, 200, 245))
        screen.blit(h_surf, (38, by + 10))

        # Wrap summary text
        words = summary_text.split()
        lines = []
        line = ""
        for w in words:
            test = line + w + " "
            if len(test) > 110:
                lines.append(line.strip())
                line = w + " "
            else:
                line = test
        if line:
            lines.append(line.strip())

        sy = by + 34
        for ln in lines[:3]:
            s_surf = self.font_tiny.render(ln, True, (185, 200, 220))
            screen.blit(s_surf, (38, sy))
            sy += 18

        # Recommendation
        sy += 4
        rec_title = self.font_small.render("RECOMMENDED THERAPY PROTOCOL:", True, (50, 210, 120))
        screen.blit(rec_title, (38, sy))

        r_surf = self.font_tiny.render(ai_recommendation, True, (240, 245, 255))
        screen.blit(r_surf, (38, sy + 22))

        # ── FOOTER ────────────────────────────────────────────────────
        footer_rect = pygame.Rect(0, WINDOW_HEIGHT - 40, GAME_AREA_WIDTH, 40)
        pygame.draw.rect(screen, (6, 10, 20), footer_rect)
        nav_txt = "Hold FIST 2s → Return to Menu  |  Clinical data saved to database"
        nav_surf = self.font_tiny.render(nav_txt, True, (80, 110, 145))
        screen.blit(nav_surf, nav_surf.get_rect(center=(cx, WINDOW_HEIGHT - 20)))

    # ------------------------------------------------------------------
    def _clinical_suggestions(self, level: int, accuracy: float,
                               angle: float, extension: float) -> list:
        """Generate evidence-based physiotherapy suggestions per level"""
        tips = []

        if level == 1:  # Flexibility / Reach
            if extension < 150:
                tips.append("🔹 Wrist extension is limited. Try wrist flexion/extension stretches 10 reps x 3 sets daily.")
            if angle < self.ROM_GOOD:
                tips.append("🔹 Finger ROM is below target. Practice full fist → open hand cycles, 15 reps x 4 sets.")
            if accuracy < 70:
                tips.append("🔹 Accuracy low — focus on slow, deliberate reach movements before increasing speed.")
            if accuracy >= 80:
                tips.append("✅ Excellent reach! Progress to Level 2 to build grip strength.")
            tips.append("📋 Clinical goal: Achieve full MCP flexion (90°) and extension (0°).")

        elif level == 2:  # Strength / Grip
            if accuracy < 60:
                tips.append("🔹 Catching accuracy low. Practice wrist pronation/supination: 10 reps x 3 sets.")
            if accuracy >= 75:
                tips.append("✅ Good grip control! Try Level 3 for fine motor precision.")
            tips.append("🔹 Squeeze a soft therapy ball 10 seconds on, 5 seconds off — 10 reps daily.")
            tips.append("📋 Clinical goal: Maintain palm-level control with 75%+ catch rate.")

        elif level == 3:  # Fine Motor / Pinch
            if accuracy < 60:
                tips.append("🔹 Pinch accuracy low. Practice thumb opposition: touch thumb to each fingertip, 10 reps.")
            if accuracy >= 75:
                tips.append("✅ Excellent fine motor control! Consider increasing session duration.")
            tips.append("🔹 Pinch small objects (coins, pegs) for 5 min daily to build lateral pinch strength.")
            tips.append("📋 Clinical goal: Achieve consistent pinch-and-release with 80%+ accuracy.")

        elif level == 4:  # Coordination / Tracing
            if accuracy < 60:
                tips.append("🔹 Target tracking is unstable. Practice tracing shapes on a table for wrist support.")
            if accuracy >= 75:
                tips.append("✅ Excellent smoothness and tremor control!")
            tips.append("🔹 Draw large figure-8s on paper 2 mins daily to improve shoulder-wrist coordination.")
            tips.append("📋 Clinical goal: Maintain continuous pursuit with minimal hand shaking.")

        elif level == 5:  # Spasticity Pump
            if accuracy < 50:
                tips.append("🔹 Struggling to open hand fully. Perform manual finger stretches before playing.")
            if accuracy >= 80:
                tips.append("✅ Great extension and rapid release!")
            tips.append("🔹 Practice making a tight fist and exploding the hand open 15 times, 3x daily.")
            tips.append("📋 Clinical goal: Rapidly overcome spasticity and achieve full finger extension.")

        elif level == 6:  # Memory Sequence
            if accuracy < 60:
                tips.append("🔹 Sequencing errors detected. Practice repeating simple 3-step physical tasks.")
            if accuracy >= 80:
                tips.append("✅ Outstanding cognitive recall and motor execution!")
            tips.append("🔹 Play memory card games while reaching to place the cards, combining thought and action.")
            tips.append("📋 Clinical goal: Connect cognitive intent directly to precise motor movement without hesitation.")

        if not tips:
            tips.append("✅ Great session! Maintain daily practice for best results.")
        return tips[:4]  # max 4 tips

    def _next_level_rec(self, level: int, accuracy: float) -> str:
        if accuracy >= 75:
            if level < 3:
                return f"🚀 RECOMMENDED NEXT: Level {level + 1} — you're ready!"
            return "🏆 All levels complete! Increase session duration or repeat for maintenance."
        return f"🔄 REPEAT Level {level} — aim for 75%+ accuracy before progressing."
