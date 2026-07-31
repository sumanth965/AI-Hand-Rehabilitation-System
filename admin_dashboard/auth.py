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



from admin_dashboard.config import *

# Session storage for therapist authentication
SESSIONS: dict[str, tuple[str, datetime]] = {}
SESSION_DURATION = timedelta(hours=8)

def create_session(username: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (username, datetime.now() + SESSION_DURATION)
    return token

def get_session(token: str) -> str | None:
    if token not in SESSIONS:
        return None
    username, expires = SESSIONS[token]
    if datetime.now() > expires:
        del SESSIONS[token]
        return None
    # Extend session
    SESSIONS[token] = (username, datetime.now() + SESSION_DURATION)
    return username

def clear_session(token: str) -> None:
    if token in SESSIONS:
        del SESSIONS[token]



