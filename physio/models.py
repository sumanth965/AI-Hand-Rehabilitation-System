"""
Enums and Data Classes for the Zero-Keyboard AI Physiotherapy System.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List


class GameState(Enum):
    PATIENT_REGISTRATION = -2
    AGE_SELECT = -1
    MAIN_MENU = 0
    LEVEL_SELECT = 1
    SETTINGS = 2
    PROGRESS = 3
    PAIN_SCALE = 4       # ← NEW: pain 0-10 before session
    HISTORY = 5          # ← NEW: full session history screen
    PAIN_AFTER_SESSION = 6
    LEVEL1_FLEXIBILITY = 10
    LEVEL2_STRENGTH = 11
    LEVEL3_FINEMOTOR = 12
    LEVEL4_COORDINATION = 13
    LEVEL5_GRIP_RELEASE = 14
    LEVEL6_FINGER_TAPS = 15
    LEVEL7_WRIST_MECHANICS = 16
    LEVEL8_SMART_ASSEMBLY = 17
    LEVEL9_PRECISION_PATH = 18
    LEVEL10_PRECISION_PATHWAY = 19
    LEVEL11_COIN_VAULT = 26
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
    wrist_rotation_angle: float = 0.0
    wrist_deviation_angle: float = 0.0
    landmarks: Optional[list] = None
    hand_label: str = "Unknown"


@dataclass
class AssemblyPart:
    name: str
    target_pos: tuple
    target_angle: float
    current_pos: list
    current_angle: float
    color: tuple
    shape: list
    is_grabbed: bool = False
    is_locked: bool = False


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


@dataclass
class PrecisionDot:
    """Dot target for Level 9 Precision Path"""
    x: float
    y: float
    radius: int
    order: int
    state: str = "WAITING"  # WAITING, ACTIVE, COMPLETED, MISSED
    activation_time: float = 0.0


@dataclass
class PathwayConfig:
    """Config for Level 10 Precision Pathway"""
    path_type: str
    points: List[Tuple[float, float]]
    width: float
    recommended_direction: str


@dataclass
class Coin:
    """Virtual coin object for Level 11 In-Hand Manipulation"""
    coin_id: int
    color_type: str  # "GOLD", "BLUE", "GREEN", "RED"
    symbol: str      # "1", "2", "3", "4" or symbol
    color: Tuple[int, int, int]
    x: float
    y: float
    radius: float
    target_vault: str
    state: str = "PRESENTED"  # PRESENTED, PICKED_UP, IN_HAND_TRANSLATING, PALM_HOLD, PALM_TO_FINGERTIP, PLACED, DROPPED
    spawn_timestamp: float = 0.0
    pickup_timestamp: float = 0.0
    manipulation_start_timestamp: float = 0.0
    manipulation_end_timestamp: float = 0.0
    placement_timestamp: float = 0.0


@dataclass
class Vault:
    """Target receptacle vault for Level 11"""
    vault_id: str  # "GOLD", "BLUE", "GREEN", "RED"
    symbol: str
    color: Tuple[int, int, int]
    x: int
    y: int
    w: int
    h: int
    coins_collected: int = 0
