"""
Sound System for the Zero-Keyboard AI Physiotherapy System.
Generates all sounds programmatically — no external audio files needed.
"""

import math
import pygame


class SoundSystem:
    """Lightweight sound effects using Pygame mixer"""
    
    def __init__(self):
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.enabled = True
            self._generate_sounds()
        except Exception as e:
            print(f"Sound disabled: {e}")

    def _generate_sounds(self):
        """Generate sounds programmatically (no external files needed)"""
        import array
        sample_rate = 22050
        # ── Improved sounds ─────────────────────────────────────────
        # Pop sound (short high-frequency burst)
        duration = 0.08
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            t = i / sample_rate
            envelope = max(0, 1.0 - t / duration)
            buf[i] = int(16000 * envelope * math.sin(2 * math.pi * 880 * t))
        self.pop = pygame.mixer.Sound(buffer=buf)
        self.pop.set_volume(0.3)

        # Catch sound (descending tone)
        duration = 0.12
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            t = i / sample_rate
            freq = 660 - 200 * t / duration
            envelope = max(0, 1.0 - t / duration)
            buf[i] = int(14000 * envelope * math.sin(2 * math.pi * freq * t))
        self.catch = pygame.mixer.Sound(buffer=buf)
        self.catch.set_volume(0.25)

        # Level complete — triumphant ascending fanfare (C-E-G-C chord)
        duration = 0.8
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        freqs = [261, 329, 392, 523]  # C4 E4 G4 C5
        for i in range(n):
            t = i / sample_rate
            envelope = max(0, 1.0 - t / duration) ** 0.5
            wave = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
            buf[i] = int(11000 * envelope * wave)
        self.level_complete = pygame.mixer.Sound(buffer=buf)
        self.level_complete.set_volume(0.4)

        # Combo milestone chime (high ping)
        duration = 0.18
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            t = i / sample_rate
            envelope = max(0, 1.0 - t / duration) ** 0.7
            buf[i] = int(13000 * envelope * math.sin(2 * math.pi * 1320 * t))
        self.combo = pygame.mixer.Sound(buffer=buf)
        self.combo.set_volume(0.2)

        # Countdown beep (neutral mid tone)
        duration = 0.07
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            t = i / sample_rate
            envelope = max(0, 1.0 - t / duration)
            buf[i] = int(10000 * envelope * math.sin(2 * math.pi * 600 * t))
        self.beep = pygame.mixer.Sound(buffer=buf)
        self.beep.set_volume(0.18)

        # Select sound (click)
        duration = 0.05
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        for i in range(n):
            t = i / sample_rate
            envelope = max(0, 1.0 - t / duration)
            buf[i] = int(10000 * envelope * math.sin(2 * math.pi * 1200 * t))
        self.select = pygame.mixer.Sound(buffer=buf)
        self.select.set_volume(0.2)

        # Background Drone (Looping Pad)
        duration = 1.0
        n = int(sample_rate * duration)
        buf = array.array('h', [0] * n)
        freqs = [130.81, 196.00, 261.63]  # C3, G3, C4
        for i in range(n):
            t = i / sample_rate
            wave = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
            lfo = 0.5 + 0.5 * math.sin(2 * math.pi * 0.5 * t)
            buf[i] = int(2500 * wave * lfo)
        self.bg_drone = pygame.mixer.Sound(buffer=buf)
        self.bg_drone.set_volume(0.12)
        if self.enabled:
            self.bg_drone.play(loops=-1)
    
    def play(self, sound_name: str):
        if not self.enabled:
            return
        sound = getattr(self, sound_name, None)
        if sound:
            sound.play()
