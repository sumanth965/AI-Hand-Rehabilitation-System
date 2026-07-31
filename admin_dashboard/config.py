"""
Therapist Dashboard for the AI Hand Rehabilitation System.

This module is intentionally separate from the real-time MediaPipe/Pygame
rehabilitation runtime. It reads the existing SQLite database, adds optional
dashboard-only metadata tables, and serves a professional browser dashboard.
"""

from __future__ import annotations

import base64
import html
import io
import json
import math
import os
import sqlite3
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, unquote, urlparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from digital_twin_rehab import DigitalTwinRehabModel
from clinical_intelligence import ClinicalIntelligenceLayer
import security_utils
import secrets



DB_PATH = "rehab_data.db"
REPORT_DIR = "reports"
HOST = "127.0.0.1"
PORT = 8081


LEVEL_NAMES = {
    1: "Flexibility - Bubble Reach",
    2: "Strength - Palm Catch",
    3: "Fine Motor - Pinch Transfer",
    4: "Coordination - Path Tracing",
    5: "Grip Release - Open/Close Cycle",
    6: "Cognitive Motor - Sequence Tap",
    7: "Forearm Rotation - Rotation Orbit",
    8: "Functional Motor - Smart Assembly",
}


