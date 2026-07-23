"""
Particle System and Score Popups for the Zero-Keyboard AI Physiotherapy System.
"""

import random
import pygame
from typing import List

from physio.constants import COLOR_WARNING


class Particle:
    """Single particle for visual effects"""
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.vx = random.uniform(-4, 4)
        self.vy = random.uniform(-6, -1)
        self.life = 1.0
        self.decay = random.uniform(0.02, 0.05)
        self.radius = random.randint(3, 8)
        self.color = color
    
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15  # gravity
        self.life -= self.decay
        return self.life > 0
    
    def draw(self, screen):
        r = max(1, int(self.radius * self.life))
        # Direct draw without alpha surface for performance
        fade = max(0.2, self.life)
        color = (int(self.color[0] * fade), int(self.color[1] * fade), int(self.color[2] * fade))
        pygame.draw.circle(screen, color, (int(self.x), int(self.y)), r)


class ParticleSystem:
    """Manages particle effects"""
    def __init__(self):
        self.particles: List[Particle] = []
    
    def emit(self, x, y, color, count=12):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))
    
    def update(self):
        self.particles = [p for p in self.particles if p.update()]
    
    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)


# Module-level popup font — never allocate inside ScorePopup.__init__
_POPUP_FONT = None
def _popup_font():
    global _POPUP_FONT
    if _POPUP_FONT is None:
        _POPUP_FONT = pygame.font.SysFont("segoeui", 36)
    return _POPUP_FONT


class ScorePopup:
    """Floating score text animation"""
    def __init__(self, x, y, text, color=COLOR_WARNING):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.life = 1.0

    def update(self):
        self.y -= 1.5
        self.life -= 0.025
        return self.life > 0

    def draw(self, screen):
        alpha = max(0, int(255 * self.life))
        text_surf = _popup_font().render(self.text, True, self.color)
        text_surf.set_alpha(alpha)
        screen.blit(text_surf, (int(self.x), int(self.y)))
