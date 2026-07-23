"""
UI Widget Components for the Zero-Keyboard AI Physiotherapy System.
SelectionRing, LevelButton, HomeIcon, CloseButton, Button, and font caching.
"""

import math
import time
import pygame
from typing import Optional, Tuple

from physio.constants import (
    HOVER_DURATION, COLOR_TEXT, COLOR_SECONDARY, COLOR_WARNING
)
from physio.utils import distance


# Module-level cached fonts for UI components (avoids per-frame allocation)
_FONT_CD   = None
_FONT_SEL  = None
_FONT_HINT = None
_FONT_BADGE = None

def _get_ui_fonts():
    global _FONT_CD, _FONT_SEL, _FONT_HINT, _FONT_BADGE
    if _FONT_CD is None:
        _FONT_CD   = pygame.font.SysFont("segoeui", 32)
        _FONT_SEL  = pygame.font.SysFont("segoeui", 20)
        _FONT_HINT = pygame.font.SysFont("segoeui", 18)
        _FONT_BADGE = pygame.font.SysFont("segoeui", 24)
    return _FONT_CD, _FONT_SEL, _FONT_HINT, _FONT_BADGE


class SelectionRing:
    """Circular progress indicator for hover-click — highly visible version"""

    def __init__(self, x, y, radius, duration=HOVER_DURATION):
        self.x = x
        self.y = y
        self.radius = radius
        self.duration = duration
        self.hover_start = None

    def update(self, cursor_pos: Optional[Tuple[int, int]]) -> bool:
        """Returns True when selection is complete (gesture or mouse)"""
        # Mouse support
        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]
        
        # Check if mouse is clicking this ring
        if distance(m_pos, (self.x, self.y)) < self.radius:
            if m_clicked:
                self.hover_start = None
                return True

        if cursor_pos is None:
            self.hover_start = None
            return False

        dist = distance(cursor_pos, (self.x, self.y))

        if dist < self.radius:
            if self.hover_start is None:
                self.hover_start = time.time()
            elapsed = time.time() - self.hover_start
            if elapsed >= self.duration:
                self.hover_start = None
                return True
        else:
            self.hover_start = None

        return False

    def draw(self, screen):
        """Draw a highly visible selection ring with glow, arc, and countdown"""
        font_cd, font_sel, font_hint, _ = _get_ui_fonts()
        is_active = self.hover_start is not None
        progress = 0.0
        if is_active:
            elapsed = time.time() - self.hover_start
            progress = min(elapsed / self.duration, 1.0)

        t = time.time()

        # --- Outer pulsing ring (always visible) ---
        pulse = int(3 * math.sin(t * 4))
        outer_color = (0, 200, 255) if not is_active else (50, 255, 150)
        pygame.draw.circle(screen, outer_color,
                           (self.x, self.y), self.radius + 6 + pulse, 2)

        # --- Glowing filled background when hovering ---
        if is_active:
            glow_surf = pygame.Surface((self.radius * 2 + 20, self.radius * 2 + 20),
                                       pygame.SRCALPHA)
            glow_r = self.radius + 10
            pygame.draw.circle(glow_surf, (50, 255, 150, 40),
                               (glow_r, glow_r), glow_r)
            screen.blit(glow_surf, (self.x - glow_r, self.y - glow_r))

        # --- Base ring ---
        base_color = (50, 255, 150) if is_active else (0, 180, 220)
        pygame.draw.circle(screen, base_color, (self.x, self.y), self.radius, 4)

        # --- Thick progress arc ---
        if is_active and progress > 0.01:
            start_a = math.radians(-90)
            end_a   = math.radians(-90 + 360 * progress)
            for thickness in [10, 8, 6]:
                arc_surf = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
                pygame.draw.arc(arc_surf, (50, 255, 150, 220),
                                (0, 0, self.radius * 2, self.radius * 2),
                                start_a, end_a, thickness)
                screen.blit(arc_surf, (self.x - self.radius, self.y - self.radius))

            remaining = self.duration - (time.time() - self.hover_start)
            cd_text = font_cd.render(f"{remaining:.1f}s", True, (255, 255, 255))
            screen.blit(cd_text, cd_text.get_rect(center=(self.x, self.y - 8)))
            sel_text = font_sel.render("SELECTING", True, (180, 255, 200))
            screen.blit(sel_text, sel_text.get_rect(center=(self.x, self.y + 12)))
        else:
            hint = font_hint.render("HOVER", True, (120, 180, 200))
            screen.blit(hint, hint.get_rect(center=(self.x, self.y)))


class LevelButton:
    """Level selection button — polished card style"""

    def __init__(self, x, y, width, height, text, level_num, ring_radius=55):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.level_num = level_num
        
        # Calculate dynamic selection ring radius and center to place on the right side.
        # Cap the radius at a safe fraction of button height to ensure it fits perfectly.
        ring_r = min(ring_radius, (height - 16) // 2)
        ring_x = x + width - ring_r - 20
        ring_y = y + height // 2
        self.ring = SelectionRing(ring_x, ring_y, ring_r)

    def update(self, cursor_pos: Optional[Tuple[int, int]]) -> bool:
        """Hover detection based on full card bounding box instead of just the ring center.
        Makes interaction significantly easier and more intuitive for rehab patients.
        """
        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]
        
        # Physical mouse support: triggers immediately on click! Mouse hover does NOT trigger the hover selection ring.
        if self.rect.collidepoint(m_pos) and m_clicked:
            self.ring.hover_start = None
            return True
            
        # Hands-free hand tracking support: hover to select.
        is_hovered = False
        if cursor_pos is not None and self.rect.collidepoint(cursor_pos):
            is_hovered = True
            
        if is_hovered:
            if self.ring.hover_start is None:
                self.ring.hover_start = time.time()
            elapsed = time.time() - self.ring.hover_start
            if elapsed >= self.ring.duration:
                self.ring.hover_start = None
                return True
        else:
            self.ring.hover_start = None
            
        return False

    def draw(self, screen, font, base_col=None, hov_col=None):
        _, _, _, font_badge = _get_ui_fonts()
        is_hovering = self.ring.hover_start is not None
        progress = 0.0
        if is_hovering:
            elapsed = time.time() - self.ring.hover_start
            progress = min(elapsed / self.ring.duration, 1.0)

        # Default colors
        default_base = (30, 32, 55)
        default_hov = (55, 60, 95)
        
        # Override if custom colors provided
        current_bg = default_base if not base_col else base_col
        current_hover = default_hov if not hov_col else hov_col
        
        bg_color = current_hover if is_hovering else current_bg
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=12)
        border_color = (50, 255, 150) if is_hovering else (0, 180, 220)
        pygame.draw.rect(screen, border_color, self.rect, 3 if is_hovering else 2, border_radius=12)

        # Badge: compact and vertically centered
        badge_size = 28 if self.rect.height > 60 else 24
        badge_y = self.rect.centery - badge_size // 2
        badge_rect = pygame.Rect(self.rect.x + 10, badge_y, badge_size, badge_size)
        badge_color = (50, 255, 150) if is_hovering else (0, 150, 200)
        pygame.draw.rect(screen, badge_color, badge_rect, border_radius=7)
        badge_text = font_badge.render(str(self.level_num), True, (0, 0, 0))
        screen.blit(badge_text, badge_text.get_rect(center=badge_rect.center))

        text_color = (255, 255, 255) if is_hovering else (200, 210, 230)
        
        # Split text by newlines for multiline age group cards
        lines = [line.strip() for line in self.text.split('\n') if line.strip()]
        text_left = self.rect.x + 10 + badge_size + 10
        text_right = self.ring.x - self.ring.radius - 10
        center_x = (text_left + text_right) // 2
        
        if len(lines) > 1:
            line_heights = [font.size(line)[1] for line in lines]
            total_h = sum(line_heights) + (len(lines) - 1) * 4
            start_y = self.rect.centery - total_h // 2
            
            for line in lines:
                surf = font.render(line, True, text_color)
                rect = surf.get_rect(center=(center_x, start_y + surf.get_height() // 2))
                screen.blit(surf, rect)
                start_y += surf.get_height() + 4
        else:
            # Single line buttons (e.g. level button or bottom utility button)
            text_surf = font.render(self.text, True, text_color)
            screen.blit(text_surf, text_surf.get_rect(midleft=(text_left, self.rect.centery)))

        bar_h = 4
        bar_rect = pygame.Rect(self.rect.x + 10, self.rect.bottom - bar_h - 6,
                               self.rect.width - 20, bar_h)
        pygame.draw.rect(screen, (40, 45, 70), bar_rect, border_radius=2)
        if progress > 0:
            fill_rect = pygame.Rect(bar_rect.x, bar_rect.y,
                                    int(bar_rect.width * progress), bar_h)
            pygame.draw.rect(screen, (50, 255, 150), fill_rect, border_radius=2)

        self.ring.draw(screen)


class HomeIcon:
    """Fist-hold + Hover-click pause/quit icon - SUPER ACCESSIBLE REDESIGN"""
    
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.duration = HOVER_DURATION
        self.ring = SelectionRing(x + 30, y + height // 2, 18, duration=self.duration)
        self.font = pygame.font.SysFont("segoeui", 20, bold=True)
        
    def update(self, is_fist: bool, cursor_pos: Optional[Tuple[int, int]]) -> bool:
        """Returns True when hover or fist hold is complete"""
        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]
        
        is_hovered = False
        if self.rect.collidepoint(m_pos):
            is_hovered = True
            if m_clicked:
                self.ring.hover_start = None
                return True
                
        if cursor_pos is not None and self.rect.collidepoint(cursor_pos):
            is_hovered = True
            
        if is_fist:
            is_hovered = True
            
        if is_hovered:
            if self.ring.hover_start is None:
                self.ring.hover_start = time.time()
            elapsed = time.time() - self.ring.hover_start
            if elapsed >= self.ring.duration:
                self.ring.hover_start = None
                return True
        else:
            self.ring.hover_start = None
            
        return False
        
    def draw(self, screen):
        """Draw highly visible elegant card button"""
        is_hovering = self.ring.hover_start is not None
        
        # Color palettes
        bg_col = (45, 25, 35) if is_hovering else (20, 22, 35)
        border_col = (255, 60, 100) if is_hovering else (0, 180, 220)
        text_col = (255, 255, 255) if is_hovering else (200, 220, 240)
        
        # Draw capsule
        pygame.draw.rect(screen, bg_col, self.rect, border_radius=15)
        pygame.draw.rect(screen, border_col, self.rect, 3 if is_hovering else 2, border_radius=15)
        
        # Text (emojis stripped to prevent ▢ rendering box)
        txt = self.font.render("MAIN MENU", True, text_col)
        screen.blit(txt, txt.get_rect(center=(self.rect.centerx + 20, self.rect.centery)))
        
        # Draw the SelectionRing inside the capsule
        self.ring.draw(screen)


class CloseButton:
    """Close button with 3-second hover to exit"""
    
    def __init__(self, x, y, width, height):
        self.rect = pygame.Rect(x, y, width, height)
        self.hover_start = None
        self.duration = 3.0
        
    def update(self, cursor_pos: Optional[Tuple[int, int]]) -> bool:
        """Returns True when hover or click is complete"""
        # Mouse support
        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]
        if self.rect.collidepoint(m_pos) and m_clicked:
            self.hover_start = None
            return True

        if cursor_pos is None:
            self.hover_start = None
            return False
        
        if self.rect.collidepoint(cursor_pos):
            if self.hover_start is None:
                self.hover_start = time.time()
            
            elapsed = time.time() - self.hover_start
            if elapsed >= self.duration:
                return True
        else:
            self.hover_start = None
        
        return False
    
    def draw(self, screen, font, text="CLOSE", base_col=(60, 40, 40), hov_col=(100, 50, 50), border_col=None):
        """Draw button with custom text and colors"""
        is_hovering = self.hover_start is not None
        color = hov_col if is_hovering else base_col
        current_border = border_col if border_col else COLOR_SECONDARY
        
        pygame.draw.rect(screen, color, self.rect, border_radius=10)
        pygame.draw.rect(screen, current_border, self.rect, 3, border_radius=10)
        
        # Text
        text_surf = font.render(text, True, COLOR_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
        
        # Progress bar
        if is_hovering:
            elapsed = time.time() - self.hover_start
            progress = min(elapsed / self.duration, 1.0)
            
            bar_width = self.rect.width - 20
            bar_height = 8
            bar_x = self.rect.x + 10
            bar_y = self.rect.bottom - 15
            
            pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=4)
            filled = int(bar_width * progress)
            if filled > 0:
                pygame.draw.rect(screen, current_border, (bar_x, bar_y, filled, bar_height), border_radius=4)
            
            # Percentage — use cached font
            _, _, font_hint, _ = _get_ui_fonts()
            percent_text = font_hint.render(f"{int(progress * 100)}%", True, COLOR_WARNING)
            percent_rect = percent_text.get_rect(center=(self.rect.centerx, self.rect.centery - 20))
            screen.blit(percent_text, percent_rect)


class Button:
    """Generic hover-to-activate button"""
    def __init__(self, x, y, width, height, text, color=(60, 60, 80)):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_start = None
        self.duration = 1.5

    def update(self, cursor_pos: Optional[Tuple[int, int]]) -> bool:
        # Mouse support
        m_pos = pygame.mouse.get_pos()
        m_clicked = pygame.mouse.get_pressed()[0]
        if self.rect.collidepoint(m_pos) and m_clicked:
            self.hover_start = None
            return True

        if cursor_pos is None:
            self.hover_start = None
            return False
        if self.rect.collidepoint(cursor_pos):
            if self.hover_start is None:
                self.hover_start = time.time()
            if time.time() - self.hover_start >= self.duration:
                self.hover_start = None
                return True
        else:
            self.hover_start = None
        return False

    def draw(self, screen, font, text=None, base_col=None, hov_col=None):
        is_hovering = self.hover_start is not None
        
        # Use provided colors or fallback to default
        active_col = base_col if base_col else self.color
        if is_hovering and hov_col:
            active_col = hov_col
            
        # Base color with hover brightening
        base_r = min(255, active_col[0] + (30 if is_hovering and not hov_col else 0))
        base_g = min(255, active_col[1] + (30 if is_hovering and not hov_col else 0))
        base_b = min(255, active_col[2] + (30 if is_hovering and not hov_col else 0))
        col = (base_r, base_g, base_b)
        
        # Inner fill (Dark transparent style)
        pygame.draw.rect(screen, col, self.rect, border_radius=12)
        
        # Neon Border
        border_col = (0, 255, 200) if is_hovering else (0, 150, 150)
        pygame.draw.rect(screen, border_col, self.rect, 2, border_radius=12)
        
        # Subtle 3D top highlight (we use a solid color since screen has no alpha channel)
        highlight = (min(255, col[0]+50), min(255, col[1]+50), min(255, col[2]+50))
        pygame.draw.line(screen, highlight, (self.rect.left+12, self.rect.top+2), (self.rect.right-12, self.rect.top+2), 2)
        
        # Text
        display_text = text if text else self.text
        
        # Drop shadow for text
        shadow = font.render(display_text, True, (0, 0, 0))
        screen.blit(shadow, shadow.get_rect(center=(self.rect.centerx + 2, self.rect.centery + 2)))
        
        # Main text
        ts = font.render(display_text, True, (255, 255, 255))
        screen.blit(ts, ts.get_rect(center=self.rect.center))
        
        # Loading bar when hovering
        if is_hovering:
            prog = min((time.time() - self.hover_start) / self.duration, 1.0)
            bar_w = int((self.rect.width - 20) * prog)
            pygame.draw.rect(screen, (50, 255, 150), (self.rect.x + 10, self.rect.bottom - 10, bar_w, 6), border_radius=3)
