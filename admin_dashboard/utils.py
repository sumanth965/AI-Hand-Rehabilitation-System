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

@dataclass
class Page:
    title: str
    body: str
    active: str = "home"
    scripts: str = ""



def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def row_value(row: sqlite3.Row, key: str, default: Any = "") -> Any:
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def short_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "")).strftime("%d %b %Y")
    except ValueError:
        return value[:16]


def minutes(seconds: Any) -> float:
    return number(seconds) / 60.0


def format_duration(seconds: Any) -> str:
    total = int(number(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def exercise_for_level(level: Any) -> str:
    return LEVEL_NAMES.get(int(number(level)), "Therapeutic Exercise")


def trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return values[-1] - values[0]


def recovery_prediction(sessions: list[sqlite3.Row]) -> float:
    values = [number(row["avg_hand_angle"]) for row in sessions if row["avg_hand_angle"] is not None]
    if len(values) < 3:
        return -1.0
    xs = list(range(len(values)))
    x_mean = sum(xs) / len(xs)
    y_mean = sum(values) / len(values)
    denom = sum((x - x_mean) ** 2 for x in xs) or 1.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denom
    predicted = y_mean + slope * (len(values) + 3)
    current = max(y_mean, 1.0)
    return max(0.0, min(100.0, (predicted / current) * 100.0))


def tremor_rating_for_sessions(sessions: list[sqlite3.Row]) -> str:
    if len(sessions) < 3:
        return "Not recorded"
    rom_values = [number(row["avg_hand_angle"]) for row in sessions[-6:]]
    mean = sum(rom_values) / len(rom_values)
    variance = sum((value - mean) ** 2 for value in rom_values) / len(rom_values)
    stdev = math.sqrt(variance)
    if stdev < 5:
        return "Low"
    if stdev < 12:
        return "Moderate"
    return "High"


def fatigue_score(row: sqlite3.Row) -> float:
    """Derive a 0-10 fatigue indicator from stored session metrics."""
    pain = number(row["pain_level"])
    accuracy_load = max(0.0, (70.0 - number(row["avg_accuracy"])) / 70.0) * 4.0
    duration_load = min(3.0, minutes(row["duration"]) / 8.0 * 3.0)
    pain_load = pain * 0.35
    return max(0.0, min(10.0, accuracy_load + duration_load + pain_load))


def recovery_status_from_metrics(avg_accuracy: float, avg_rom: float, risk_level: str, sessions_count: int) -> str:
    if sessions_count == 0:
        return "Not started"
    if str(risk_level).lower() == "high":
        return "At risk"
    if avg_accuracy >= 75 and avg_rom >= 75:
        return "Progressing well"
    if avg_accuracy >= 55 and avg_rom >= 45:
        return "Active recovery"
    return "Needs review"


def recovery_category(score: float) -> str:
    if score <= 25:
        return "Poor"
    if score <= 50:
        return "Fair"
    if score <= 75:
        return "Good"
    return "Excellent"


def calculated_functional_recovery_score(row: sqlite3.Row, consistency: float = 1.0) -> float:
    try:
        stored = number(row["functional_recovery_score"], -1)
        if stored > 0:
            return round(stored, 1)
    except (IndexError, KeyError):
        pass
    pain_after = row_value(row, "pain_after_session", row_value(row, "pain_level", 0))
    smoothness = row_value(row, "movement_smoothness", 0.7)
    score = (
        0.30 * max(0.0, min(1.0, number(row["avg_hand_angle"]) / 90.0))
        + 0.25 * max(0.0, min(1.0, number(row["avg_accuracy"]) / 100.0))
        + 0.20 * max(0.0, min(1.0, (10.0 - number(pain_after)) / 10.0))
        + 0.15 * max(0.0, min(1.0, consistency))
        + 0.10 * max(0.0, min(1.0, number(smoothness, 0.7)))
    ) * 100.0
    return round(max(0.0, min(100.0, score)), 1)


