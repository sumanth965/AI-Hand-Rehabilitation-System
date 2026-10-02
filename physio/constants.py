"""
Constants & Configuration for the Zero-Keyboard AI Physiotherapy System.
"""

WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
GAME_AREA_WIDTH = int(WINDOW_WIDTH * 0.75)  # 960px
SIDEBAR_WIDTH = WINDOW_WIDTH - GAME_AREA_WIDTH  # 320px
FPS = 60

# Colors
COLOR_BG = (15, 15, 25)
COLOR_SIDEBAR_BG = (12, 18, 30)
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
COLOR_MED_TEXT = (220, 235, 248)
COLOR_MED_MUTED = (130, 170, 205)
COLOR_MED_PANEL = (20, 28, 45)
COLOR_MED_PRIMARY = (0, 180, 220)
COLOR_MED_SUCCESS = (50, 230, 140)
COLOR_MED_WARNING = (255, 190, 40)

LEVEL_DISPLAY_NAMES = {
    1: "Flexibility Training",
    2: "Strength Coordination",
    3: "Fine Motor Pinch",
    4: "Path Tracing Control",
    5: "Grip Release Cycle",
    6: "Cognitive Finger Taps",
    7: "Forearm Rotation Orbit",
    8: "Smart Functional Assembly",
    9: "Precision Path - Dots",
    10: "Precision Pathway",
    11: "In-Hand Manipulation - Coin Vault",
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
        "level7_name": "Rotation Orbit",
        "level8_name": "Toy Builder",
        "level9_name": "Star Connect",
        "level10_name": "Rainbow Pathway",
        "level11_name": "Treasure Vault",
        "level1_icon": "🦋",
        "level2_icon": "🌻",
        "level3_icon": "🌱",
        "level4_icon": "✨",
        "level5_icon": "🎈",
        "level6_icon": "🧠",
        "level7_icon": "🪐",
        "level8_icon": "🧱",
        "level9_icon": "⭐",
        "level10_icon": "🌈",
        "level11_icon": "🪙",
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
        "level7_name": "Galaxy Spin",
        "level8_name": "Mech Assembly",
        "level9_name": "Matrix Nodes",
        "level10_name": "Laser Corridor",
        "level11_name": "Cyber Vault",
        "level1_icon": "⚡",
        "level2_icon": "🎯",
        "level3_icon": "🔮",
        "level4_icon": "⚡",
        "level5_icon": "🔋",
        "level6_icon": "🧩",
        "level7_icon": "🛰️",
        "level8_icon": "🔧",
        "level9_icon": "💠",
        "level10_icon": "⚡",
        "level11_icon": "🪙",
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
        "level7_name": "Orbital Path",
        "level8_name": "Stone Builder",
        "level9_name": "Precision Dots",
        "level10_name": "Zen Pathway",
        "level11_name": "Coin Vault",
        "level1_icon": "🍃",
        "level2_icon": "💧",
        "level3_icon": "🪨",
        "level4_icon": "〰️",
        "level5_icon": "🌬️",
        "level6_icon": "👣",
        "level7_icon": "🌎",
        "level8_icon": "🧱",
        "level9_icon": "🎯",
        "level10_icon": "〰️",
        "level11_icon": "🪙",
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
        "level7_name": "Moon Orbit",
        "level8_name": "Birdhouse",
        "level9_name": "Memory Dots",
        "level10_name": "Gentle Trail",
        "level11_name": "Coin Sorter",
        "level1_icon": "🌺",
        "level2_icon": "🎵",
        "level3_icon": "🧩",
        "level4_icon": "🖌️",
        "level5_icon": "❤️",
        "level6_icon": "🧠",
        "level7_icon": "🌕",
        "level8_icon": "🏠",
        "level9_icon": "🎨",
        "level10_icon": "🌿",
        "level11_icon": "🪙",
        "speed_multiplier": 0.8,  # Slower
        "size_multiplier": 1.2,   # Bigger targets
    }
}
