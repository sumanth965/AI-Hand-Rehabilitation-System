"""Script to extract the PhysioSystem class into physio/game.py"""
import os

src = r'd:\Documentsss\AI-Hand-Rehabilitation-System\zero_keyboard_physio.py'
dst = r'd:\Documentsss\AI-Hand-Rehabilitation-System\physio\game.py'

with open(src, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Extract lines 2929 onwards (PhysioSystem class + entry point)
game_lines = lines[2928:]  # 0-indexed

header = '"""\nMain Game Application (PhysioSystem) for the Zero-Keyboard AI Physiotherapy System.\n"""\n\n'
header += 'import cv2\n'
header += 'import mediapipe as mp\n'
header += 'import pygame\n'
header += 'import numpy as np\n'
header += 'import sqlite3\n'
header += 'import security_utils\n'
header += 'import threading\n'
header += 'import time\n'
header += 'import math\n'
header += 'import random\n'
header += 'from dataclasses import dataclass, field\n'
header += 'from enum import Enum\n'
header += 'from typing import Optional, Tuple, List\n'
header += 'from collections import deque\n'
header += 'from datetime import datetime\n'
header += 'import os\n'
header += 'import io\n'
header += 'import pyttsx3\n'
header += 'import matplotlib\n'
header += 'matplotlib.use("Agg")\n'
header += 'import matplotlib.pyplot as plt\n'
header += 'from adaptive_ai_engine import AdaptiveRehabEngine, ForearmExerciseClassifier\n'
header += 'try:\n'
header += '    from reportlab.pdfgen import canvas\n'
header += '    from reportlab.lib.pagesizes import letter\n'
header += '    from reportlab.lib import colors\n'
header += 'except ImportError:\n'
header += '    pass\n\n'
header += 'from physio.constants import *\n'
header += 'from physio.utils import distance, lerp, weighted_average, recovery_category, functional_recovery_score\n'
header += 'from physio.voice import VOICE\n'
header += 'from physio.sound import SoundSystem\n'
header += 'from physio.particles import ParticleSystem, ScorePopup\n'
header += 'from physio.models import (\n'
header += '    GameState, AgeGroup, HandData, AssemblyPart, Bubble, FallingItem, Seed\n'
header += ')\n'
header += 'from physio.camera import WebcamStream\n'
header += 'from physio.hand_engine import HandEngine\n'
header += 'from physio.database import DatabaseManager\n'
header += 'from physio.ui_widgets import (\n'
header += '    SelectionRing, LevelButton, HomeIcon, CloseButton, Button, _get_ui_fonts\n'
header += ')\n'
header += 'from physio.medical_sidebar import MedicalSidebar, MedicalSidebarV2, PostGameSummary\n'
header += 'from physio.clinical import KinematicQualityTracker, AdvancedCompensationDetector\n\n'

with open(dst, 'w', encoding='utf-8') as f:
    f.write(header)
    for line in game_lines:
        f.write(line)

print(f"SUCCESS: Wrote header + {len(game_lines)} lines to {dst}")
