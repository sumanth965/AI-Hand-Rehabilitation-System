"""
Zero-Keyboard AI Physiotherapy System
Complete hand control with split-screen medical sidebar
"""

import cv2
import mediapipe as mp
import pygame
import numpy as np
import sqlite3
import threading
import time
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List
from collections import deque
from datetime import datetime
import os
import io
import pyttsx3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
except ImportError:
    pass

# ============================================================================
# VOICE ENGINE
# ============================================================================

class VoiceEngine:
    def __init__(self):
        try:
            self.engine = pyttsx3.init()
            self.lock = threading.Lock()
            self.is_speaking = False
            self.enabled = True
            self.last_speech = 0.0
        except Exception as e:
            print(f"Voice init failed: {e}")
            self.enabled = False
            
    def speak(self, text):
        if not self.enabled: return
        with self.lock:
            # Buffer voice feedback to speak only once every 3 seconds
            if not self.is_speaking and (time.time() - self.last_speech >= 3.0):
                self.is_speaking = True
                self.last_speech = time.time()
                threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()
                
    def _speak_thread(self, text):
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except:
            pass
        finally:
            with self.lock:
                self.is_speaking = False

VOICE = VoiceEngine()

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
GAME_AREA_WIDTH = int(WINDOW_WIDTH * 0.75)  # 960px
SIDEBAR_WIDTH = WINDOW_WIDTH - GAME_AREA_WIDTH  # 320px
FPS = 60

# Colors
COLOR_BG = (15, 15, 25)
COLOR_SIDEBAR_BG = (236, 243, 249)
COLOR_PRIMARY = (0, 200, 255)
COLOR_SECONDARY = (255, 100, 150)
COLOR_SUCCESS = (50, 255, 150)
COLOR_WARNING = (255, 200, 50)
COLOR_DANGER = (204, 64, 74)
COLOR_TEXT = (240, 240, 240)
COLOR_ACCENT = (138, 43, 226)  # Purple
COLOR_BUBBLE = (100, 200, 255)
COLOR_SEED = (139, 69, 19)  # Brown
COLOR_POT = (34, 139, 34)  # Green

# Phase 2 medical interface palette
COLOR_MED_TEXT = (28, 39, 53)
COLOR_MED_MUTED = (102, 119, 138)
COLOR_MED_PANEL = (255, 255, 255)
COLOR_MED_PRIMARY = (0, 119, 182)
COLOR_MED_SUCCESS = (29, 163, 101)
COLOR_MED_WARNING = (220, 143, 20)

LEVEL_DISPLAY_NAMES = {
    1: "Flexibility Training",
    2: "Strength Coordination",
    3: "Fine Motor Pinch",
    4: "Path Tracing Control",
    5: "Grip Release Cycle",
    6: "Cognitive Finger Taps",
}

# Game Settings
HOVER_DURATION = 1.5
FIST_HOLD_DURATION = 2.0
SMOOTHING_WINDOW = 12  # Increased for much smoother aim/tracking
LEVEL_DURATION = 30  # seconds for timed levels

# Age-Based Themes
AGE_THEMES = {
    "child": {
        "name": "Magic Garden",
        "bg_color": (25, 35, 50),
        "primary_color": (255, 150, 200),  # Pink
        "secondary_color": (150, 255, 150),  # Light green
        "accent_color": (255, 200, 100),  # Yellow
        "level1_name": "Butterfly Catch",
        "level2_name": "Flower Watering",
        "level3_name": "Seed Planting",
        "level4_name": "Magic Trace",
        "level5_name": "Balloon Pump",
        "level6_name": "Simon Says",
        "level1_icon": "🦋",
        "level2_icon": "🌻",
        "level3_icon": "🌱",
        "level4_icon": "✨",
        "level5_icon": "🎈",
        "level6_icon": "🧠",
        "speed_multiplier": 0.7,  # Slower
        "size_multiplier": 1.3,   # Bigger targets
    },
    "young": {
        "name": "Cyber Arena",
        "bg_color": (10, 10, 20),
        "primary_color": (0, 255, 255),  # Cyan
        "secondary_color": (255, 0, 255),  # Magenta
        "accent_color": (255, 255, 0),  # Yellow
        "level1_name": "Speed Strike",
        "level2_name": "Precision Catch",
        "level3_name": "Quantum Grab",
        "level4_name": "Neon Path",
        "level5_name": "Power Core",
        "level6_name": "Pattern Logic",
        "level1_icon": "⚡",
        "level2_icon": "🎯",
        "level3_icon": "🔮",
        "level4_icon": "⚡",
        "level5_icon": "🔋",
        "level6_icon": "🧩",
        "speed_multiplier": 1.3,  # Faster
        "size_multiplier": 0.9,   # Smaller targets
    },
    "adult": {
        "name": "Zen Garden",
        "bg_color": (20, 25, 20),
        "primary_color": (100, 200, 150),  # Sage green
        "secondary_color": (150, 180, 200),  # Soft blue
        "accent_color": (200, 180, 150),  # Beige
        "level1_name": "Leaf Collection",
        "level2_name": "Water Flow",
        "level3_name": "Stone Arrangement",
        "level4_name": "Zen Flow",
        "level5_name": "Bellows Breath",
        "level6_name": "Memory Path",
        "level1_icon": "🍃",
        "level2_icon": "💧",
        "level3_icon": "🪨",
        "level4_icon": "〰️",
        "level5_icon": "🌬️",
        "level6_icon": "👣",
        "speed_multiplier": 1.0,  # Normal
        "size_multiplier": 1.1,   # Slightly bigger
    },
    "senior": {
        "name": "Memory Lane",
        "bg_color": (30, 25, 20),
        "primary_color": (200, 150, 100),  # Warm orange
        "secondary_color": (150, 200, 150),  # Soft green
        "accent_color": (200, 180, 200),  # Lavender
        "level1_name": "Gentle Blooms",
        "level2_name": "Musical Catch",
        "level3_name": "Pattern Match",
        "level4_name": "Smooth Line",
        "level5_name": "Heartbeat",
        "level6_name": "Recall Game",
        "level1_icon": "🌺",
        "level2_icon": "🎵",
        "level3_icon": "🧩",
        "level4_icon": "🖌️",
        "level5_icon": "❤️",
        "level6_icon": "🧠",
        "speed_multiplier": 0.8,  # Slower
        "size_multiplier": 1.2,   # Bigger targets
    }
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two points"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation"""
    return a + (b - a) * t

# ============================================================================
# DATABASE & DATA MODELS
# ============================================================================

# ============================================================================
# SOUND SYSTEM
# ============================================================================

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

# ============================================================================
# PARTICLE SYSTEM
# ============================================================================

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

# ============================================================================
# SCORE POPUP
# ============================================================================

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

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def weighted_average(values: deque) -> float:
    """Calculate weighted average (recent values weighted more)"""
    if not values:
        return 0
    weights = np.linspace(0.5, 1.0, len(values))
    return np.average(list(values), weights=weights)

def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class GameState(Enum):
    PATIENT_REGISTRATION = -2
    AGE_SELECT = -1
    MAIN_MENU = 0
    LEVEL_SELECT = 1
    SETTINGS = 2
    PROGRESS = 3
    PAIN_SCALE = 4       # ← NEW: pain 0-10 before session
    HISTORY = 5          # ← NEW: full session history screen
    LEVEL1_FLEXIBILITY = 10
    LEVEL2_STRENGTH = 11
    LEVEL3_FINEMOTOR = 12
    LEVEL4_COORDINATION = 13
    LEVEL5_GRIP_RELEASE = 14
    LEVEL6_FINGER_TAPS = 15
    PAUSED = 20
    LEVEL_COMPLETE = 22
    RESULTS = 21
    CLOUD_SYNC = 23
    THERAPIST_DASHBOARD = 24
    CALIBRATION = 25

class AgeGroup(Enum):
    CHILD = "child"          # 5-12 years
    YOUNG_ADULT = "young"    # 18-35 years
    ADULT = "adult"          # 35-60 years
    SENIOR = "senior"        # 60+ years

@dataclass
class HandData:
    """Processed hand tracking data"""
    index_tip: Optional[Tuple[int, int]] = None
    thumb_tip: Optional[Tuple[int, int]] = None
    palm_center: Optional[Tuple[int, int]] = None
    wrist: Optional[Tuple[int, int]] = None
    is_pinching: bool = False
    is_fist: bool = False
    finger_extension: float = 0.0
    knuckle_angles: List[float] = field(default_factory=list)
    landmarks: Optional[list] = None
    hand_label: str = "Unknown"

@dataclass
class Bubble:
    """Bubble object for Level 1"""
    x: float
    y: float
    radius: int
    color: Tuple[int, int, int]
    popped: bool = False
    vx: float = 0  # Velocity for moving bubbles
    vy: float = 0
    is_golden: bool = False  # Golden bubbles worth 3x

@dataclass
class FallingItem:
    """Falling item for Level 2"""
    x: float
    y: float
    radius: int
    speed: float
    color: Tuple[int, int, int]
    is_bomb: bool = False  # Bombs reduce score
    is_powerup: bool = False  # Power-ups give bonuses
    is_shield: bool = False
    is_freeze: bool = False

@dataclass
class Seed:
    """Seed object for Level 3"""
    x: float
    y: float
    radius: int
    speed: float
    grabbed: bool = False
    is_golden: bool = False  # Golden seeds worth 3x

# ============================================================================
# THREADED WEBCAM STREAM
# ============================================================================

class WebcamStream:
    """High-performance non-blocking threaded webcam capture"""
    
    def __init__(self, src=0, width=640, height=480):
        self.src = src
        self.width = width
        self.height = height
        self.stream = None
        self.grabbed = False
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.init_done = False
        self.init_error = False
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return self
    
    def _update(self):
        # Open camera in background thread to prevent blocking Pygame GUI thread
        try:
            self.stream = cv2.VideoCapture(self.src)
            if not self.stream.isOpened():
                raise RuntimeError("Failed to open camera")
            
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.stream.set(cv2.CAP_PROP_FPS, 30)
            self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            grabbed, frame = self.stream.read()
            if grabbed and frame is not None:
                with self.lock:
                    self.grabbed = grabbed
                    self.frame = frame
            self.init_done = True
        except Exception as e:
            print(f"Background camera initialization failed: {e}")
            self.init_error = True
            self.init_done = True
            return
            
        while self.running:
            try:
                grabbed, frame = self.stream.read()
                if grabbed and frame is not None:
                    with self.lock:
                        self.grabbed = grabbed
                        self.frame = frame
            except Exception:
                pass  # Never crash the tracking thread
            time.sleep(0.001)

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return self.grabbed, self.frame.copy()

    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
        if self.stream is not None:
            try:
                self.stream.release()
            except Exception:
                pass

# ============================================================================
# HAND TRACKING ENGINE
# ============================================================================

class HandEngine:
    """Hand tracking with gesture recognition"""
    
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.6
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self.webcam = None
        self.hand_data = HandData()
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Calibration defaults
        self.fist_threshold = 0.12
        self.calibration_active = False
        self.calibrated_max_extension = 170.0
        
        # Smoothing buffers (weighted average)
        self.index_x_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.index_y_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.palm_x_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.palm_y_buffer = deque(maxlen=SMOOTHING_WINDOW)
        
        self.mirrored_frame = None
        
    def start(self):
        try:
            self.webcam = WebcamStream(src=0).start()
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            self.webcam = None
            
        self.running = True
        self.thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self.thread.start()
        
    def _tracking_loop(self):
        while self.running:
            grabbed, frame = self.webcam.read()
            if not grabbed or frame is None:
                continue
            
            # Mirror for natural interaction
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)
            
            # Draw landmarks and process data
            annotated = frame.copy()
            new_hand_data = HandData()
            
            if results.multi_hand_landmarks:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    # Get hand label (Left/Right)
                    label = results.multi_handedness[i].classification[0].label
                    
                    # Process primary hand data to get real-time flex/stretch metrics
                    hand_angle = 180.0
                    temp_hand_data = HandData()
                    if i == 0:
                        new_hand_data = self._process_landmarks(hand_landmarks)
                        new_hand_data.hand_label = label
                        temp_hand_data = new_hand_data
                        if temp_hand_data.knuckle_angles and len(temp_hand_data.knuckle_angles) > 0:
                            hand_angle = temp_hand_data.knuckle_angles[0]
                    else:
                        temp_hand_data = self._process_landmarks(hand_landmarks)
                        if temp_hand_data.knuckle_angles and len(temp_hand_data.knuckle_angles) > 0:
                            hand_angle = temp_hand_data.knuckle_angles[0]
                            
                    # Determine dynamic cyber-medical colors based on stretch quality
                    if hand_angle > 155:
                        bone_col = (0, 255, 200) # Glowing neon cyan for full extension/stretch
                        node_col = (255, 255, 255)
                    elif hand_angle < 110:
                        bone_col = (255, 120, 0) # Glowing amber orange for deep flexion/fist
                        node_col = (255, 200, 100)
                    else:
                        bone_col = (0, 180, 255) # Sleek sci-fi blue for transition range
                        node_col = (200, 220, 255)
                        
                    # Draw thicker neon landmarks for easier webcam visibility from a distance
                    self.mp_draw.draw_landmarks(
                        annotated, hand_landmarks, self.mp_hands.HAND_CONNECTIONS,
                        self.mp_draw.DrawingSpec(color=bone_col, thickness=3, circle_radius=3),
                        self.mp_draw.DrawingSpec(color=node_col, thickness=1)
                    )
            
            with self.lock:
                self.hand_data = new_hand_data
                self.mirrored_frame = annotated
            
            time.sleep(0.001)
    
    def _process_landmarks(self, landmarks) -> HandData:
        """Extract hand data with gesture recognition"""
        # Key landmarks
        wrist = landmarks.landmark[0]
        thumb_tip = landmarks.landmark[4]
        index_tip = landmarks.landmark[8]
        middle_tip = landmarks.landmark[12]
        ring_tip = landmarks.landmark[16]
        pinky_tip = landmarks.landmark[20]
        index_mcp = landmarks.landmark[5]
        middle_mcp = landmarks.landmark[9]
        ring_mcp = landmarks.landmark[13]
        pinky_mcp = landmarks.landmark[17]
        
        # Scale to game area (left 75% of screen)
        raw_index_x = index_tip.x * GAME_AREA_WIDTH
        raw_index_y = index_tip.y * WINDOW_HEIGHT
        
        # Weighted average smoothing
        self.index_x_buffer.append(raw_index_x)
        self.index_y_buffer.append(raw_index_y)
        
        smooth_x = weighted_average(self.index_x_buffer)
        smooth_y = weighted_average(self.index_y_buffer)
        
        # Dynamic Reach Scaling based on Calibration ROM
        if self.calibration_active and self.calibrated_max_extension < 170.0:
            extension_mult = 170.0 / self.calibrated_max_extension
            center_x = GAME_AREA_WIDTH / 2
            center_y = WINDOW_HEIGHT / 2
            
            scaled_offset_x = (smooth_x - center_x) * extension_mult
            scaled_offset_y = (smooth_y - center_y) * extension_mult
            
            smooth_x = np.clip(center_x + scaled_offset_x, 15, GAME_AREA_WIDTH - 15)
            smooth_y = np.clip(center_y + scaled_offset_y, 15, WINDOW_HEIGHT - 15)
            
        index_pos = (int(smooth_x), int(smooth_y))
        thumb_pos = (int(thumb_tip.x * GAME_AREA_WIDTH), int(thumb_tip.y * WINDOW_HEIGHT))
        
        # Palm center
        raw_palm_x = ((wrist.x + middle_mcp.x) / 2) * GAME_AREA_WIDTH
        raw_palm_y = ((wrist.y + middle_mcp.y) / 2) * WINDOW_HEIGHT
        
        self.palm_x_buffer.append(raw_palm_x)
        self.palm_y_buffer.append(raw_palm_y)
        
        palm_center = (int(weighted_average(self.palm_x_buffer)), 
                      int(weighted_average(self.palm_y_buffer)))
        
        wrist_pos = (int(wrist.x * GAME_AREA_WIDTH), int(wrist.y * WINDOW_HEIGHT))
        
        # Pinch detection
        pinch_dist = math.sqrt(
            (thumb_tip.x - index_tip.x)**2 + 
            (thumb_tip.y - index_tip.y)**2
        )
        is_pinching = pinch_dist < 0.07  # Relaxed for easier detection
        
        # Fist detection (all fingertips close to palm)
        avg_finger_y = (index_tip.y + middle_tip.y + ring_tip.y + pinky_tip.y) / 4
        palm_y = (wrist.y + middle_mcp.y) / 2
        is_fist = abs(avg_finger_y - palm_y) < self.fist_threshold
        
        # Finger extension (max reach)
        extension = math.sqrt(
            (index_tip.x - wrist.x)**2 + 
            (index_tip.y - wrist.y)**2
        ) * GAME_AREA_WIDTH
        
        # Calculate knuckle angles
        angles = [
            self._calculate_angle((wrist.x, wrist.y), (index_mcp.x, index_mcp.y), (index_tip.x, index_tip.y)),
            self._calculate_angle((wrist.x, wrist.y), (middle_mcp.x, middle_mcp.y), (middle_tip.x, middle_tip.y)),
            self._calculate_angle((wrist.x, wrist.y), (ring_mcp.x, ring_mcp.y), (ring_tip.x, ring_tip.y)),
            self._calculate_angle((wrist.x, wrist.y), (pinky_mcp.x, pinky_mcp.y), (pinky_tip.x, pinky_tip.y))
        ]
        
        return HandData(
            index_tip=index_pos,
            thumb_tip=thumb_pos,
            palm_center=palm_center,
            wrist=wrist_pos,
            is_pinching=is_pinching,
            is_fist=is_fist,
            finger_extension=extension,
            knuckle_angles=angles,
            landmarks=[landmarks]
        )
    
    def _calculate_angle(self, p1, p2, p3) -> float:
        # Calculate lengths of sides
        a = math.sqrt((p2[0] - p3[0])**2 + (p2[1] - p3[1])**2)
        c = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        b = math.sqrt((p1[0] - p3[0])**2 + (p1[1] - p3[1])**2)
        
        # Prevent division by zero
        if a * c == 0:
            return 0.0
            
        # Law of Cosines formula
        cos_angle = (a**2 + c**2 - b**2) / (2 * a * c)
        
        # Clamp value to [-1, 1] to handle float precision errors
        cos_angle = max(-1.0, min(1.0, cos_angle))
        
        # Calculate angle in radians and convert to degrees
        angle_rad = math.acos(cos_angle)
        return math.degrees(angle_rad)
    
    def get_hand_data(self) -> HandData:
        with self.lock:
            return self.hand_data
    
    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            return self.mirrored_frame.copy() if self.mirrored_frame is not None else None
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        if self.webcam:
            self.webcam.stop()

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class DatabaseManager:
    """Analytics database"""
    
    def __init__(self, db_path="rehab_data.db"):
        self.db_path = db_path
        self.last_session_id = None
        self._init_database()
    
    def _init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT DEFAULT 'Unknown',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    level INTEGER,
                    score INTEGER,
                    duration REAL,
                    avg_accuracy REAL,
                    max_finger_extension REAL,
                    reach_distance REAL,
                    avg_hand_angle REAL DEFAULT 0,
                    pain_level INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    name TEXT PRIMARY KEY,
                    age INTEGER,
                    age_group TEXT,
                    cal_fist_val REAL DEFAULT 0.12,
                    cal_max_ext REAL DEFAULT 170.0,
                    cal_min_ang REAL DEFAULT 15.0,
                    cal_max_ang REAL DEFAULT 90.0,
                    cal_active INTEGER DEFAULT 0,
                    id_number TEXT UNIQUE
                )
            """)
            # Migrations for older DBs
            for col, defn in [("level",          "INTEGER DEFAULT 1"),
                              ("score",          "INTEGER DEFAULT 0"),
                              ("duration",       "REAL DEFAULT 0"),
                              ("avg_accuracy",   "REAL DEFAULT 0"),
                              ("max_finger_extension", "REAL DEFAULT 0"),
                              ("reach_distance", "REAL DEFAULT 0"),
                              ("patient_id",     "TEXT DEFAULT 'Unknown'"),
                              ("avg_hand_angle", "REAL DEFAULT 0"),
                              ("pain_level",     "INTEGER DEFAULT 0")]:
                try:
                    cursor.execute(f"SELECT {col} FROM sessions LIMIT 1")
                except sqlite3.OperationalError:
                    try:
                        cursor.execute(f"ALTER TABLE sessions ADD COLUMN {col} {defn}")
                    except Exception as e:
                        print(f"Migration error for sessions {col}: {e}")
                        
            # Patient migrations
            try:
                cursor.execute(f"SELECT id_number FROM patients LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    cursor.execute(f"ALTER TABLE patients ADD COLUMN id_number TEXT")
                    cursor.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_id_number ON patients(id_number)")
                except Exception as e:
                    print(f"Migration error for patients id_number: {e}")
                    
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"CRITICAL: Database initialization failed: {e}")
            with open("db_error.txt", "a") as f:
                f.write(f"{datetime.now()} - Init Error: {e}\n")

    def save_patient(self, name: str, age: int, age_group: str,
                     cal_fist_val: float = 0.12, cal_max_ext: float = 170.0,
                     cal_min_ang: float = 15.0, cal_max_ang: float = 90.0,
                     cal_active: int = 0, id_number: str = None):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # If id_number is not provided but exists in db, preserve it
            if id_number is None:
                cursor.execute("SELECT id_number FROM patients WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row:
                    id_number = row[0]
                    
            cursor.execute("""
                INSERT OR REPLACE INTO patients 
                (name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active, id_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active, id_number))
            conn.commit()
            conn.close()
            print(f"[SUCCESS] Saved patient profile: {name} (Age {age}, Group {age_group})")
        except Exception as e:
            print(f"Failed to save patient profile: {e}")

    def get_patient(self, name: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active
                FROM patients WHERE name = ?
            """, (name,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    'age': row[0],
                    'age_group': row[1],
                    'cal_fist_val': row[2],
                    'cal_max_ext': row[3],
                    'cal_min_ang': row[4],
                    'cal_max_ang': row[5],
                    'cal_active': row[6]
                }
            return None
        except Exception as e:
            print(f"Failed to get patient: {e}")
            return None

    def get_patient_by_id(self, id_number: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active
                FROM patients WHERE id_number = ?
            """, (id_number,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    'name': row[0],
                    'age': row[1],
                    'age_group': row[2],
                    'cal_fist_val': row[3],
                    'cal_max_ext': row[4],
                    'cal_min_ang': row[5],
                    'cal_max_ang': row[6],
                    'cal_active': row[7]
                }
        except Exception as e:
            print(f"Error fetching patient by ID: {e}")
        return None

    def get_all_patients(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, age, age_group, cal_fist_val, cal_max_ext, cal_min_ang, cal_max_ang, cal_active
                FROM patients ORDER BY name ASC
            """)
            rows = cursor.fetchall()
            conn.close()
            res = []
            for row in rows:
                res.append({
                    'name': row[0],
                    'age': row[1],
                    'age_group': row[2],
                    'cal_fist_val': row[3],
                    'cal_max_ext': row[4],
                    'cal_min_ang': row[5],
                    'cal_max_ang': row[6],
                    'cal_active': row[7]
                })
            return res
        except Exception as e:
            print(f"Failed to get all patients: {e}")
            return []
    
    def save_session(self, level: int, score: int, duration: float,
                    avg_accuracy: float, max_extension: float,
                    reach_distance: float = 0, avg_hand_angle: float = 0,
                    pain_level: int = 0, patient_id: str = "Unknown"):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sessions
                  (patient_id, level, score, duration, avg_accuracy,
                   max_finger_extension, reach_distance, avg_hand_angle, pain_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (patient_id, level, score, duration, avg_accuracy,
                   max_extension, reach_distance, avg_hand_angle, pain_level))
            
            self.last_session_id = cursor.lastrowid
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] Session saved: Level {level}, Score {score}, Accuracy {avg_accuracy:.1f}%")
        except Exception as e:
            import logging
            logging.basicConfig(filename='db_error.txt', level=logging.ERROR, 
                                format='%(asctime)s - Database Error: %(message)s')
            logging.error(f"Failed to save session (locked or missing db): {str(e)}")
            print("Database locked/missing! Logged error to db_error.txt instead of crashing.")
    
    def get_last_session(self):
        """Get the most recent session data"""
        if self.last_session_id is None:
            return None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT level, score, duration, avg_accuracy, max_finger_extension, reach_distance, avg_hand_angle
            FROM sessions
            WHERE id = ?
        """, (self.last_session_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'level': result[0],
                'score': result[1],
                'duration': result[2],
                'avg_accuracy': result[3],
                'max_extension': result[4],
                'reach_distance': result[5],
                'avg_hand_angle': result[6]
            }
        return None
    
    def get_all_time_best(self):
        """Get all-time best performance metrics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(score) FROM sessions")
            best_score = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(avg_accuracy) FROM sessions")
            best_accuracy = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(avg_hand_angle) FROM sessions")
            best_angle = cursor.fetchone()[0] or 0
            cursor.execute("SELECT MAX(max_finger_extension) FROM sessions")
            best_extension = cursor.fetchone()[0] or 0
            conn.close()
            return {
                'score': best_score,
                'accuracy': best_accuracy,
                'angle': best_angle,
                'extension': best_extension
            }
        except Exception as e:
            print(f"Failed to pull all-time best: {e}")
            return {
                'score': 0,
                'accuracy': 0,
                'angle': 0,
                'extension': 0
            }

    def get_recent_sessions(self, limit: int = 6, patient_id: str = None):
        """Return last N sessions ordered oldest→newest for progress chart"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if patient_id:
                cursor.execute("""
                    SELECT level, avg_accuracy, avg_hand_angle, score,
                           strftime('%d/%m', timestamp) as date
                    FROM sessions 
                    WHERE patient_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (patient_id, limit))
            else:
                cursor.execute("""
                    SELECT level, avg_accuracy, avg_hand_angle, score,
                           strftime('%d/%m', timestamp) as date
                    FROM sessions ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return list(reversed(rows))
        except Exception as e:
            print(f"Failed to pull recent sessions: {e}")
            return []

    def get_session_history(self, limit: int = 20, patient_id: str = None):
        """Full session list for the History screen (newest first)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if patient_id:
                cursor.execute("""
                    SELECT id,
                           strftime('%d/%m/%Y %H:%M', timestamp) as dt,
                           level, score, avg_accuracy, avg_hand_angle,
                           duration, pain_level
                    FROM sessions 
                    WHERE patient_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (patient_id, limit))
            else:
                cursor.execute("""
                    SELECT id,
                           strftime('%d/%m/%Y %H:%M', timestamp) as dt,
                           level, score, avg_accuracy, avg_hand_angle,
                           duration, pain_level
                    FROM sessions ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            print(f"Failed to pull session history: {e}")
            return []

    def get_rom_trend(self, limit: int = 10, patient_id: str = None):
        """ROM angle per session newest→oldest, for trend line chart"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if patient_id:
                cursor.execute("""
                    SELECT avg_hand_angle, strftime('%d/%m', timestamp)
                    FROM sessions 
                    WHERE patient_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (patient_id, limit))
            else:
                cursor.execute("""
                    SELECT avg_hand_angle, strftime('%d/%m', timestamp)
                    FROM sessions ORDER BY id DESC LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return list(reversed(rows))
        except Exception as e:
            print(f"Failed to pull ROM trend: {e}")
            return []

    def predict_recovery_progress(self, patient_id: str = None) -> float:
        """Predict recovery percentage over next 7 days based on recent data."""
        try:
            sessions = self.get_session_history(20, patient_id=patient_id)
            if len(sessions) < 3: return -1.0
            
            # Use max_finger_extension or avg_hand_angle for trend
            # session format: (id, dt, level, score, acc, rom, dur, pain)
            x = np.array(range(len(sessions))).reshape(-1, 1)
            y = np.array([float(s[5]) for s in sessions]) # ROM
            
            from sklearn.linear_model import LinearRegression
            model = LinearRegression().fit(x, y)
            
            future_x = np.array([[len(sessions) + 7]])
            prediction = model.predict(future_x)[0]
            
            current_avg = np.mean(y)
            improvement = ((prediction - current_avg) / current_avg * 100) if current_avg != 0 else 0
            return max(0, improvement)
        except Exception as e:
            print(f"Prediction error: {e}")
            return -1.0

    def clear_all_history(self):
        """Purge all session records from database"""
        try:
            import sqlite3
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM sessions")
                conn.commit()
            print("Database history purged.")
        except Exception as e:
            print(f"Purge error: {e}")

    def render_matplotlib_dashboard(self, patient_id: str = None) -> pygame.Surface:
        try:
            rom_data = self.get_rom_trend(15, patient_id=patient_id) 
            sessions = self.get_session_history(15, patient_id=patient_id)
            
            if not rom_data or not sessions:
                surf = pygame.Surface((660, 560))
                surf.fill((8, 12, 22))
                # Render placeholders
                font = pygame.font.SysFont("segoeui", 20)
                lbl = font.render("AWAITING PATIENT DATA FOR CLINICAL DASHBOARD", True, (0, 180, 255))
                surf.blit(lbl, lbl.get_rect(center=(330, 280)))
                return surf
                
            # Create a 2x1 vertical layout with exact size 6.6x5.6 to match container aspect ratio perfectly
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.6, 5.6), dpi=100)
            fig.patch.set_facecolor('#080c16')
            
            rom_chrono = list(reversed(rom_data))
            angles = [r[0] or 0 for r in rom_chrono]
            dates = [r[1] or "" for r in rom_chrono] 
            
            # High-visibility neon green trend line with white nodes
            ax1.plot(dates, angles, marker='o', markersize=6, color='#00f0ff', linewidth=3, 
                     markerfacecolor='#32ff96', markeredgecolor='#080c16')
            ax1.set_facecolor('#0f172a')
            ax1.set_title("Flexion ROM Trend (deg)", color='#00f0ff', fontsize=11, fontweight='bold', pad=8)
            ax1.tick_params(colors='#ffffff', labelsize=9)
            ax1.tick_params(axis='x', rotation=15)
            ax1.grid(color='#1e293b', linestyle=':', linewidth=0.8)
            ax1.spines['bottom'].set_color('#1e293b')
            ax1.spines['top'].set_color('#1e293b')
            ax1.spines['left'].set_color('#1e293b')
            ax1.spines['right'].set_color('#1e293b')
            
            sess_chrono = list(reversed(sessions))
            durations = [s[6] or 0 for s in sess_chrono] # Duration in seconds
            sdates = [(s[1] or "")[:6] for s in sess_chrono]
            
            # High-visibility sky blue bars with neon green borders
            ax2.bar(sdates, durations, color='#0088ff', edgecolor='#32ff96', linewidth=1.5, alpha=0.9)
            ax2.set_facecolor('#0f172a')
            ax2.set_title("Rehab Session Consistency", color='#00f0ff', fontsize=11, fontweight='bold', pad=8)
            ax2.tick_params(colors='#ffffff', labelsize=9)
            ax2.tick_params(axis='x', rotation=15)
            ax2.grid(color='#1e293b', linestyle=':', linewidth=0.8)
            ax2.spines['bottom'].set_color('#1e293b')
            ax2.spines['top'].set_color('#1e293b')
            ax2.spines['left'].set_color('#1e293b')
            ax2.spines['right'].set_color('#1e293b')
            
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format='png', facecolor='#080c16')
            buf.seek(0)
            plt.close(fig)
            return pygame.image.load(buf, 'png')
        except Exception as e:
            print(f"Matplotlib dashboard error: {e}")
            surf = pygame.Surface((660, 560))
            surf.fill((8, 12, 22))
            return surf

# ============================================================================
# UI COMPONENTS
# ============================================================================

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
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=16)
        border_color = (50, 255, 150) if is_hovering else (0, 180, 220)
        pygame.draw.rect(screen, border_color, self.rect, 4 if is_hovering else 3, border_radius=16)

        # Badge: Vertically center for normal buttons, slightly offset down for tall cards
        badge_y = self.rect.y + 12 if self.rect.height <= 80 else self.rect.y + 16
        badge_rect = pygame.Rect(self.rect.x + 12, badge_y, 36, 36)
        badge_color = (50, 255, 150) if is_hovering else (0, 150, 200)
        pygame.draw.rect(screen, badge_color, badge_rect, border_radius=8)
        badge_text = font_badge.render(str(self.level_num), True, (0, 0, 0))
        screen.blit(badge_text, badge_text.get_rect(center=badge_rect.center))

        text_color = (255, 255, 255) if is_hovering else (200, 210, 230)
        
        # Split text by newlines for multiline age group cards
        lines = [line.strip() for line in self.text.split('\n') if line.strip()]
        if len(lines) > 1:
            # Multi-line card layout (e.g. age group selection card)
            left_boundary = self.rect.x + 60
            right_boundary = self.ring.x - self.ring.radius - 15
            center_x = (left_boundary + right_boundary) // 2
            
            line_heights = [font.size(line)[1] for line in lines]
            total_h = sum(line_heights) + (len(lines) - 1) * 6
            start_y = self.rect.centery - total_h // 2
            
            for line in lines:
                surf = font.render(line, True, text_color)
                rect = surf.get_rect(center=(center_x, start_y + surf.get_height() // 2))
                screen.blit(surf, rect)
                start_y += surf.get_height() + 6
        else:
            # Single line buttons (e.g. level button or bottom utility button)
            # Center vertically, left-aligned at x+60 (just next to level badge)
            text_surf = font.render(self.text, True, text_color)
            screen.blit(text_surf, text_surf.get_rect(midleft=(self.rect.x + 60, self.rect.centery)))

        bar_h = 6
        bar_rect = pygame.Rect(self.rect.x + 12, self.rect.bottom - bar_h - 8,
                               self.rect.width - 24, bar_h)
        pygame.draw.rect(screen, (40, 45, 70), bar_rect, border_radius=3)
        if progress > 0:
            fill_rect = pygame.Rect(bar_rect.x, bar_rect.y,
                                    int(bar_rect.width * progress), bar_h)
            pygame.draw.rect(screen, (50, 255, 150), fill_rect, border_radius=3)

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

# ============================================================================
# MEDICAL SIDEBAR
# ============================================================================

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

    def _panel(self, screen, rect, border=(210, 224, 236)):
        pygame.draw.rect(screen, COLOR_MED_PANEL, rect, border_radius=8)
        pygame.draw.rect(screen, border, rect, 1, border_radius=8)

    def _metric(self, screen, rect, label, value, color=COLOR_MED_TEXT):
        self._panel(screen, rect)
        self._draw_text(screen, label.upper(), self.font_small, COLOR_MED_MUTED, (rect.x + 10, rect.y + 7))
        value_surf = self.font_data.render(str(value), True, color)
        screen.blit(value_surf, (rect.x + 10, rect.y + 25))

    def _status_pill(self, screen, rect, text, color):
        bg = tuple(max(0, min(255, int(c * 0.14 + 230))) for c in color)
        pygame.draw.rect(screen, bg, rect, border_radius=12)
        pygame.draw.rect(screen, color, rect, 1, border_radius=12)
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
             correctness_text: str = "Ready"):
        pygame.draw.rect(screen, COLOR_SIDEBAR_BG, (self.x, 0, self.width, WINDOW_HEIGHT))
        pygame.draw.line(screen, (198, 214, 229), (self.x, 0), (self.x, WINDOW_HEIGHT), 1)

        title_rect = pygame.Rect(self.x + 12, 10, self.width - 24, 42)
        self._panel(screen, title_rect)
        self._draw_text(screen, "AI Rehabilitation Monitor", self.font_title, COLOR_MED_TEXT,
                        (title_rect.x + 10, title_rect.y + 6))
        self._draw_text(screen, "Live clinical session", self.font_small, COLOR_MED_MUTED,
                        (title_rect.x + 10, title_rect.y + 27))

        cam_y = 62
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

        y = cam_rect.bottom + 10
        has_hand = hand_data.index_tip is not None
        status = "Tracking stable" if has_hand else "Hand not detected"
        self._status_pill(screen, pygame.Rect(self.x + 12, y, self.width - 24, 26),
                          status, COLOR_MED_SUCCESS if has_hand else COLOR_DANGER)
        y += 36

        if is_results:
            return

        correctness_lower = correctness_text.lower()
        correct_col = COLOR_MED_SUCCESS if correctness_lower.startswith(("correct", "good", "ready")) else COLOR_DANGER
        self._status_pill(screen, pygame.Rect(self.x + 12, y, self.width - 24, 28),
                          correctness_text, correct_col)
        y += 38

        acc = (accuracy_hits / accuracy_attempts * 100) if accuracy_attempts > 0 else 0.0
        acc_col = COLOR_MED_SUCCESS if acc >= 70 else COLOR_MED_WARNING if acc >= 40 else COLOR_DANGER
        rom = sum(hand_data.knuckle_angles[:4]) / len(hand_data.knuckle_angles[:4]) if hand_data.knuckle_angles else 0.0
        card_w = (self.width - 34) // 2

        self._metric(screen, pygame.Rect(self.x + 12, y, card_w, 54), "Score", score)
        self._metric(screen, pygame.Rect(self.x + 22 + card_w, y, card_w, 54), "Accuracy", f"{acc:.0f}%", acc_col)
        y += 64
        self._metric(screen, pygame.Rect(self.x + 12, y, card_w, 54), "Exercises", exercise_count)
        mins = int(session_elapsed // 60)
        secs = int(session_elapsed % 60)
        self._metric(screen, pygame.Rect(self.x + 22 + card_w, y, card_w, 54), "Timer", f"{mins:02d}:{secs:02d}")
        y += 64
        self._metric(screen, pygame.Rect(self.x + 12, y, card_w, 54), "Current ROM", f"{rom:.0f} deg", COLOR_MED_PRIMARY)
        pain_col = COLOR_MED_SUCCESS if pain_level <= 3 else COLOR_MED_WARNING if pain_level <= 6 else COLOR_DANGER
        self._metric(screen, pygame.Rect(self.x + 22 + card_w, y, card_w, 54), "Pain Score", f"{pain_level}/10", pain_col)
        y += 64

        panel = pygame.Rect(self.x + 12, y, self.width - 24, 62)
        self._panel(screen, panel)
        self._draw_text(screen, "EXERCISE NAME", self.font_small, COLOR_MED_MUTED, (panel.x + 10, panel.y + 8))
        self._draw_text(screen, exercise_name, self.font_data, COLOR_MED_TEXT, (panel.x + 10, panel.y + 29))
        y = panel.bottom + 10

        pred_text = "Need more data"
        pred_col = COLOR_MED_MUTED
        if recovery_prediction is not None and recovery_prediction >= 0:
            pred_text = f"{recovery_prediction:.1f}% predicted recovery"
            pred_col = COLOR_MED_PRIMARY
        panel = pygame.Rect(self.x + 12, y, self.width - 24, 60)
        self._panel(screen, panel)
        self._draw_text(screen, "RECOVERY PREDICTION", self.font_small, COLOR_MED_MUTED, (panel.x + 10, panel.y + 8))
        self._draw_text(screen, pred_text, self.font_label, pred_col, (panel.x + 10, panel.y + 31))
        y = panel.bottom + 10

        panel = pygame.Rect(self.x + 12, y, self.width - 24, 104)
        self._panel(screen, panel)
        self._draw_text(screen, "STATUS MESSAGE", self.font_small, COLOR_MED_MUTED, (panel.x + 10, panel.y + 8))
        next_y = self._wrap(screen, level_goals or "Ready for guided rehabilitation.",
                            panel.x + 10, panel.y + 30, 34, COLOR_MED_TEXT)
        if hand_data.is_pinching or hand_data.is_fist:
            gesture = "Pinch active" if hand_data.is_pinching else "Fist active"
            self._draw_text(screen, gesture, self.font_small, COLOR_MED_PRIMARY,
                            (panel.x + 10, min(next_y + 2, panel.bottom - 18)))
        self._bar(screen, panel.x + 10, panel.bottom - 12, panel.width - 20, acc / 100.0, acc_col)


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
        self.font_title = pygame.font.SysFont("segoeui", 38)
        self.font_head  = pygame.font.SysFont("segoeui", 28)
        self.font_body  = pygame.font.SysFont("segoeui", 22)
        self.font_small = pygame.font.SysFont("segoeui", 18)
        self.font_tiny  = pygame.font.SysFont("segoeui", 16)
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
                         pygame.Rect(x, y, w, 24), border_radius=5)
        t = self.font_tiny.render(f"  {title}", True, (0, 0, 0))
        screen.blit(t, (x + 4, y + 4))
        return y + 30

    def _line(self, screen, txt, y, col=(200, 215, 230), indent=24):
        s = self.font_small.render(txt, True, col)
        screen.blit(s, (indent, y))
        return y + 20

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
            import matplotlib.pyplot as plt
            import io
            
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

        cx  = GAME_AREA_WIDTH // 2
        grade_str, grade_col = self._rom_grade(angle)
        stars  = self._stars(accuracy)
        tier   = self._tier(accuracy)
        exs    = self.EXERCISES.get(level, {}).get(tier, [])

        # ── BACKGROUND PLATE ──────────────────────────────────────────
        pygame.draw.rect(screen, (8, 12, 25), pygame.Rect(10, 75, GAME_AREA_WIDTH - 20, WINDOW_HEIGHT - 120), border_radius=10)
        pygame.draw.rect(screen, (0, 100, 150), pygame.Rect(10, 75, GAME_AREA_WIDTH - 20, WINDOW_HEIGHT - 120), 1, border_radius=10)

        # ── HEADER ────────────────────────────────────────────────────
        pygame.draw.rect(screen, (10, 20, 40), pygame.Rect(0, 0, GAME_AREA_WIDTH, 70))
        pygame.draw.line(screen, (0, 200, 255), (0, 70), (GAME_AREA_WIDTH, 70), 2)
        
        title_surf = self.font_title.render("SESSION PERFORMANCE REPORT", True, (0, 210, 255))
        screen.blit(title_surf, title_surf.get_rect(center=(cx, 35)))

        y_top = 85
        
        # ── CLINICAL SUMMARY (One-liner) ─────────────────────────────
        one_line = self._one_liner(level, accuracy, angle)
        ol_bg = pygame.Rect(20, y_top, GAME_AREA_WIDTH - 40, 32)
        pygame.draw.rect(screen, (20, 35, 60), ol_bg, border_radius=6)
        ol_surf = self.font_small.render(one_line, True, (255, 210, 120))
        screen.blit(ol_surf, ol_surf.get_rect(center=ol_bg.center))
        
        # ── COLUMNS ───────────────────────────────────────────────────
        col1_x, col2_x = 20, 490
        col_w = 450
        y = y_top + 45

        # --- LEFT: PERFORMANCE ---
        ly = y
        ly = self._section_bar(screen, "SESSION METRICS", col1_x, ly, col_w, (0, 140, 200))
        
        # Star visualization (Graphical)
        sy = ly + 15
        star_col = [(220,60,60),(255,200,0),(50,220,120)][stars-1]
        for i in range(3):
            self._draw_star(screen, col1_x + 25 + i*35, sy, 14, i < stars, star_col)
        ly += 45
        
        ly = self._line(screen, f"Accuracy: {accuracy:.0f}%", ly, (200, 240, 200), indent=col1_x + 10)
        ly = self._line(screen, f"Joint Angle: {angle:.1f}°", ly, grade_col, indent=col1_x + 10)
        ly = self._line(screen, f"Grade: {grade_str}", ly, grade_col, indent=col1_x + 10)
        
        ly += 20
        ly = self._section_bar(screen, "DAILY EXERCISES", col1_x, ly, col_w, (130, 80, 0))
        for i, (ex, dose, freq) in enumerate(exs[:3]):
            ly = self._line(screen, f"{i+1}. {ex}", ly, (200, 220, 240), indent=col1_x + 5)
            ly = self._line(screen, f"   {dose} | {freq}", ly, (140, 160, 180), indent=col1_x + 15)
            ly += 2

        # --- RIGHT: ANALYTICS ---
        ry = y
        ry = self._section_bar(screen, "RECOVERY VISUALIZATION", col2_x, ry, col_w, (70, 40, 140))
        
        if self.session_chart:
            # Scale chart to fit half screen
            scaled_chart = pygame.transform.smoothscale(self.session_chart, (col_w - 10, 220))
            screen.blit(scaled_chart, (col2_x + 5, ry + 5))
            ry += 235
        else:
            ry += 40

        ry = self._section_bar(screen, "FLEXIBILITY PROGRESS", col2_x, ry, col_w, (0, 120, 150))
        bar_x = col2_x + 10
        bar_w = col_w - 20
        ry += 10
        pygame.draw.rect(screen, (30, 40, 60), pygame.Rect(bar_x, ry, bar_w, 18), border_radius=4)
        fill = int(bar_w * min(angle / self.ROM_NORMAL, 1.0))
        if fill > 0:
            pygame.draw.rect(screen, grade_col, pygame.Rect(bar_x, ry, fill, 18), border_radius=4)
        ry += 30

        # Footer
        nav_txt = "Hold FIST 2s to Return to Menu | Clinical data saved to database"
        nav_surf = self.font_small.render(nav_txt, True, (100, 130, 160))
        screen.blit(nav_surf, nav_surf.get_rect(center=(cx, WINDOW_HEIGHT - 30)))

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

# ============================================================================
# MAIN GAME APPLICATION
# ============================================================================

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

class PhysioSystem:
    """Main application"""
    
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.SCALED)
        pygame.display.set_caption("Zero-Keyboard AI Physiotherapy System")
        self.clock = pygame.time.Clock()
        
        # Cached fonts (NEVER create fonts inside draw loops — causes memory leak/crash)
        self.font_large  = pygame.font.SysFont("segoeui", 54)
        self.font_medium = pygame.font.SysFont("segoeui", 40)
        self.font_head   = pygame.font.SysFont("segoeui", 28)
        self.font_small  = pygame.font.SysFont("segoeui", 22)
        self.font_hud    = pygame.font.SysFont("segoeui", 22)
        self.font_hint   = pygame.font.SysFont("segoeui", 18)
        self.font_tiny   = pygame.font.SysFont("segoeui", 16)
        self.font_cd     = pygame.font.SysFont("segoeui", 32)
        self.font_badge  = pygame.font.SysFont("segoeui", 24)

        # Cursor trail buffer
        self._cursor_trail: list = []
        
        # Components
        self.hand_engine = HandEngine()
        self.db = DatabaseManager()
        self.sidebar = MedicalSidebarV2()
        self.sounds = SoundSystem()
        self.particles = ParticleSystem()
        self.popups: List[ScorePopup] = []
        
        # State
        self.state = GameState.PATIENT_REGISTRATION
        self._last_state = None  # Track state changes for safe mouse warp and safety grace periods
        self._transition_time = 0.0  # Safe grace period timestamp on screen transitions
        self.age_group = None  # Will be set on age selection
        
        # Patient Information
        self.patient_name = ""
        self.patient_age = ""
        self.patient_id_str = ""
        self.input_active = "id"  # default to "id"
        
        self.running = True
        self.session_start = None
        self.score = 0
        self.max_extension = 0.0
        self.reach_distance = 0.0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        
        # Visual feedback
        self.combo = 0
        self.feedback_text = None
        self.feedback_timer = 0
        self.screen_shake = 0
        self.shake_offset = (0, 0)

        # Pain scale (before each session)
        self.pain_level = 0          # 0-10 NRS score
        self.pending_level = None    # which level player picked (before pain screen)

        # Power-ups and game modifiers
        self.score_multiplier = 1.0
        self.multiplier_timer = 0
        self.slow_mo = False
        self.slow_mo_timer = 0
        self.shield_active = False
        self.shield_timer = 0
        self.achievements_unlocked = set()
        
        # UI Elements
        # Age selection buttons (4 large cards) centered for 1280 WINDOW_WIDTH
        self.age_buttons = [
            LevelButton(240, 150, 380, 180, "CHILDREN\n5-12 years", 1),
            LevelButton(660, 150, 380, 180, "YOUNG ADULTS\n18-35 years", 2),
            LevelButton(240, 380, 380, 180, "ADULTS\n35-60 years", 3),
            LevelButton(660, 380, 380, 180, "SENIORS\n60+ years", 4)
        ]
        
        cx = GAME_AREA_WIDTH // 2
        bw = 270
        gap = 50
        col1_x = cx - bw - (gap // 2)
        col2_x = cx + (gap // 2)
        self.level_buttons = [
            LevelButton(col1_x, 170, bw, 80, "LEVEL 1", 1, ring_radius=48),
            LevelButton(col2_x, 170, bw, 80, "LEVEL 2", 2, ring_radius=48),
            LevelButton(col1_x, 275, bw, 80, "LEVEL 3", 3, ring_radius=48),
            LevelButton(col2_x, 275, bw, 80, "LEVEL 4", 4, ring_radius=48),
            LevelButton(col1_x, 380, bw, 80, "LEVEL 5", 5, ring_radius=48),
            LevelButton(col2_x, 380, bw, 80, "LEVEL 6", 6, ring_radius=48)
        ]
        # Adjusting positions to fit History, Calibration, Exit nicely side-by-side
        self.history_button = LevelButton(cx - 410, 495, 260, 60, "RECOVERY HISTORY", 9, ring_radius=40)
        self.calibrate_button = LevelButton(cx - 130, 495, 260, 60, "ROM DIAGNOSTICS", 8, ring_radius=40)
        self.exit_button = LevelButton(cx + 150, 495, 260, 60, "EXIT SYSTEM", 99, ring_radius=40)
        self.logout_button = Button(20, 15, 140, 40, "← LOGOUT", (50, 50, 70))
        self.logout_button.duration = 1.2
        self.home_icon = HomeIcon(GAME_AREA_WIDTH - 250, 15, 240, 60)
        
        # Calibration state variables
        self.calibrated_fist_val = 0.12       # default check threshold
        self.calibrated_max_extension = 170.0  # default reach extension in pixels
        self.calibrated_min_angle = 15.0      # min knuckle angle (fist)
        self.calibrated_max_angle = 90.0      # max knuckle angle (open)
        self.calibration_active = False       # whether calibration was completed
        
        # Game objects
        self.bubbles = []
        self.falling_items = []
        self.seeds = []
        self.basket_x = GAME_AREA_WIDTH // 2
        self.basket_y = WINDOW_HEIGHT - 100
        self.pot_x = GAME_AREA_WIDTH // 2
        self.pot_y = WINDOW_HEIGHT - 80
        
        self.trace_t = 0.0
        self.trace_target_x = GAME_AREA_WIDTH // 2
        self.trace_target_y = WINDOW_HEIGHT // 2
        self.trace_path = []
        
        self.pump_state = 0
        self.pump_reps = 0
        self.balloon_scale = 1.0
        
        self.simon_sequence = []
        self.simon_player_idx = 0
        self.simon_state = "START"
        self.simon_timer = 0
        self.simon_show_idx = 0
        self.simon_active_pad = None
        
        self.current_level = 0
        
        # Analytics tracking
        self.angle_history = deque(maxlen=300)  # Track angles for averaging
        
        # Post-game components
        self.summary_screen = PostGameSummary()
        self.quick_start_button = CloseButton(GAME_AREA_WIDTH // 2 - 240, 560, 480, 60)
        self.quick_start_button.duration = 2.0
        
        # Repositioned buttons to prevent footer overlap
        btn_y = 495
        bw, bh = 170, 44
        cx = GAME_AREA_WIDTH // 2
        
        self.menu_button  = CloseButton(cx - 360, btn_y, bw, bh)
        self.next_button  = CloseButton(cx - 180, btn_y, bw, bh)
        self.home_button  = CloseButton(cx + 0,   btn_y, bw, bh)
        self.close_button = CloseButton(cx + 180, btn_y, bw, bh)
        
        # Calibration buttons
        self.cal_start_button = CloseButton(GAME_AREA_WIDTH // 2 - 130, 460, 260, 60)
        self.cal_start_button.duration = 1.5
        self.cal_finish_button = CloseButton(GAME_AREA_WIDTH // 2 - 130, 540, 260, 60)
        self.cal_finish_button.duration = 1.5
        
        for b in [self.menu_button, self.next_button, self.home_button, self.close_button]:
            b.duration = 1.2
        self.session_data = None
        self.best_data = None
        self._level_complete_time = 0.0   # set by _end_level
        self.correctness_warning = ""
        self.warning_timer = 0
        self.dashboard_surf = None
        self.dashboard_loading = False
        
        # Virtual Sensei state
        self.last_coach_time = 0
        self.coaching_cooldown = 12.0 # Don't be annoying
        self.streak_counter = 0
        
        # Purge button for history
        self.purge_button = Button(WINDOW_WIDTH - 220, WINDOW_HEIGHT - 60, 200, 45, "PURGE RECORDS", (200, 50, 50))
        self.history_back_button = Button(20, WINDOW_HEIGHT - 60, 150, 45, "← BACK", (40, 60, 100))
        
        # Load and cache top 3 patient profiles for hands-free directory selection
        self._refresh_patient_profiles()

    def _refresh_patient_profiles(self):
        """Query existing patients and construct zero-keyboard buttons for the top 3"""
        self.patient_profile_buttons = {}
        
    def run(self):
        """Main application loop with initial splash screen"""
        try:
            # 1. INITIAL SPLASH SCREEN LOOP (while engine starts)
            loading = True
            start_time = time.time()
            engine_started = False
            engine_ready = False
            engine_error = False
            
            # Status messages for the medical splash
            status_msgs = [
                "BOOTING CLINICAL CORE...",
                "INITIALIZING NEURAL INTERFACE...",
                "CALIBRATING OPTICAL SENSORS...",
                "SYNCING PATIENT DATABASE...",
                "BIO-FEEDBACK ENGINE ONLINE.",
                "SYSTEM READY."
            ]
            
            while loading and self.running:
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        loading = False
                    if event.type == pygame.KEYDOWN and engine_error:
                        # Allow skipping splash if camera failed
                        loading = False
                
                # Start engine
                if not engine_started:
                    self.hand_engine.start()
                    engine_started = True
                
                # Progress
                elapsed = time.time() - start_time
                progress = min(1.0, elapsed / 3.5)
                
                # Readiness check
                engine_ready = False
                engine_error = False
                
                if self.hand_engine.webcam:
                    # Check background initialization status
                    if getattr(self.hand_engine.webcam, 'init_done', False):
                        if getattr(self.hand_engine.webcam, 'init_error', False):
                            engine_error = True
                        else:
                            with self.hand_engine.lock:
                                if self.hand_engine.mirrored_frame is not None:
                                    engine_ready = True
                else:
                    engine_error = True
                
                # Finish loading
                if progress >= 1.0 and engine_ready:
                    loading = False
                # Auto-proceed after 8s even if error (keyboard fallback)
                if engine_error and elapsed > 8.0:
                    loading = False
                
                self._draw_initial_splash(progress, status_msgs, engine_error)
                self.clock.tick(60)

            # Warp the mouse pointer to a safe, empty area (top right) immediately after loading screen
            pygame.mouse.set_pos((WINDOW_WIDTH - 50, 50))

            # 2. MAIN APPLICATION LOOP
            while self.running:
                self._handle_events()
                self._update()
                self._draw()
                self.clock.tick(FPS)
                
        finally:
            self.hand_engine.stop()
            try:
                pygame.mixer.quit()
            except:
                pass
            pygame.quit()

    def _draw_initial_splash(self, progress: float, messages: list, has_error: bool = False):
        """Premium medical-themed startup animation"""
        self.screen.fill((4, 8, 15)) # Deep space black/blue
        cx, cy = WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2
        t = time.time()

        # --- Tech Background Grid ---
        grid_color = (15, 25, 40)
        for x in range(0, WINDOW_WIDTH, 40):
            pygame.draw.line(self.screen, grid_color, (x, 0), (x, WINDOW_HEIGHT), 1)
        for y in range(0, WINDOW_HEIGHT, 40):
            pygame.draw.line(self.screen, grid_color, (0, y), (WINDOW_WIDTH, y), 1)

        # --- Moving Scanline ---
        scan_y = int((t * 200) % WINDOW_HEIGHT)
        pygame.draw.line(self.screen, (0, 150, 100, 60), (0, scan_y), (WINDOW_WIDTH, scan_y), 2)

        # --- Central Neural Hub Animation ---
        # Pulsing Glow
        glow_size = int(150 + 20 * math.sin(t * 4))
        glow_surf = pygame.Surface((glow_size * 2, glow_size * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (0, 100, 255, 30), (glow_size, glow_size), glow_size)
        self.screen.blit(glow_surf, (cx - glow_size, cy - glow_size))

        # Rotating Hexagons
        for i in range(3):
            angle = t * (i + 1) * 0.5
            pts = []
            r = 80 + i * 30
            for j in range(6):
                a = angle + j * (math.pi / 3)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            pygame.draw.polygon(self.screen, (0, 200, 255), pts, 2)

        # Inner pulsing core
        core_r = int(40 + 5 * math.sin(t * 8))
        pygame.draw.circle(self.screen, (0, 255, 180), (cx, cy), core_r, 3)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 10)

        # --- Progress Bar ---
        bar_w, bar_h = 400, 10
        bar_x, bar_y = cx - bar_w // 2, cy + 180
        pygame.draw.rect(self.screen, (20, 30, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=5)
        pygame.draw.rect(self.screen, (0, 255, 150), (bar_x, bar_y, int(bar_w * progress), bar_h), border_radius=5)
        
        # Glow for bar
        if progress > 0:
            pygame.draw.rect(self.screen, (0, 255, 150), (bar_x, bar_y, int(bar_w * progress), bar_h), 2, border_radius=5)

        # --- Loading Text Log ---
        log_idx = min(int(progress * len(messages)), len(messages) - 1)
        for i in range(log_idx + 1):
            alpha = 255 if i == log_idx else 100
            msg = messages[i]
            if i == log_idx:
                # Add flickering cursor to current line
                if int(t * 4) % 2 == 0: msg += " _"
            
            txt = self.font_hint.render(msg, True, (0, 255, 180))
            txt.set_alpha(alpha)
            self.screen.blit(txt, (50, 50 + i * 25))

        # --- Error Warning ---
        if has_error:
            err_surf = pygame.Surface((500, 100), pygame.SRCALPHA)
            err_surf.fill((100, 0, 0, 180))
            self.screen.blit(err_surf, (WINDOW_WIDTH//2 - 250, WINDOW_HEIGHT - 180))
            pygame.draw.rect(self.screen, (255, 50, 50), (WINDOW_WIDTH//2 - 250, WINDOW_HEIGHT - 180, 500, 100), 2)
            
            e_txt1 = self.font_small.render("CAMERA NOT DETECTED", True, (255, 200, 200))
            e_txt2 = self.font_hint.render("System will run in Keyboard Fallback Mode.", True, (255, 255, 255))
            e_txt3 = self.font_tiny.render("Press any key to continue...", True, (200, 200, 200))
            
            self.screen.blit(e_txt1, e_txt1.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 150)))
            self.screen.blit(e_txt2, e_txt2.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 125)))
            self.screen.blit(e_txt3, e_txt3.get_rect(center=(WINDOW_WIDTH//2, WINDOW_HEIGHT - 100)))

        # --- Percentage ---
        pct_txt = self.font_medium.render(f"{int(progress * 100)}%", True, (255, 255, 255))
        self.screen.blit(pct_txt, pct_txt.get_rect(center=(cx, bar_y + 40)))

        # --- Branded Footer ---
        footer = self.font_tiny.render("AI PHYSIOTHERAPY SYSTEM v2.0 | ZERO-KEYBOARD CLINICAL INTERFACE", True, (60, 90, 120))
        self.screen.blit(footer, footer.get_rect(center=(cx, WINDOW_HEIGHT - 30)))

        pygame.display.flip()
    
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Handle keyboard input for patient registration
            elif event.type == pygame.KEYDOWN and self.state == GameState.PATIENT_REGISTRATION:
                if event.key == pygame.K_BACKSPACE:
                    if self.input_active == "name":
                        self.patient_name = self.patient_name[:-1]
                    elif self.input_active == "age":
                        self.patient_age = self.patient_age[:-1]
                    elif self.input_active == "id":
                        self.patient_id_str = self.patient_id_str[:-1]
                elif event.key == pygame.K_TAB:
                    # Switch between fields
                    if self.input_active == "id": self.input_active = "name"
                    elif self.input_active == "name": self.input_active = "age"
                    else: self.input_active = "id"
                elif event.key == pygame.K_RETURN:
                    # Submit if ID is provided OR (name and age) are provided
                    if self.patient_id_str or (self.patient_name and self.patient_age):
                        self._submit_registration()
                else:
                    # Add character to active field
                    if self.input_active == "name" and len(self.patient_name) < 30:
                        if event.unicode.isprintable():
                            self.patient_name += event.unicode
                    elif self.input_active == "age" and len(self.patient_age) < 3:
                        if event.unicode.isdigit():
                            self.patient_age += event.unicode
                    elif self.input_active == "id" and len(self.patient_id_str) < 30:
                        if event.unicode.isprintable():
                            self.patient_id_str += event.unicode
                            
            # Therapist Dashboard shortcut
            elif event.type == pygame.KEYDOWN and self.state == GameState.MAIN_MENU:
                if event.key == pygame.K_F12:
                    self.state = GameState.THERAPIST_DASHBOARD
                    try: self.sounds.play('select')
                    except: pass
    
    def _update(self):
        # Check if state has transitioned to safely warp the mouse cursor and reset button hover clocks
        if self.state != self._last_state:
            # Warp the mouse pointer to a safe, empty area (top right inside the medical sidebar)
            pygame.mouse.set_pos((WINDOW_WIDTH - 50, 50))
            
            # Reset all button hover timers so the next screen starts completely fresh
            self._reset_all_button_hovers()
            
            # Update last state tracker and record transition time for safety grace period
            self._last_state = self.state
            self._transition_time = time.time()

        hand_data = self.hand_engine.get_hand_data()
        
        # Enforce 2.0-second safety grace period after transition to prevent accidental selections
        if time.time() - getattr(self, '_transition_time', 0.0) < 2.0:
            from copy import copy
            hand_data = copy(hand_data)
            hand_data.index_tip = None
        
        # Track max extension and angles
        if hand_data.finger_extension > 0:
            self.max_extension = max(self.max_extension, hand_data.finger_extension)
            
        # Virtual Sensei AI Coaching
        self._run_virtual_sensei(hand_data)
        
        if hand_data.knuckle_angles and len(hand_data.knuckle_angles) > 0:
            self.angle_history.append(hand_data.knuckle_angles[0])
            # Real-time Correctness Detection inside gameplay
            if self.state in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, GameState.LEVEL3_FINEMOTOR]:
                angle = hand_data.knuckle_angles[0]
                if angle > 165 and not hand_data.is_pinching: # Not bending enough
                    if self.warning_timer <= 0:
                        self.correctness_warning = "Bend fingers slightly more"
                        VOICE.speak("Bend fingers slightly more")
                        self.warning_timer = 120 # warn ~2s apart
                elif angle < 120:
                    if self.correctness_warning == "Bend fingers slightly more" and self.warning_timer <= 60:
                        self.correctness_warning = "Good job"
                        VOICE.speak("Good job")
                        self.warning_timer = 180 # Stay at "good job" for 3s
                if self.warning_timer > 0:
                    self.warning_timer -= 1
                elif self.warning_timer <= 0:
                    self.correctness_warning = ""
        
        # Check home icon (pause/quit) - Double-Trigger Exit
        if self.state not in [GameState.MAIN_MENU, GameState.RESULTS,
                               GameState.LEVEL_COMPLETE, GameState.PAIN_SCALE,
                               GameState.HISTORY, GameState.PATIENT_REGISTRATION,
                               GameState.AGE_SELECT, GameState.CLOUD_SYNC, GameState.THERAPIST_DASHBOARD]:
            
            # Check if we are in an active gameplay level where making a fist is part of the therapy
            gameplay_states = [
                GameState.LEVEL1_FLEXIBILITY,
                GameState.LEVEL2_STRENGTH,
                GameState.LEVEL3_FINEMOTOR,
                GameState.LEVEL4_COORDINATION,
                GameState.LEVEL5_GRIP_RELEASE,
                GameState.LEVEL6_FINGER_TAPS
            ]
            is_gameplay = self.state in gameplay_states
            
            # Trigger 1: Hover-to-Select on HomeIcon (disable global fist trigger during active gameplay or calibration)
            fist_trigger_disabled = is_gameplay or (self.state == GameState.CALIBRATION)
            home_hover_exit = self.home_icon.update(False if fist_trigger_disabled else hand_data.is_fist, hand_data.index_tip)
            
            # Trigger 2: Global Fist hold countdown anywhere on the screen (disabled during active gameplay or calibration)
            global_fist_exit = False
            if not is_gameplay and self.state != GameState.CALIBRATION and hand_data.is_fist:
                if not hasattr(self, '_global_fist_start') or self._global_fist_start is None:
                    self._global_fist_start = time.time()
                elapsed = time.time() - self._global_fist_start
                if elapsed >= 2.0:
                    global_fist_exit = True
                    self._global_fist_start = None
            else:
                self._global_fist_start = None
                
            if home_hover_exit or global_fist_exit:
                self.state = GameState.MAIN_MENU
                self._reset_game()
                self._global_fist_start = None
        
        # Check tracking & Freeze Timer
        is_playing = self.state in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, 
                                    GameState.LEVEL3_FINEMOTOR, GameState.LEVEL4_COORDINATION,
                                    GameState.LEVEL5_GRIP_RELEASE, GameState.LEVEL6_FINGER_TAPS]
        
        now = time.time()
        dt = now - getattr(self, '_last_update_time', now)
        self._last_update_time = now

        if is_playing and hand_data.index_tip is None:
            self.tracking_lost = True
            # Freeze the game timer by advancing session_start
            if self.session_start is not None:
                self.session_start += dt
        else:
            self.tracking_lost = False
            if is_playing:
                self.game_has_started = True
            
        # State machine
        if self.state == GameState.PATIENT_REGISTRATION:
            self._update_patient_registration(hand_data)
        elif self.state == GameState.AGE_SELECT:
            self._update_age_select(hand_data)
        elif self.state == GameState.MAIN_MENU:
            self._update_menu(hand_data)
        elif self.state == GameState.PAIN_SCALE:
            self._update_pain_scale(hand_data)
        elif self.state == GameState.HISTORY:
            self._update_history(hand_data)
        elif self.state == GameState.CALIBRATION:
            self._update_calibration(hand_data)
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            if not getattr(self, 'tracking_lost', False):
                self._update_level1(hand_data)
        elif self.state == GameState.LEVEL2_STRENGTH:
            if not getattr(self, 'tracking_lost', False):
                self._update_level2(hand_data)
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            if not getattr(self, 'tracking_lost', False):
                self._update_level3(hand_data)
        elif self.state == GameState.LEVEL4_COORDINATION:
            if not getattr(self, 'tracking_lost', False):
                self._update_level4(hand_data)
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            if not getattr(self, 'tracking_lost', False):
                self._update_level5(hand_data)
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            if not getattr(self, 'tracking_lost', False):
                self._update_level6(hand_data)
        elif self.state == GameState.LEVEL_COMPLETE:
            if time.time() - self._level_complete_time > 2.5:
                self.state = GameState.RESULTS
        elif self.state == GameState.RESULTS:
            self._update_results(hand_data)
        elif self.state == GameState.CLOUD_SYNC:
            if time.time() - getattr(self, 'sync_start', 0) > 2.5:
                self.state = GameState.MAIN_MENU
                self._reset_game()
        elif self.state == GameState.THERAPIST_DASHBOARD:
            self._update_therapist_dashboard(hand_data)
            if self.admin_back_button.update(hand_data.index_tip) or (hand_data.is_fist and self.home_icon.update(True, hand_data.index_tip)):
                self.state = GameState.MAIN_MENU
                    
        # Update visual effects
        self.particles.update()
        self.popups = [p for p in self.popups if p.update()]
        
        # Update power-up timers
        if self.multiplier_timer > 0:
            self.multiplier_timer -= 1
            if self.multiplier_timer == 0:
                self.score_multiplier = 1.0
        
        if self.slow_mo_timer > 0:
            self.slow_mo_timer -= 1
            if self.slow_mo_timer == 0:
                self.slow_mo = False
                
        if self.shield_timer > 0:
            self.shield_timer -= 1
            if self.shield_timer == 0:
                self.shield_active = False
        
        # Update feedback timer
        if self.feedback_timer > 0:
            self.feedback_timer -= 1
            if self.feedback_timer == 0:
                self.feedback_text = None
        
        # Update screen shake
        if self.screen_shake > 0:
            self.screen_shake -= 1
            shake_amount = self.screen_shake // 2
            self.shake_offset = (random.randint(-shake_amount, shake_amount), 
                                random.randint(-shake_amount, shake_amount))
        else:
            self.shake_offset = (0, 0)
    
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

    def _update_menu(self, hand_data: HandData):
        if hasattr(self, 'logout_button') and self.logout_button.update(hand_data.index_tip):
            self.state = GameState.PATIENT_REGISTRATION
            self.patient_name = ""
            self.patient_age = ""
            self.input_active = "name"
            self.pain_checked = False
            self.calibration_active = False
            self.calibrated_fist_val = 0.12
            self.calibrated_max_extension = 170.0
            self.calibrated_min_angle = 15.0
            self.calibrated_max_angle = 90.0
            self.sounds.play('pop')
            return

        if hasattr(self, 'exit_button') and self.exit_button.update(hand_data.index_tip):
            self.running = False
            return
            
        # Calibration button
        if hasattr(self, 'calibrate_button') and self.calibrate_button.update(hand_data.index_tip):
            self.state = GameState.CALIBRATION
            self._init_calibration()
            self.sounds.play('select')
            return

        # History button
        if self.history_button.update(hand_data.index_tip):
            self.state = GameState.HISTORY
            self.dashboard_surf = None
            self.dashboard_loading = True
            self.sounds.play('select')
            
            # Load dashboard chart asynchronously in a background thread to prevent UI freezing
            def load_async():
                try:
                    surf = self.db.render_matplotlib_dashboard(self.patient_name)
                    self.dashboard_surf = surf
                except Exception as e:
                    print(f"Failed loading async chart: {e}")
                finally:
                    self.dashboard_loading = False
            
            threading.Thread(target=load_async, daemon=True).start()
            return
            
        for button in self.level_buttons:
            if button.update(hand_data.index_tip):
                self.current_level = button.level_num
                self.pending_level = button.level_num
                self.sounds.play('select')
                if not getattr(self, 'pain_checked', False):
                    self.pain_level = 0  # reset pain before pain screen
                    self.state = GameState.PAIN_SCALE  # show pain scale first
                else:
                    self._start_level()
                break
    
    def _update_level1(self, hand_data: HandData):
        """Level 1: Pop the Bubbles (Flexibility)"""
        # Safety: ensure bubbles exist
        if not self.bubbles:
            self._spawn_bubbles()
            return

        # Move bubbles
        for bubble in self.bubbles:
            if not bubble.popped:
                bubble.x += bubble.vx
                bubble.y += bubble.vy
                if bubble.x < bubble.radius or bubble.x > GAME_AREA_WIDTH - bubble.radius:
                    bubble.vx *= -1
                if bubble.y < bubble.radius or bubble.y > WINDOW_HEIGHT - bubble.radius:
                    bubble.vy *= -1

        if hand_data.index_tip:
            for bubble in self.bubbles:
                if not bubble.popped:
                    dist = distance(hand_data.index_tip, (bubble.x, bubble.y))
                    if dist < bubble.radius:
                        bubble.popped = True
                        self.accuracy_attempts += 1   # count per bubble, not per frame
                        self.accuracy_hits += 1
                        points = int(10 * self.score_multiplier * (3 if bubble.is_golden else 1))
                        self.score += points
                        self.combo += 1
                        self._trigger_feedback()
                        self.sounds.play('pop')
                        color = (255, 215, 0) if bubble.is_golden else COLOR_BUBBLE
                        self.particles.emit(int(bubble.x), int(bubble.y), color, 20 if bubble.is_golden else 15)
                        self.popups.append(ScorePopup(bubble.x, bubble.y - 20, f"+{points}"))
                        if hand_data.wrist:
                            reach = distance(hand_data.wrist, (bubble.x, bubble.y))
                            self.reach_distance = max(self.reach_distance, reach)

        # Check if all bubbles popped (only when list is non-empty)
        if (self.bubbles and all(b.popped for b in self.bubbles)) or (time.time() - getattr(self, 'level_wall_start', 0.0) > LEVEL_DURATION * 1.5):
            self._end_level()
    
    def _update_level2(self, hand_data: HandData):
        """Level 2: The Basket (Strength)"""
        # Smooth basket movement
        if hand_data.palm_center:
            self.basket_x = hand_data.palm_center[0]
        
        speed_mult = 0.5 if self.slow_mo else 1.0
        
        # Update falling items
        for item in self.falling_items[:]:
            item.y += item.speed * speed_mult * getattr(self, 'pacing_multiplier', 1.0)
            
            # Check collision with basket
            if (item.y >= self.basket_y - 20 and 
                item.y <= self.basket_y + 20 and
                abs(item.x - self.basket_x) < 75):
                
                self.falling_items.remove(item)
                
                if item.is_bomb:
                    if self.shield_active:
                        self.shield_active = False
                        self.shield_timer = 0
                        self.sounds.play('pop')
                        self.particles.emit(int(item.x), self.basket_y, (0, 200, 255), 25)
                        self.popups.append(ScorePopup(item.x, self.basket_y - 30, "DEFLECTED!"))
                    else:
                        # Bomb! Lose points and combo
                        self.score = max(0, self.score - 10)
                        self.combo = 0
                        self.sounds.play('pop')  # Different sound
                        self.particles.emit(int(item.x), self.basket_y, (255, 0, 0), 20)
                        self.popups.append(ScorePopup(item.x, self.basket_y - 30, "-10"))
                elif item.is_powerup:
                    # Power-up! 2x multiplier
                    self.score_multiplier = 2.0
                    self.multiplier_timer = 300  # 5 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (255, 215, 0), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "2X!"))
                elif getattr(item, 'is_shield', False):
                    self.shield_active = True
                    self.shield_timer = 600  # 10 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (0, 200, 255), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "SHIELD!"))
                elif getattr(item, 'is_freeze', False):
                    self.slow_mo = True
                    self.slow_mo_timer = 300  # 5 seconds
                    self.sounds.play('level_complete')
                    self.particles.emit(int(item.x), self.basket_y, (100, 255, 255), 25)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, "FREEZE!"))
                else:
                    # Normal item caught — count as hit
                    points = int(15 * self.score_multiplier)
                    self.score += points
                    self.accuracy_hits += 1
                    self.accuracy_attempts += 1  # Count attempt only when item resolves
                    self.combo += 1
                    self.consecutive_misses = 0 # reset misses on hit
                    if self.combo > 0 and self.combo % 8 == 0:
                        self._adjust_pacing("fast")
                    self._trigger_feedback()
                    self.sounds.play('catch')
                    self.particles.emit(int(item.x), self.basket_y, COLOR_SUCCESS, 10)
                    self.popups.append(ScorePopup(item.x, self.basket_y - 30, f"+{points}"))
            
            elif item.y > WINDOW_HEIGHT:
                self.falling_items.remove(item)
                if not item.is_bomb and not item.is_powerup and not getattr(item, 'is_shield', False) and not getattr(item, 'is_freeze', False):
                    self.accuracy_attempts += 1  # Missed a catchable item
                    self.combo = 0  # Reset combo on miss (but not for bombs/powerups)
                    self.consecutive_misses += 1
                    if self.consecutive_misses >= 3:
                        self.consecutive_misses = 0
                        self._adjust_pacing("slow")
        
        # Spawn new items
        if len(self.falling_items) < 3 and random.random() < 0.02:
            self._spawn_falling_item()
        
        # End after 30 seconds
        if (time.time() - self.session_start > 30) or (time.time() - getattr(self, 'level_wall_start', 0.0) > LEVEL_DURATION * 1.5):
            self._end_level()
    
    def _update_level3(self, hand_data: HandData):
        """Level 3: Pinch & Drop (Fine Motor)"""
        # Update seeds
        for seed in self.seeds[:]:
            if not seed.grabbed:
                seed.y += seed.speed * getattr(self, 'pacing_multiplier', 1.0)
                
                # Check pinch grab
                if hand_data.is_pinching and hand_data.index_tip:
                    dist = distance(hand_data.index_tip, (seed.x, seed.y))
                    if dist < seed.radius + 35:  # Easier grab radius
                        seed.grabbed = True
                        self.accuracy_attempts += 1
            else:
                # Follow cursor
                if hand_data.index_tip:
                    seed.x = hand_data.index_tip[0]
                    seed.y = hand_data.index_tip[1]
                    
                    # Check drop in pot
                    if not hand_data.is_pinching:
                        pot_dist = distance((seed.x, seed.y), (self.pot_x, self.pot_y))
                        if pot_dist < 60:
                            points = int(25 * self.score_multiplier * (3 if seed.is_golden else 1))
                            self.score += points
                            self.accuracy_hits += 1
                            self.combo += 1
                            self.consecutive_misses = 0 # reset misses on pot success
                            if self.combo > 0 and self.combo % 6 == 0:
                                self._adjust_pacing("fast")
                            self._trigger_feedback()
                            self.sounds.play('catch')
                            color = (255, 215, 0) if seed.is_golden else COLOR_SUCCESS
                            self.particles.emit(self.pot_x, self.pot_y, color, 18 if seed.is_golden else 12)
                            self.popups.append(ScorePopup(self.pot_x, self.pot_y - 40, f"+{points}"))
                        else:
                            self.combo = 0  # Reset on miss
                        self.seeds.remove(seed)
            
            # Remove if off screen
            if seed.y > WINDOW_HEIGHT and not seed.grabbed:
                self.seeds.remove(seed)
                self.combo = 0 # Missed a seed
                self.consecutive_misses += 1
                if self.consecutive_misses >= 3:
                    self.consecutive_misses = 0
                    self._adjust_pacing("slow")
        
        # Spawn new seeds
        if len(self.seeds) < 2 and random.random() < 0.015:
            self._spawn_seed()
        
        # End after 30 seconds
        if (time.time() - self.session_start > 30) or (time.time() - getattr(self, 'level_wall_start', 0.0) > LEVEL_DURATION * 1.5):
            self._end_level()

    def _update_level4(self, hand_data: HandData):
        """Level 4: Tracing / Coordination (Hand Stability)"""
        # Time-based movement for the target (Figure 8 pattern)
        theme = self._get_theme()
        speed_mult = theme.get("speed_multiplier", 1.0)
        self.trace_t += 0.008 * speed_mult * getattr(self, 'pacing_multiplier', 1.0)
        
        # Figure 8 (Lissajous curve) parameters
        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        a = 180 # width scale (was 300)
        b = 90 # height scale (was 150)
        
        # Calculate target position
        self.trace_target_x = cx + a * math.sin(self.trace_t)
        self.trace_target_y = cy + b * math.sin(2 * self.trace_t)
        
        # Store path for drawing
        self.trace_path.append((self.trace_target_x, self.trace_target_y))
        if len(self.trace_path) > 100:
            self.trace_path.pop(0)
            
        # Check tracing accuracy
        if hand_data.index_tip:
            dist = distance(hand_data.index_tip, (self.trace_target_x, self.trace_target_y))
            
            # Record every few frames for accuracy
            if int(self.trace_t * 100) % 5 == 0:
                self.accuracy_attempts += 1
                self.recent_tracing_attempts += 1
                if dist < 85: # Good trace radius (was 60)
                    self.accuracy_hits += 1
                    self.recent_tracing_hits += 1
                    self.score += int(5 * self.score_multiplier)
                    
                    if dist < 45: # Perfect trace (was 30)
                        self.combo += 1
                        self.particles.emit(int(self.trace_target_x), int(self.trace_target_y), COLOR_SUCCESS, 2)
                else:
                    self.combo = 0 # Lost combo
                
                # Check dynamic pacing every 15 checks
                if self.recent_tracing_attempts >= 15:
                    ratio = self.recent_tracing_hits / self.recent_tracing_attempts
                    if ratio >= 0.85 and self.pacing_multiplier < 1.3:
                        self._adjust_pacing("fast")
                    elif ratio < 0.50 and self.pacing_multiplier > 0.6:
                        self._adjust_pacing("slow")
                    self.recent_tracing_attempts = 0
                    self.recent_tracing_hits = 0
            
            # Trigger feedback occasionally
            if self.combo > 0 and self.combo % 20 == 0 and int(self.trace_t * 100) % 5 == 0:
                self._trigger_feedback()
                self.sounds.play('catch')
                self.popups.append(ScorePopup(self.trace_target_x, self.trace_target_y - 40, "SMOOTH!"))
                
        # End after 30 seconds or wall-clock safety ceiling
        if (time.time() - self.session_start > 30) or (time.time() - getattr(self, 'level_wall_start', 0.0) > LEVEL_DURATION * 1.5):
            self._end_level()

    def _update_level5(self, hand_data: HandData):
        """Level 5: Grip & Release (Spasticity Pump)"""
        # Constantly deflate slowly (deflation rate adapts to pacing)
        if self.balloon_scale > 1.0:
            self.balloon_scale -= 0.005 * getattr(self, 'pacing_multiplier', 1.0)
            
        # If no rep completed for 8 seconds, slow down the deflation rate (make it easier)
        if not hasattr(self, 'last_rep_time'):
            self.last_rep_time = time.time()
            
        if hand_data.is_fist and self.pump_state == 0:
            self.pump_state = 1
            self.balloon_scale = max(0.5, self.balloon_scale - 0.2)
            self.sounds.play('catch')
        elif not hand_data.is_fist and hand_data.finger_extension > 120 and self.pump_state == 1:
            self.pump_state = 0
            self.pump_reps += 1
            self.accuracy_hits += 1
            self.accuracy_attempts += 1
            self.combo += 1
            self.last_rep_time = time.time() # Reset trigger timer on success
            if self.combo > 0 and self.combo % 3 == 0:
                self._adjust_pacing("fast")
            self.balloon_scale = min(2.0, self.balloon_scale + 0.5)
            self.score += int(15 * self.score_multiplier)
            self.sounds.play('pop')
            self.particles.emit(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2, COLOR_SUCCESS, 15)
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2 - 50, "+1 REP!"))
            
            if self.combo % 3 == 0:
                self._trigger_feedback()
                
        if time.time() - self.last_rep_time > 8.0:
            self.last_rep_time = time.time() # Reset trigger timer
            if self.pacing_multiplier > 0.6:
                self._adjust_pacing("slow")
                
        # End after 30 seconds
        if (time.time() - self.session_start > 30) or (time.time() - getattr(self, 'level_wall_start', 0.0) > LEVEL_DURATION * 1.5):
            self.accuracy_attempts = max(self.accuracy_attempts, 5) # Provide base attempts
            self._end_level()

    def _update_level6(self, hand_data: HandData):
        """Level 6: Memory Sequence (Cognitive Motor)"""
        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        pads = {
            1: (cx - 150, cy - 80),
            2: (cx + 150, cy - 80),
            3: (cx - 150, cy + 120),
            4: (cx + 150, cy + 120)
        }
        
        if self.simon_state == "START":
            self.simon_sequence = [random.randint(1, 4)]
            self.simon_state = "SHOW"
            self.simon_timer = time.time()
            self.simon_show_idx = 0
            self.simon_active_pad = None
            
        elif self.simon_state == "SHOW":
            t = time.time() - self.simon_timer
            # Every 1 second, show the next pad
            if t > 0.8:
                if self.simon_show_idx < len(self.simon_sequence):
                    self.simon_active_pad = self.simon_sequence[self.simon_show_idx]
                    self.sounds.play('pop')
                    self.simon_show_idx += 1
                    self.simon_timer = time.time()
                elif t > 1.2:
                    self.simon_active_pad = None
                    self.simon_state = "PLAY"
                    self.simon_player_idx = 0
                    self.popups.append(ScorePopup(cx, cy - 200, "YOUR TURN!", (0, 255, 255)))
            elif t > 0.4:
                self.simon_active_pad = None # brief pause between flashes
                
        elif self.simon_state == "PLAY":
            if not hand_data.index_tip: return
            hx, hy = hand_data.index_tip
            
            # Check collisions with pads
            hovered_pad = None
            for p_id, (px, py) in pads.items():
                if distance((hx, hy), (px, py)) < 75:
                    hovered_pad = p_id
                    break
                    
            if hovered_pad:
                if getattr(self, '_last_hover', None) != hovered_pad:
                    self._last_hover = hovered_pad
                    self._hover_start = time.time()
                elif time.time() - self._hover_start > 0.4: # 0.4s hover to select
                    self.simon_active_pad = hovered_pad
                    self.sounds.play('catch')
                    
                    if hovered_pad == self.simon_sequence[self.simon_player_idx]:
                        # Correct!
                        self.simon_player_idx += 1
                        self.accuracy_hits += 1
                        self.accuracy_attempts += 1
                        self.score += int(10 * self.score_multiplier)
                        self.particles.emit(pads[hovered_pad][0], pads[hovered_pad][1], COLOR_SUCCESS, 10)
                        
                        if self.simon_player_idx >= len(self.simon_sequence):
                            # Sequence complete!
                            self.popups.append(ScorePopup(cx, cy, "CORRECT!", COLOR_SUCCESS))
                            self.simon_sequence.append(random.randint(1, 4))
                            self.simon_state = "SHOW"
                            self.simon_timer = time.time() + 1.0 # Pause before showing next
                            self.simon_show_idx = 0
                            self.simon_active_pad = None
                            self.combo += 1
                            if self.combo % 2 == 0:
                                self._trigger_feedback()
                    else:
                        # Wrong!
                        self.accuracy_attempts += 1
                        self.popups.append(ScorePopup(cx, cy, "WRONG!", COLOR_WARNING))
                        self.simon_state = "START"
                        self.combo = 0
                    
                    self._last_hover = None
            else:
                self._last_hover = None
                self.simon_active_pad = None

        if (time.time() - self.session_start > 30) or (time.time() - getattr(self, 'level_wall_start', 0.0) > LEVEL_DURATION * 1.5):
            self.accuracy_attempts = max(self.accuracy_attempts, 5)
            self._end_level()

    def _draw_cyber_grid(self):
        """Moving background grid for technical feel"""
        scr = self.screen
        t = time.time()
        offset_y = int((t * 40) % 40)
        grid_col = (10, 25, 45)
        for y in range(-40, WINDOW_HEIGHT + 40, 40):
            pygame.draw.line(scr, grid_col, (0, y + offset_y), (GAME_AREA_WIDTH, y + offset_y), 1)
        for x in range(0, GAME_AREA_WIDTH + 40, 40):
            pygame.draw.line(scr, grid_col, (x, 0), (x, WINDOW_HEIGHT), 1)

    def _draw(self):
        self.screen.fill(COLOR_BG)
        pygame.draw.rect(self.screen, (12, 18, 30), (0, 0, GAME_AREA_WIDTH, WINDOW_HEIGHT))
        pygame.draw.line(self.screen, (35, 50, 68), (0, 72), (GAME_AREA_WIDTH, 72), 1)
            
        # Draw game area
        if self.state == GameState.PATIENT_REGISTRATION:
            self._draw_patient_registration()
        elif self.state == GameState.AGE_SELECT:
            self._draw_age_select()
        elif self.state == GameState.MAIN_MENU:
            self._draw_menu()
        elif self.state == GameState.PAIN_SCALE:
            self._draw_pain_scale()
        elif self.state == GameState.HISTORY:
            self._draw_history()
        elif self.state == GameState.CALIBRATION:
            self._draw_calibration()
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            self._draw_level1()
        elif self.state == GameState.LEVEL2_STRENGTH:
            self._draw_level2()
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            self._draw_level3()
        elif self.state == GameState.LEVEL4_COORDINATION:
            self._draw_level4()
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            self._draw_level5()
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            self._draw_level6()
        elif self.state == GameState.LEVEL_COMPLETE:
            self._draw_level_complete()
        elif self.state == GameState.RESULTS:
            self._draw_results()
        elif self.state == GameState.CLOUD_SYNC:
            self._draw_cloud_sync()
        elif self.state == GameState.THERAPIST_DASHBOARD:
            self._draw_therapist_dashboard()
        
        # Draw sidebar (not for full-screen states)
        _no_sidebar = [GameState.AGE_SELECT,
                       GameState.PATIENT_REGISTRATION, GameState.LEVEL_COMPLETE,
                       GameState.PAIN_SCALE, GameState.HISTORY, GameState.CLOUD_SYNC,
                       GameState.THERAPIST_DASHBOARD]
        if self.state not in _no_sidebar:
            hand_data = self.hand_engine.get_hand_data()
            camera_frame = self.hand_engine.get_frame()
            goals = self._get_level_goals()
            self.sidebar.draw(self.screen, camera_frame, hand_data, goals,
                              self.accuracy_hits, self.accuracy_attempts,
                              is_results=(self.state == GameState.RESULTS),
                              is_calibration=(self.state == GameState.CALIBRATION),
                              is_mirror_active=getattr(self, 'results_mirror_active', False),
                              is_paused=getattr(self, 'tracking_lost', False),
                              score=self.score,
                              exercise_name=self._get_current_exercise_name(),
                              exercise_count=self._get_exercise_count(),
                              session_elapsed=self._get_session_elapsed(),
                              pain_level=self.pain_level,
                              recovery_prediction=self._get_recovery_prediction(),
                              correctness_text=self._get_correctness_label(hand_data))

            # Draw progress chart over the bottom half of the sidebar on Results screen
            if self.state == GameState.RESULTS:
                self._draw_progress_chart()

            # Draw cursor
            self._draw_cursor(hand_data)

            # Draw home icon (gameplay only)
            if self.state not in [GameState.MAIN_MENU, GameState.RESULTS]:
                self.home_icon.draw(self.screen)
        
        # Draw particles and popups on top
        self.particles.draw(self.screen)
        for popup in self.popups:
            popup.draw(self.screen)
        
        # Draw live HUD bar (in gameplay states only)
        gameplay_states = [GameState.LEVEL1_FLEXIBILITY,
                           GameState.LEVEL2_STRENGTH,
                           GameState.LEVEL3_FINEMOTOR,
                           GameState.LEVEL4_COORDINATION,
                           GameState.LEVEL5_GRIP_RELEASE,
                           GameState.LEVEL6_FINGER_TAPS]
        if self.state in gameplay_states:
            hud_y = 8
            hud_h = 36
            hud_w = GAME_AREA_WIDTH - 20
            hud_rect = pygame.Rect(10, hud_y, hud_w, hud_h)

            # Semi-transparent HUD background
            hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
            hud_surf.fill((10, 15, 30, 200))
            self.screen.blit(hud_surf, (10, hud_y))
            pygame.draw.rect(self.screen, (0, 180, 220), hud_rect, 2, border_radius=8)

            hud_font = self.font_hud  # cached — no per-frame allocation

            # Tracking Lost Overlay (Pause / Ready)
            if getattr(self, 'tracking_lost', False):
                pause_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                pause_surf.fill((0, 0, 0, 200)) # Darker background
                self.screen.blit(pause_surf, (0, 0))
                
                # Draw MASSIVE neon pause/ready box
                box_w, box_h = 700, 250
                box_x = (GAME_AREA_WIDTH - box_w) // 2
                box_y = (WINDOW_HEIGHT - box_h) // 2
                box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
                
                has_started = getattr(self, 'game_has_started', False)
                
                # Determine colors and text based on whether the game has actually started
                if has_started:
                    border_outer_color = (255, 30, 60)   # Glowing warning red
                    border_inner_color = (255, 100, 100)
                    title_text = "SYSTEM PAUSED"
                    title_color = (255, 60, 60)
                    desc_text = "PLEASE RETURN HAND TO CAMERA VIEW"
                else:
                    border_outer_color = (0, 180, 255)   # Glowing cyber cyan
                    border_inner_color = (0, 255, 200)
                    title_text = "READY? SHOW HAND TO START"
                    title_color = (0, 220, 255)
                    desc_text = "POSITION INDEX FINGER IN CAMERA FRAME TO BEGIN"
                
                # Glowing border effect
                pygame.draw.rect(self.screen, border_outer_color, pygame.Rect(box_x-4, box_y-4, box_w+8, box_h+8), border_radius=20)
                pygame.draw.rect(self.screen, (20, 10, 15), box_rect, border_radius=15)
                pygame.draw.rect(self.screen, border_inner_color, box_rect, 4, border_radius=15)
                
                warn_text = self.font_medium.render(title_text, True, title_color)
                self.screen.blit(warn_text, warn_text.get_rect(center=(box_x + box_w//2, box_y + 80)))
                
                sub_text = self.font_small.render(desc_text, True, (255, 255, 255))
                self.screen.blit(sub_text, sub_text.get_rect(center=(box_x + box_w//2, box_y + 160)))

            # Score
            score_str = f"SCORE: {self.score}"
            sc = hud_font.render(score_str, True, (255, 255, 255))
            self.screen.blit(sc, (20, hud_y + 8))

            # Accuracy
            acc = (self.accuracy_hits / self.accuracy_attempts * 100) \
                  if self.accuracy_attempts > 0 else 0.0
            acc_color = (50, 220, 120) if acc >= 70 else \
                        (255, 180, 0)  if acc >= 40 else (220, 80, 80)
            acc_str = f"ACC: {acc:.0f}%"
            ac = hud_font.render(acc_str, True, acc_color)
            self.screen.blit(ac, (180, hud_y + 8))

            # Combo
            if self.combo > 1:
                combo_color = (255, 215, 0) if self.combo >= 5 else (255, 180, 60)
                co = hud_font.render(f"x{self.combo} COMBO", True, combo_color)
                self.screen.blit(co, (310, hud_y + 8))

            # Multiplier badge
            if self.score_multiplier > 1.0:
                mx = hud_font.render(f"{self.score_multiplier:.0f}x BOOST", True, (255, 100, 255))
                self.screen.blit(mx, (470, hud_y + 8))
        
        # Draw feedback text (center screen) — use cached font to avoid per-frame allocation
        if self.feedback_text and self.feedback_timer > 0:
            feedback_surf = self.font_large.render(self.feedback_text, True, COLOR_SUCCESS)
            feedback_rect = feedback_surf.get_rect(center=(GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 3))
            shadow = self.font_large.render(self.feedback_text, True, (0, 0, 0))
            self.screen.blit(shadow, shadow.get_rect(center=(GAME_AREA_WIDTH // 2 + 3, WINDOW_HEIGHT // 3 + 3)))
            self.screen.blit(feedback_surf, feedback_rect)
            
        # Draw correctness warning (top center)
        if getattr(self, 'correctness_warning', "") and getattr(self, 'state', None) in gameplay_states:
            c_color = (255, 100, 100) if "Bend" in self.correctness_warning else (100, 255, 100)
            warning_surf = self.font_hud.render(self.correctness_warning, True, c_color)
            warning_rect = warning_surf.get_rect(center=(GAME_AREA_WIDTH // 2, 70))
            shadow_warn = self.font_hud.render(self.correctness_warning, True, (0, 0, 0))
            self.screen.blit(shadow_warn, shadow_warn.get_rect(center=(GAME_AREA_WIDTH // 2 + 2, 72)))
            self.screen.blit(warning_surf, warning_rect)
        
        # Apply screen shake offset
        if self.shake_offset != (0, 0):
            # Create a temporary surface with the current screen
            temp_surf = self.screen.copy()
            self.screen.fill(COLOR_BG)
            self.screen.blit(temp_surf, self.shake_offset)
            
        # Draw Global Fist-Hold Exit Overlay
        if hasattr(self, '_global_fist_start') and self._global_fist_start is not None:
            elapsed = time.time() - self._global_fist_start
            progress = min(elapsed / 2.0, 1.0)
            if progress > 0.05:
                # Dim background
                dim_surf = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
                dim_surf.fill((10, 10, 20, 180))
                self.screen.blit(dim_surf, (0, 0))
                
                # Glowing center box
                box_w, box_h = 600, 300
                box_x = (WINDOW_WIDTH - box_w) // 2
                box_y = (WINDOW_HEIGHT - box_h) // 2
                pygame.draw.rect(self.screen, (20, 25, 45), (box_x, box_y, box_w, box_h), border_radius=20)
                pygame.draw.rect(self.screen, (255, 60, 100), (box_x, box_y, box_w, box_h), 4, border_radius=20)
                
                # Ring gauge in center of box
                cx = box_x + box_w // 2
                cy = box_y + box_h // 2 + 30
                radius = 50
                pygame.draw.circle(self.screen, (40, 45, 65), (cx, cy), radius, 8)
                
                start_a = math.radians(-90)
                end_a = math.radians(-90 + 360 * progress)
                arc_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.arc(arc_surf, (255, 60, 100), (0, 0, radius * 2, radius * 2), start_a, end_a, 10)
                self.screen.blit(arc_surf, (cx - radius, cy - radius))
                
                # Text inside ring
                rem = max(0.0, 2.0 - elapsed)
                cd_t = self.font_cd.render(f"{rem:.1f}s", True, (255, 255, 255))
                self.screen.blit(cd_t, cd_t.get_rect(center=(cx, cy)))
                
                # Heading
                h_t = self.font_medium.render("HOLDING FIST TO EXIT", True, (255, 60, 100))
                self.screen.blit(h_t, h_t.get_rect(center=(cx, box_y + 40)))
                sub_t = self.font_small.render("Keep hand closed to return to Main Menu", True, (180, 200, 220))
                self.screen.blit(sub_t, sub_t.get_rect(center=(cx, box_y + 85)))

        pygame.display.flip()
    
    def _draw_camera_preview(self, x, y, w, h, label="SYSTEM CAMERA"):
        """Draw live camera feed with a technical border"""
        with self.hand_engine.lock:
            frame = self.hand_engine.mirrored_frame
            if frame is not None:
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    f_h, f_w = frame_rgb.shape[:2]
                    frame_surf = pygame.image.frombuffer(frame_rgb.tobytes(), (f_w, f_h), "RGB")
                    scaled_surf = pygame.transform.scale(frame_surf, (w, h))
                    self.screen.blit(scaled_surf, (x, y))
                    
                    # Green Phosphor Tint for CRT look
                    tint = pygame.Surface((w, h), pygame.SRCALPHA)
                    tint.fill((0, 255, 120, 40))
                    self.screen.blit(tint, (x, y))
                except: pass
            else:
                pygame.draw.rect(self.screen, (10, 15, 25), (x, y, w, h))
                txt = self.font_tiny.render("CALIBRATING...", True, (60, 80, 100))
                self.screen.blit(txt, txt.get_rect(center=(x+w//2, y+h//2)))

        # Technical frame
        pygame.draw.rect(self.screen, (0, 200, 255), (x, y, w, h), 2, border_radius=4)
        pygame.draw.line(self.screen, (0, 255, 150), (x, y+h+5), (x+40, y+h+5), 2)
        lbl = self.font_tiny.render(label, True, (0, 255, 150))
        self.screen.blit(lbl, (x, y+h+10))
        
        # Flickering "REC" dot
        if int(time.time()*2) % 2 == 0:
            pygame.draw.circle(self.screen, (255, 50, 50), (x+w-15, y+15), 4)
    
    
    
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
        title = self.font_large.render("AI PHYSIOTHERAPY", True, primary)
        title_rect = title.get_rect(center=(GAME_AREA_WIDTH // 2, 60))
        
        # Soft Glow Behind Title
        glow = pygame.Surface((title_rect.width + 100, title_rect.height + 40), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (primary[0], primary[1], primary[2], 25), glow.get_rect())
        self.screen.blit(glow, glow.get_rect(center=(GAME_AREA_WIDTH // 2, 60)))
        
        # Drop Shadow
        shadow = self.font_large.render("AI PHYSIOTHERAPY", True, (0, 0, 0))
        self.screen.blit(shadow, shadow.get_rect(center=(GAME_AREA_WIDTH // 2 + 3, 63)))
        
        self.screen.blit(title, title_rect)

        # Theme name
        theme_surf = self.font_small.render(f"Theme: {theme['name']}", True, theme["accent_color"])
        theme_rect = theme_surf.get_rect(center=(GAME_AREA_WIDTH // 2, 108))
        self.screen.blit(theme_surf, theme_rect)

        # Welcome patient
        if self.patient_name:
            welcome = self.font_small.render(f"Welcome, {self.patient_name}!", True, COLOR_SUCCESS)
            welcome_rect = welcome.get_rect(center=(GAME_AREA_WIDTH // 2, 140))
            self.screen.blit(welcome, welcome_rect)

        # Update level button labels to theme names (emojis stripped for system font compatibility)
        level_names = [
            theme['level1_name'],
            theme['level2_name'],
            theme['level3_name'],
            theme.get('level4_name', 'Magic Trace'),
            theme.get('level5_name', 'Balloon Pump'),
            theme.get('level6_name', 'Piano Play'),
        ]
        for i, button in enumerate(self.level_buttons):
            if i < len(level_names):
                button.text = level_names[i]
            button.draw(self.screen, self.font_small)

        # Instructions
        inst = self.font_small.render("Hover your finger over a level to select", True, COLOR_TEXT)
        inst_rect = inst.get_rect(center=(GAME_AREA_WIDTH // 2, 605))
        self.screen.blit(inst, inst_rect)

        # History, Calibration, and Exit utility buttons
        self.history_button.draw(self.screen, self.font_small, base_col=(30, 80, 150), hov_col=(50, 120, 200))
        if hasattr(self, 'calibrate_button'):
            self.calibrate_button.draw(self.screen, self.font_small, base_col=(120, 60, 140), hov_col=(160, 80, 180))
        if hasattr(self, 'exit_button'):
            self.exit_button.draw(self.screen, self.font_small, base_col=(180, 40, 40), hov_col=(255, 60, 60))
    
    def _draw_level1(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level1_name']

        # Title (pushed down to clear HUD bar)
        title = self.font_medium.render(f"LEVEL 1: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))

        # Bubble counter
        total_bubbles = len(self.bubbles)
        remaining = sum(1 for b in self.bubbles if not b.popped)
        counter_text = self.font_hint.render(
            f"Bubbles: {remaining} / {total_bubbles}", True, (180, 210, 230))
        self.screen.blit(counter_text, (50, 115))

        # Dot row showing bubble status
        dot_x = 50
        dot_y = 142
        for bubble in self.bubbles:
            dot_color = primary if not bubble.popped else (50, 55, 75)
            pygame.draw.circle(self.screen, dot_color, (dot_x, dot_y), 6)
            pygame.draw.circle(self.screen, (255, 255, 255), (dot_x, dot_y), 6, 1)
            dot_x += 18

        # Bubbles
        for bubble in self.bubbles:
            if not bubble.popped:
                pygame.draw.circle(self.screen, bubble.color, (int(bubble.x), int(bubble.y)), bubble.radius)
                surf = pygame.Surface((bubble.radius*2, bubble.radius*2), pygame.SRCALPHA)
                pygame.draw.ellipse(surf, (255,255,255,90), (bubble.radius*0.4, bubble.radius*0.15, bubble.radius, bubble.radius*0.5))
                self.screen.blit(surf, (int(bubble.x) - bubble.radius, int(bubble.y) - bubble.radius))
                pygame.draw.circle(self.screen, primary, (int(bubble.x), int(bubble.y)), bubble.radius, 2)
    
    def _draw_level2(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level2_name']

        # Title pushed lower
        title = self.font_medium.render(f"LEVEL 2: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))

        # Timer bar lower
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        # Basket (theme-colored)
        basket_rect = pygame.Rect(int(self.basket_x - 75), self.basket_y, 150, 40)
        pygame.draw.rect(self.screen, theme["secondary_color"], basket_rect, border_radius=10)
        pygame.draw.rect(self.screen, primary, basket_rect, 3, border_radius=10)

        # Shield Effect
        if self.shield_active:
            pulse = int(5 * math.sin(time.time() * 10))
            shield_rect = basket_rect.copy()
            shield_rect.inflate_ip(20 + pulse, 20 + pulse)
            pygame.draw.ellipse(self.screen, (0, 200, 255), shield_rect, 3)
            # draw a faint inner fill via an alpha surface
            shield_surf = pygame.Surface((shield_rect.width, shield_rect.height), pygame.SRCALPHA)
            pygame.draw.ellipse(shield_surf, (0, 200, 255, 40), shield_surf.get_rect())
            self.screen.blit(shield_surf, shield_rect.topleft)

        # Freezing background tint
        if self.slow_mo:
            freeze_surf = pygame.Surface((GAME_AREA_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            freeze_surf.fill((100, 255, 255, 15))
            self.screen.blit(freeze_surf, (0, 0))

        # Falling items
        for item in self.falling_items:
            pygame.draw.circle(self.screen, item.color,
                             (int(item.x), int(item.y)), item.radius)
            pygame.draw.circle(self.screen, COLOR_TEXT,
                             (int(item.x), int(item.y)), item.radius, 2)
    
    def _draw_level3(self):
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme['level3_name']

        # Title pushed lower
        title = self.font_medium.render(f"LEVEL 3: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))

        # Timer bar lower
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        # Pot (theme-colored)
        pygame.draw.circle(self.screen, theme["secondary_color"], (self.pot_x, self.pot_y), 50)
        pygame.draw.circle(self.screen, primary, (self.pot_x, self.pot_y), 50, 3)

        # Seeds
        for seed in self.seeds:
            color = theme["accent_color"] if seed.grabbed else COLOR_SEED
            pygame.draw.circle(self.screen, color,
                             (int(seed.x), int(seed.y)), seed.radius)
            pygame.draw.circle(self.screen, COLOR_TEXT,
                             (int(seed.x), int(seed.y)), seed.radius, 2)
                             
    def _draw_level4(self):
        """Draw Tracing Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level4_name', 'Magic Trace')

        title = self.font_medium.render(f"LEVEL 4: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        
        # Draw the full Figure-8 guide path (static background)
        points = []
        for i in range(101):
            t = i * (math.pi * 2 / 100)
            px = cx + 180 * math.sin(t)
            py = cy + 90 * math.sin(2 * t)
            points.append((px, py))
            
        if len(points) > 1:
            pygame.draw.lines(self.screen, (30, 50, 70), False, points, 5)
            
        # Draw the recent path trail (active)
        if len(self.trace_path) > 1:
            pygame.draw.lines(self.screen, theme["secondary_color"], False, self.trace_path, 3)
            
        # Draw target
        pygame.draw.circle(self.screen, theme["accent_color"], (int(self.trace_target_x), int(self.trace_target_y)), 25)
        pygame.draw.circle(self.screen, (255, 255, 255), (int(self.trace_target_x), int(self.trace_target_y)), 10)
        
        inst = self.font_small.render("Keep your finger exactly on the moving target!", True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 200)))
        
    def _draw_level5(self):
        """Draw Grip & Release Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level5_name', 'Balloon Pump')

        title = self.font_medium.render(f"LEVEL 5: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # Timer bar
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx = GAME_AREA_WIDTH // 2
        cy = WINDOW_HEIGHT // 2 + 30
        
        # Draw balloon/core
        base_r = 80
        current_r = int(base_r * self.balloon_scale)
        
        color = theme["accent_color"] if self.pump_state == 0 else theme["secondary_color"]
        pygame.draw.circle(self.screen, color, (cx, cy), current_r)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), current_r, max(1, current_r // 15))
        
        # Reps text
        reps_text = self.font_large.render(str(self.pump_reps), True, (255, 255, 255))
        self.screen.blit(reps_text, reps_text.get_rect(center=(cx, cy)))
        
        inst_txt = "Make a FIST, then OPEN your hand fully!" if self.pump_state == 0 else "OPEN your hand wide!"
        inst = self.font_small.render(inst_txt, True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + current_r + 40)))
        
    def _draw_level6(self):
        """Draw Memory Sequence Level"""
        theme = self._get_theme()
        primary = theme["primary_color"]
        level_name = theme.get('level6_name', 'Memory Sequence')

        title = self.font_medium.render(f"LEVEL 6: {level_name}", True, primary)
        self.screen.blit(title, (50, 75))
        
        # Timer
        if self.session_start:
            elapsed = time.time() - self.session_start
            remaining = max(0, 1.0 - elapsed / LEVEL_DURATION)
            bar_w = GAME_AREA_WIDTH - 150
            bar_x = 50
            bar_y = 120
            pygame.draw.rect(self.screen, (40, 40, 50), (bar_x, bar_y, bar_w, 12), border_radius=6)
            r = int(255 * (1 - remaining))
            g = int(200 * remaining)
            bar_color = (r, g, int(200 * remaining))
            filled_w = int(bar_w * remaining)
            if filled_w > 0:
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, filled_w, 12), border_radius=6)
            time_text = self.font_small.render(f"{max(0, LEVEL_DURATION - int(elapsed))}s", True, COLOR_TEXT)
            self.screen.blit(time_text, (bar_x + bar_w + 10, bar_y - 5))

        cx, cy = GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2
        pads = {
            1: (cx - 150, cy - 80),
            2: (cx + 150, cy - 80),
            3: (cx - 150, cy + 120),
            4: (cx + 150, cy + 120)
        }
        pad_colors = {
            1: (255, 100, 100), # Red
            2: (100, 255, 100), # Green
            3: (100, 100, 255), # Blue
            4: (255, 255, 100)  # Yellow
        }
        
        for p_id, (px, py) in pads.items():
            col = pad_colors[p_id]
            is_active = (getattr(self, 'simon_active_pad', None) == p_id)
            is_hovering = (self.simon_state == "PLAY" and getattr(self, '_last_hover', None) == p_id)
            
            draw_col = col if is_active else tuple(int(c * 0.4) for c in col)
            r_size = 75 if is_active else 65
            if is_hovering and not is_active:
                draw_col = tuple(int(c * 0.7) for c in col)
                r_size = 70
                # Draw hover progress
                if hasattr(self, '_hover_start'):
                    prog = min(1.0, (time.time() - self._hover_start) / 0.4)
                    pygame.draw.arc(self.screen, (255,255,255), (px-80, py-80, 160, 160), math.pi/2, math.pi/2 + 2*math.pi*prog, 4)
            
            pygame.draw.circle(self.screen, draw_col, (px, py), r_size)
            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), r_size, 3)
            
        status = "WATCH CAREFULLY!" if self.simon_state == "SHOW" else "REPEAT SEQUENCE"
        if self.simon_state == "START": status = "GET READY"
        inst = self.font_medium.render(status, True, COLOR_TEXT)
        self.screen.blit(inst, inst.get_rect(center=(cx, cy + 240)))
        
        seq_len = max(0, len(self.simon_sequence) - 1) if self.simon_state == "START" else len(self.simon_sequence)
        score_t = self.font_small.render(f"Sequence Length: {seq_len}", True, (0, 255, 200))
        self.screen.blit(score_t, score_t.get_rect(center=(cx, cy - 200)))
    
    def _draw_cursor(self, hand_data: HandData):  # noqa
        if not hand_data.index_tip:
            return

        cx, cy = hand_data.index_tip
        t = time.time()

        # --- State-based colors ---
        if hand_data.is_fist:
            core_color   = (255, 140, 0)   # Orange = fist/pause
            ring_color   = (255, 180, 60)
            glow_color   = (255, 120, 0)
        elif hand_data.is_pinching:
            core_color   = (50, 255, 150)  # Green = pinching
            ring_color   = (100, 255, 180)
            glow_color   = (0, 200, 100)
        else:
            core_color   = (0, 200, 255)   # Cyan = normal point
            ring_color   = (80, 220, 255)
            glow_color   = (0, 150, 220)

        # --- Motion trail ---
        self._cursor_trail.append((cx, cy))
        if len(self._cursor_trail) > 12:
            self._cursor_trail.pop(0)

        for i, (tx, ty) in enumerate(self._cursor_trail[:-1]):
            alpha_factor = (i + 1) / len(self._cursor_trail)
            r = int(glow_color[0] * alpha_factor)
            g = int(glow_color[1] * alpha_factor)
            b = int(glow_color[2] * alpha_factor)
            trail_r = max(2, int(8 * alpha_factor))
            pygame.draw.circle(self.screen, (r, g, b), (tx, ty), trail_r)

        # --- Outer pulsing glow ring ---
        pulse = int(5 + 4 * math.sin(t * 5))
        pygame.draw.circle(self.screen, glow_color, (cx, cy), 22 + pulse, 2)

        # --- Mid ring ---
        pygame.draw.circle(self.screen, ring_color, (cx, cy), 18, 3)

        # --- Filled inner circle ---
        pygame.draw.circle(self.screen, core_color, (cx, cy), 12)

        # --- Bright white center dot ---
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 4)

        # --- Crosshair lines for precision ---
        line_len = 8
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx - line_len - 14, cy), (cx - 14, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx + 14, cy), (cx + line_len + 14, cy), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx, cy - line_len - 14), (cx, cy - 14), 2)
        pygame.draw.line(self.screen, (255, 255, 255),
                         (cx, cy + 14), (cx, cy + line_len + 14), 2)

        # --- Pinch line between thumb and index ---
        if hand_data.is_pinching and hand_data.thumb_tip:
            pygame.draw.line(self.screen, (50, 255, 150),
                             hand_data.index_tip, hand_data.thumb_tip, 3)
            # Small circle at thumb tip too
            pygame.draw.circle(self.screen, (50, 255, 150),
                               hand_data.thumb_tip, 8)
            pygame.draw.circle(self.screen, (255, 255, 255),
                               hand_data.thumb_tip, 3)
    
    def _spawn_bubbles(self):
        self.bubbles.clear()
        theme = self._get_theme()
        spd = theme["speed_multiplier"]
        sz = int(60 * theme["size_multiplier"])
        bubble_color = theme["primary_color"]

        positions = [
            (200, 200), (GAME_AREA_WIDTH - 200, 200),
            (200, WINDOW_HEIGHT - 150), (GAME_AREA_WIDTH - 200, WINDOW_HEIGHT - 150),
            (GAME_AREA_WIDTH // 2, WINDOW_HEIGHT // 2)
        ]
        for x, y in positions:
            is_golden = random.random() < 0.2  # 20% golden
            color = (255, 215, 0) if is_golden else bubble_color
            vx = random.uniform(-2, 2) * spd
            vy = random.uniform(-2, 2) * spd
            bubble = Bubble(x, y, sz, color)
            bubble.vx = vx
            bubble.vy = vy
            bubble.is_golden = is_golden
            self.bubbles.append(bubble)

    def _spawn_falling_item(self):
        theme = self._get_theme()
        spd = theme["speed_multiplier"]
        sz = int(25 * theme["size_multiplier"])

        x = random.randint(100, GAME_AREA_WIDTH - 100)
        y = -30

        rand = random.random()
        if rand < 0.15:  # 15% bombs
            item = FallingItem(x, y, sz, 3 * spd, (255, 50, 50))
            item.is_bomb = True
        elif rand < 0.20:  # 5% 2x power-ups
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (255, 215, 0))
            item.is_powerup = True
        elif rand < 0.25:  # 5% shields
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (0, 200, 255))
            item.is_shield = True
        elif rand < 0.30:  # 5% freeze
            item = FallingItem(x, y, int(sz * 0.8), 2.5 * spd, (100, 255, 255))
            item.is_freeze = True
        else:  # 70% normal
            item = FallingItem(x, y, sz, 3 * spd, theme["secondary_color"])

        self.falling_items.append(item)

    def _spawn_seed(self):
        theme = self._get_theme()
        spd = theme["speed_multiplier"]
        sz = int(18 * theme["size_multiplier"])

        x = random.randint(100, GAME_AREA_WIDTH - 100)
        y = -30
        is_golden = random.random() < 0.25  # 25% golden
        seed = Seed(x, y, sz, 2.5 * spd, False)
        seed.is_golden = is_golden
        self.seeds.append(seed)
    
    def _get_level_goals(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Select a level to begin rehabilitation"
        elif self.state == GameState.LEVEL1_FLEXIBILITY:
            return "Pop all bubbles in corners to test flexibility and reach"
        elif self.state == GameState.LEVEL2_STRENGTH:
            return "Move palm to catch falling items. Build strength!"
        elif self.state == GameState.LEVEL3_FINEMOTOR:
            return "Pinch seeds and drop them in the pot. Fine motor control!"
        elif self.state == GameState.LEVEL4_COORDINATION:
            return "Follow the moving target smoothly to test hand stability!"
        elif self.state == GameState.LEVEL5_GRIP_RELEASE:
            return "Make a FIST, then OPEN fully to pump the object!"
        elif self.state == GameState.LEVEL6_FINGER_TAPS:
            return "Memorize the pattern and repeat it!"
        return ""

    def _get_current_exercise_name(self) -> str:
        if self.state == GameState.MAIN_MENU:
            return "Therapy Selection"
        if self.state == GameState.CALIBRATION:
            return "ROM Diagnostics"
        return LEVEL_DISPLAY_NAMES.get(getattr(self, "current_level", 0), "Therapeutic Training")

    def _get_exercise_count(self) -> int:
        if getattr(self, "current_level", 0) == 5:
            return int(getattr(self, "pump_reps", 0))
        return int(getattr(self, "accuracy_hits", 0))

    def _get_session_elapsed(self) -> float:
        if self.session_start:
            return max(0.0, time.time() - self.session_start)
        return 0.0

    def _get_correctness_label(self, hand_data: HandData) -> str:
        warning = getattr(self, "correctness_warning", "")
        if warning:
            if "Bend" in warning:
                return "Incorrect - adjust movement"
            return "Correct - good control"
        if hand_data.index_tip is None:
            return "Incorrect - hand missing"
        return "Ready - tracking hand"

    def _get_recovery_prediction(self) -> Optional[float]:
        now = time.time()
        cache_time = getattr(self, "_recovery_prediction_time", 0.0)
        if now - cache_time > 5.0:
            try:
                self._recovery_prediction_cache = self.db.predict_recovery_progress(self.patient_name)
            except Exception:
                self._recovery_prediction_cache = -1.0
            self._recovery_prediction_time = now
        return getattr(self, "_recovery_prediction_cache", -1.0)
    
    def _end_level(self):
        try:
            duration = time.time() - self.session_start
            avg_accuracy = (self.accuracy_hits / self.accuracy_attempts * 100) if self.accuracy_attempts > 0 else 0

            avg_hand_angle = sum(self.angle_history) / len(self.angle_history) if len(self.angle_history) > 0 else 0

            self.db.save_session(
                self.current_level, self.score, duration,
                avg_accuracy, self.max_extension,
                self.reach_distance, avg_hand_angle,
                pain_level=self.pain_level, patient_id=self.patient_name
            )

            self.session_data = self.db.get_last_session()
            if not self.session_data:
                self.session_data = {
                    'level': self.current_level,
                    'score': self.score,
                    'duration': duration,
                    'avg_accuracy': avg_accuracy,
                    'max_extension': self.max_extension,
                    'reach_distance': self.reach_distance,
                    'avg_hand_angle': avg_hand_angle
                }
            self.best_data    = self.db.get_all_time_best()
            
            # Generate Session Charts (Pie/Histogram)
            self.summary_screen.generate_session_charts(
                self.accuracy_hits, self.accuracy_attempts, list(self.angle_history)
            )

            # Auto-save text, HTML, and PDF reports
            try:
                import os
                os.makedirs("reports", exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                sd = self.session_data or {}
                
                # 1. Text Report Card
                fname = f"reports/report_L{self.current_level}_{ts}.txt"
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(f"AI Hand Rehabilitation — Session Report\n")
                    f.write(f"{'='*45}\n")
                    f.write(f"Patient  : {self.patient_name or 'Unknown'}\n")
                    f.write(f"Date     : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
                    f.write(f"Level    : {self.current_level}\n")
                    f.write(f"Pain NRS : {self.pain_level}/10\n")
                    f.write(f"\n-- Performance --\n")
                    f.write(f"Score    : {sd.get('score', self.score)}\n")
                    f.write(f"Accuracy : {sd.get('avg_accuracy', 0):.1f}%\n")
                    f.write(f"ROM Angle: {sd.get('avg_hand_angle', 0):.1f}°\n")
                    f.write(f"Duration : {sd.get('duration', 0):.0f}s\n")
                    f.write(f"\n-- All-Time Best --\n")
                    bd = self.best_data or {}
                    f.write(f"Best Score   : {bd.get('score', 0)}\n")
                    f.write(f"Best Accuracy: {bd.get('accuracy', 0):.1f}%\n")
                    f.write(f"Best ROM     : {bd.get('angle', 0):.1f}°\n")
                print(f"Text Report saved: {fname}")

                # 2. Premium Clinical HTML Report Card
                html_fname = f"reports/session_report_L{self.current_level}_{ts}.html"
                
                LEVEL_NAMES = [
                    "Flexibility - Pop the Bubbles",
                    "Flexibility - Pop the Bubbles", 
                    "Strength & Speed - Catch the Apples", 
                    "Fine Motor - Plant the Seeds", 
                    "Coordination - Trace the Path", 
                    "Grip & Release - Balloon Pump", 
                    "Cognitive Precision - Simon Pattern Tap"
                ]
                level_name_str = LEVEL_NAMES[self.current_level] if self.current_level < len(LEVEL_NAMES) else "Therapeutic Training"
                
                acc_val = sd.get('avg_accuracy', 0)
                rom_val = sd.get('avg_hand_angle', 0)
                dur_val = sd.get('duration', 0)
                
                suggestions_list = []
                if acc_val >= 85:
                    suggestions_list.append("Patient demonstrated exceptional target accuracy. Recommend advancing to the next difficulty tier or level.")
                elif acc_val >= 60:
                    suggestions_list.append("Good neuromuscular accuracy. Continue with the current protocol to build muscle memory and control.")
                else:
                    suggestions_list.append("Target accuracy is low. Encourage slower, more deliberate hand movements. Consider a pediatric or senior mode to expand target radii.")

                if rom_val >= 45:
                    suggestions_list.append("Average finger flexion is excellent, showing deep range of motion. Joint flexibility is healthy.")
                else:
                    suggestions_list.append("Reduced range of motion (ROM) detected. Incorporate warm-up finger stretching exercises before sessions.")

                if self.pain_level >= 5:
                    suggestions_list.append("WARNING: High patient pain level reported. Shorten session duration, encourage regular pauses, and consult with the attending therapist.")
                else:
                    suggestions_list.append("Patient reported minimal pain during this session. Good tolerability of the motor exercises.")
                
                suggestions_html = "\n".join([f"<li>{s}</li>" for s in suggestions_list])
                
                html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Therapy Session Report - L{self.current_level}</title>
    <style>
        :root {{
            --bg-color: #080c16;
            --card-bg: rgba(13, 22, 42, 0.7);
            --border-color: rgba(0, 255, 204, 0.2);
            --accent-glow: #00ffcc;
            --accent-blue: #0088ff;
            --text-primary: #ffffff;
            --text-secondary: #8fa0c0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .report-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 800px;
            box-shadow: 0 8px 32px 0 rgba(0, 255, 204, 0.08);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            position: relative;
            overflow: hidden;
        }}
        .report-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-blue), var(--accent-glow));
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(143, 160, 192, 0.15);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 1px;
            background: linear-gradient(90deg, #ffffff, var(--accent-glow));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header-meta {{
            text-align: right;
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .patient-info {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .info-item {{
            display: flex;
            flex-direction: column;
        }}
        .info-label {{
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }}
        .info-value {{
            font-size: 18px;
            font-weight: 600;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 35px;
        }}
        .metric-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 25px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .metric-details h3 {{
            margin: 0 0 5px 0;
            font-size: 14px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}
        .metric-details .value {{
            font-size: 28px;
            font-weight: 700;
            color: var(--accent-glow);
        }}
        .radial-indicator {{
            position: relative;
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: conic-gradient(var(--accent-glow) {acc_val}%, rgba(255, 255, 255, 0.08) 0);
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .radial-indicator::after {{
            content: '{acc_val:.1f}%';
            position: absolute;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: #0d162a;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 600;
        }}
        .clinical-suggestions {{
            background: rgba(0, 255, 204, 0.04);
            border: 1px dashed var(--border-color);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
        }}
        .clinical-suggestions h2 {{
            margin-top: 0;
            font-size: 18px;
            color: var(--accent-glow);
            letter-spacing: 0.5px;
        }}
        .clinical-suggestions ul {{
            margin: 0;
            padding-left: 20px;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        .clinical-suggestions li {{
            margin-bottom: 8px;
        }}
        .footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 12px;
            border-top: 1px solid rgba(143, 160, 192, 0.15);
            padding-top: 20px;
        }}
        @media print {{
            body {{
                background: #fff;
                color: #000;
                padding: 0;
            }}
            .report-card {{
                border: none;
                box-shadow: none;
                background: none;
                padding: 0;
                backdrop-filter: none;
            }}
            .report-card::before {{
                display: none;
            }}
            .metric-card, .patient-info {{
                border: 1px solid #ddd;
                background: #fff;
                color: #000;
            }}
            .metric-details .value {{
                color: #000;
            }}
            .radial-indicator::after {{
                background: #fff;
                color: #000;
            }}
        }}
    </style>
</head>
<body>
    <div class="report-card">
        <div class="header">
            <div>
                <h1>CLINICAL THERAPY REPORT</h1>
                <span style="color: var(--accent-glow); font-size: 12px; letter-spacing: 2px;">NEURAL BIO-FEEDBACK SUITE</span>
            </div>
            <div class="header-meta">
                <div>SESSION TIMESTAMP</div>
                <div>{datetime.now().strftime('%d %B %Y %H:%M')}</div>
            </div>
        </div>

        <div class="patient-info">
            <div class="info-item">
                <span class="info-label">Patient Name</span>
                <span class="info-value">{self.patient_name or 'Unknown'}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Demographic</span>
                <span class="info-value">{self.age_group.value if self.age_group else 'Adult'} (Age {self.patient_age or '30'})</span>
            </div>
            <div class="info-item">
                <span class="info-label">Therapy Protocol</span>
                <span class="info-value">Level {self.current_level} - {level_name_str}</span>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Performance Score</h3>
                    <div class="value">{sd.get('score', self.score)}</div>
                </div>
                <div style="font-size: 24px;">🏆</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Target Accuracy</h3>
                    <div class="value">{acc_val:.1f}%</div>
                </div>
                <div class="radial-indicator"></div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Range of Motion (ROM)</h3>
                    <div class="value">{rom_val:.1f}°</div>
                </div>
                <div style="font-size: 24px; color: var(--accent-glow);">📐</div>
            </div>
            <div class="metric-card">
                <div class="metric-details">
                    <h3>Pre-Session Pain / Time</h3>
                    <div class="value">{self.pain_level}/10 <span style="font-size: 16px; font-weight: normal; color: var(--text-secondary);">({dur_val:.0f}s)</span></div>
                </div>
                <div style="font-size: 24px;">⚡</div>
            </div>
        </div>

        <div class="clinical-suggestions">
            <h2>CLINICAL OBSERVATIONS & SUGGESTIONS</h2>
            <ul>
                {suggestions_html}
            </ul>
        </div>

        <div class="footer">
            Generated by Zero-Keyboard AI Hand Rehabilitation System | Confidential Medical Record
        </div>
    </div>
</body>
</html>"""
                with open(html_fname, "w", encoding="utf-8") as f:
                    f.write(html_template)
                print(f"HTML Report saved: {html_fname}")
                VOICE.speak("Clinical report exported to reports folder.")
                
                # 3. PDF Generation (with fixed imports and variables)
                try:
                    from reportlab.pdfgen import canvas
                    from reportlab.lib.pagesizes import letter
                    pdf_fname = f"reports/report_L{self.current_level}_{ts}.pdf"
                    c = canvas.Canvas(pdf_fname, pagesize=letter)
                    c.setFont("Helvetica-Bold", 24)
                    c.setFillColorRGB(0, 0.4, 0.6)
                    c.drawString(50, 750, "AI Hand Rehabilitation - Clinical Report")
                    
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(50, 710, f"Patient Name: {self.patient_name or 'Unknown'}")
                    c.drawString(50, 690, f"Date: {datetime.now().strftime('%d %B %Y  %H:%M')}")
                    c.drawString(50, 670, f"Diagnostic Level: {self.current_level}")
                    c.drawString(50, 650, f"Pre-Session Pain NRS: {self.pain_level}/10")
                    
                    c.setFont("Helvetica-Bold", 16)
                    c.setFillColorRGB(0, 0.3, 0.5)
                    c.drawString(50, 610, "Session Telemetry")
                    
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0, 0, 0)
                    c.drawString(50, 580, f"Final Score: {sd.get('score', self.score)}")
                    c.drawString(50, 560, f"Target Accuracy: {acc_val:.1f}%")
                    c.drawString(50, 540, f"Average Range of Motion: {rom_val:.1f} degrees")
                    c.drawString(50, 520, f"Therapy Duration: {dur_val:.0f} seconds")
                    
                    c.save()
                    print(f"PDF Report saved: {pdf_fname}")
                except Exception as pdf_e:
                    print(f"PDF save warning: {pdf_e}")
                    
            except Exception as re:
                print(f"Report save warning: {re}")

            # Big celebration burst

            cx = GAME_AREA_WIDTH // 2
            for _ in range(5):
                self.particles.emit(cx + random.randint(-200, 200),
                                    WINDOW_HEIGHT // 2,
                                    random.choice([(255,215,0),(0,220,120),(0,200,255),(255,100,150)]),
                                    30)

            # Go to LEVEL_COMPLETE celebration screen first
            self._level_complete_time = time.time()
            self.state = GameState.LEVEL_COMPLETE
            self.sounds.play('level_complete')
            self.screen_shake = 25

        except Exception as e:
            print(f"Error in _end_level: {e}")
            self.state = GameState.MAIN_MENU
            self._reset_game()


    
    def _run_virtual_sensei(self, hand_data: HandData):
        """AI-driven therapeutic coaching"""
        if self.state not in [GameState.LEVEL1_FLEXIBILITY, GameState.LEVEL2_STRENGTH, GameState.LEVEL3_FINEMOTOR, GameState.LEVEL4_COORDINATION, GameState.LEVEL5_GRIP_RELEASE, GameState.LEVEL6_FINGER_TAPS]:
            return
            
        now = time.time()
        if now - self.last_coach_time < self.coaching_cooldown:
            return
            
        # 1. Performance Feedback
        accuracy = (self.accuracy_hits / self.accuracy_attempts * 100) if self.accuracy_attempts > 0 else 100
        
        # Check for poor ROM
        if hand_data.finger_extension > 0 and hand_data.finger_extension < 120:
            VOICE.speak("Try to open your hand fully to improve range of motion.")
            self.last_coach_time = now
            return

        # Check for poor accuracy
        if self.accuracy_attempts > 10 and accuracy < 50:
            VOICE.speak("Slow down and focus on the center of the targets.")
            self.last_coach_time = now
            return

        # Check for great performance (encouragement)
        if self.combo > 8:
            VOICE.speak("Excellent control! Your motor precision is improving.")
            self.last_coach_time = now
            return

        # Check for steady progress
        if now - self.session_start > 20:
            VOICE.speak("Stay focused. You are doing a great job today.")
            self.last_coach_time = now

    def _reset_game(self):
        self.bubbles.clear()
        self.falling_items.clear()
        self.seeds.clear()
        self.score = 0
        self.max_extension = 0
        self.reach_distance = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.angle_history.clear()
        self.combo = 0
        self.feedback_text = None
        self.feedback_timer = 0
    
    def _trigger_feedback(self):
        """Trigger visual feedback based on combo"""
        if self.combo >= 15 and "combo15" not in self.achievements_unlocked:
            self.achievements_unlocked.add("combo15")
            self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, 120, "ACHIEVEMENT: 15 COMBO!"))
            self.sounds.play('level_complete')
            
        if self.combo >= 10:
            if "combo10" not in self.achievements_unlocked:
                self.achievements_unlocked.add("combo10")
                self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, 120, "ACHIEVEMENT: 10 COMBO!"))
                self.sounds.play('level_complete')
            self.feedback_text = "AMAZING!"
            self.feedback_timer = 60
        elif self.combo >= 7:
            self.feedback_text = "EXCELLENT!"
            self.feedback_timer = 50
        elif self.combo >= 4:
            self.feedback_text = "GREAT!"
            self.feedback_timer = 40
            self.sounds.play('combo')
        elif self.combo >= 2:
            self.feedback_text = "GOOD!"
            self.feedback_timer = 30
            
    def _adjust_pacing(self, change_type: str):
        """Dynamic pacing adjustment with sound cues and visual popup HUD alerts."""
        now = time.time()
        should_speak = (now - getattr(self, 'last_pacing_voice_time', 0.0)) > 10.0

        if change_type == "slow":
            self.pacing_multiplier = max(0.5, self.pacing_multiplier - 0.15)
            self.sounds.play('select')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 80, WINDOW_HEIGHT // 2, "PACING: SLOWER", (255, 128, 0)))
            if should_speak:
                VOICE.speak("Pacing adjusted. Let's take it slow and steady.")
                self.last_pacing_voice_time = now
        elif change_type == "fast":
            self.pacing_multiplier = min(1.4, self.pacing_multiplier + 0.1)
            self.sounds.play('level_complete')
            self.popups.append(ScorePopup(GAME_AREA_WIDTH // 2 - 80, WINDOW_HEIGHT // 2, "PACING: FASTER!", COLOR_SUCCESS))
            if should_speak:
                VOICE.speak("Excellent coordination! Pacing up slightly.")
                self.last_pacing_voice_time = now
    
    def _update_results(self, hand_data: HandData):
        """Update results screen"""
        # Debounce safeguard for hand lost tracking in results screen
        if hand_data.index_tip is None:
            if not hasattr(self, '_results_lost_t') or self._results_lost_t is None:
                self._results_lost_t = time.time()
            if time.time() - self._results_lost_t > 0.8:
                self.results_mirror_active = True
        else:
            self._results_lost_t = None
            self.results_mirror_active = False

        if self.close_button.update(hand_data.index_tip):
            self.running = False
        
        # PLAY AGAIN
        if self.menu_button.update(hand_data.index_tip):
            # Replay current level
            self.pending_level = self.current_level
            self._reset_game()
            self._start_level()
            self.sounds.play('select')
        
        # MAIN MENU (Via Cloud Sync)
        if self.home_button.update(hand_data.index_tip):
            self.state = GameState.CLOUD_SYNC
            self.sync_start = time.time()
            self.sounds.play('select')
            self.home_button.hover_start = None
            self.menu_button.hover_start = None
            self.close_button.hover_start = None
            if hasattr(self, 'next_button'):
                self.next_button.hover_start = None
                
        # NEXT GAME
        if hasattr(self, 'next_button') and getattr(self, 'current_level', 1) < 6 and self.next_button.update(hand_data.index_tip):
            self.pending_level = min(6, self.current_level + 1)
            self.sounds.play('select')
            self.menu_button.hover_start = None
            self.close_button.hover_start = None
            self.next_button.hover_start = None
            self.home_button.hover_start = None
            if not getattr(self, 'pain_checked', False):
                self.pain_level = 0
                self.state = GameState.PAIN_SCALE
            else:
                self._start_level()

    # ── Pain scale helpers ──────────────────────────────────────────────
    def _start_level(self):
        """Actually start the pending level after pain score captured"""
        self.game_has_started = False
        lv = self.pending_level or 1
        self.current_level = lv
        self.session_start = time.time()
        self.level_wall_start = time.time()
        self.score = 0
        self.max_extension = 0
        self.reach_distance = 0
        self.accuracy_hits = 0
        self.accuracy_attempts = 0
        self.pacing_multiplier = 1.0
        self.consecutive_misses = 0
        self.last_pacing_voice_time = 0.0
        self.recent_tracing_attempts = 0
        self.recent_tracing_hits = 0
        if lv == 1:
            self.state = GameState.LEVEL1_FLEXIBILITY
            self._spawn_bubbles()
            VOICE.speak("Level 1: Bubble Pop. Extend your index finger and touch the moving bubbles to pop them and improve flexibility.")
        elif lv == 2:
            self.state = GameState.LEVEL2_STRENGTH
            VOICE.speak("Level 2: Fruit Catch. Move your hand left and right to catch the falling apples in the basket.")
        elif lv == 3:
            self.state = GameState.LEVEL3_FINEMOTOR
            VOICE.speak("Level 3: Fine Motor. Close your index and thumb to pinch and pick up seeds, then drop them in the pot.")
        elif lv == 4:
            self.state = GameState.LEVEL4_COORDINATION
            self.trace_t = 0.0
            self.trace_path = []
            VOICE.speak("Level 4: Trace the Path. Move your index finger along the dotted line to trace the medical pattern.")
        elif lv == 5:
            self.state = GameState.LEVEL5_GRIP_RELEASE
            self.pump_state = 0
            self.pump_reps = 0
            self.balloon_scale = 1.0
            VOICE.speak("Level 5: Balloon Pump. Close your hand into a fist, then open it fully to pump up the balloon.")
        elif lv == 6:
            self.state = GameState.LEVEL6_FINGER_TAPS
            self.simon_sequence = []
            self.simon_state = "START"
            VOICE.speak("Level 6: Pattern Tap. Memorize the blinking pattern, then hover over the colored pads in correct order.")
        self.sounds.play('select')
        self.popups.append(ScorePopup(GAME_AREA_WIDTH//2, WINDOW_HEIGHT//2 - 60, "POSTURE FIX: Sit up & keep shoulders relaxed!"))


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
                    self.pain_level = i
                    self.pain_checked = True
                    self._start_level()
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
                        self.pain_level = i
                        self.pain_checked = True
                        self._start_level()
                    return

        # No dot hovered
        if hasattr(self, '_pain_hover'):
            del self._pain_hover
            del self._pain_hover_t

    def _draw_pain_scale(self):
        """Full-screen NRS 0-10 pain scale with visual indicators"""
        t  = time.time()
        cy = WINDOW_HEIGHT // 2
        cx = WINDOW_WIDTH  // 2

        self.screen.fill((8, 14, 30))

        # Header
        pygame.draw.rect(self.screen, (15, 25, 55),
                         pygame.Rect(0, 0, WINDOW_WIDTH, 80))
        h1 = self.font_large.render("Pain Level Assessment", True, (0, 200, 255))
        self.screen.blit(h1, h1.get_rect(center=(cx, 40)))

        sub = self.font_small.render(
            "Hover your finger over a number to rate your current pain  (0 = No Pain   10 = Worst Pain)",
            True, (130, 160, 200))
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
            if hasattr(self, 'next_button') and getattr(self, 'current_level', 1) < 6:
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
        global LEVEL_DURATION
        if not hasattr(self, 'admin_back_button'):
            self.admin_back_button = LevelButton(50, 150, 250, 80, "EXIT ADMIN", 0)
            self.admin_purge_button = LevelButton(50, 270, 350, 80, "PURGE ALL PATIENT DATA", 99)
            self.admin_timer_button = LevelButton(50, 390, 350, 80, f"LEVEL DURATION: {LEVEL_DURATION}s", 88)
            
        if self.admin_purge_button.update(hand_data.index_tip):
            try:
                self.db.cursor.execute("DELETE FROM sessions")
                self.db.conn.commit()
                self.sounds.play('level_complete')
            except: pass
            
        if self.admin_timer_button.update(hand_data.index_tip):
            LEVEL_DURATION = 60 if LEVEL_DURATION == 30 else 30
            self.admin_timer_button.text = f"LEVEL DURATION: {LEVEL_DURATION}s"
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
