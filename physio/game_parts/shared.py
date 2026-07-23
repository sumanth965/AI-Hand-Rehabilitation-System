"""
Main Game Application (PhysioSystem) for the Zero-Keyboard AI Physiotherapy System.
"""

import cv2
import mediapipe as mp
import pygame
import numpy as np
import sqlite3
import security_utils
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
from adaptive_ai_engine import AdaptiveRehabEngine, ForearmExerciseClassifier
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
except ImportError:
    pass

from physio.constants import *
from physio.utils import distance, lerp, weighted_average, recovery_category, functional_recovery_score
from physio.voice import VOICE
from physio.sound import SoundSystem
from physio.particles import ParticleSystem, ScorePopup
from physio.models import (
    GameState, AgeGroup, HandData, AssemblyPart, Bubble, FallingItem, Seed
)
from physio.camera import WebcamStream
from physio.hand_engine import HandEngine
from physio.database import DatabaseManager
from physio.ui_widgets import (
    SelectionRing, LevelButton, HomeIcon, CloseButton, Button, _get_ui_fonts
)
from physio.medical_sidebar import MedicalSidebar, MedicalSidebarV2, PostGameSummary
from physio.clinical import KinematicQualityTracker, AdvancedCompensationDetector

