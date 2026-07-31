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
from admin_dashboard.auth import *
from admin_dashboard.utils import *
from admin_dashboard.database import *



class NotificationPagesMixin:
    def notifications(self) -> Page:
        body = f'<section class="grid two">{self.alert_cards(full=True)}</section>'
        return Page("Notifications", body, "notifications")

    def alert_cards(self, full: bool = False) -> str:
        alerts = self.alerts()
        if not alerts:
            alerts = [("No critical alerts", "All tracked sessions are within expected monitoring thresholds.", "")]
        return "".join(
            f'<div class="card alert {esc(level)}"><h2>{esc(title)}</h2><p class="muted">{esc(message)}</p></div>'
            for title, message, level in alerts[:12 if full else 4]
        )

    def alerts(self) -> list[tuple[str, str, str]]:
        alerts: list[tuple[str, str, str]] = []
        now = datetime.now()
        for patient in self.repo.patients():
            name = patient["name"]
            sessions = self.repo.sessions_chrono(name)
            if not sessions:
                alerts.append((f"{name}: no completed sessions", "Patient is registered but has no stored rehabilitation session.", "warning"))
                continue
            last = sessions[-1]
            try:
                last_dt = datetime.fromisoformat(str(last["timestamp"]))
                if now - last_dt > timedelta(days=7):
                    alerts.append((f"{name}: missed therapy", f"Last session was on {short_date(last['timestamp'])}.", "warning"))
            except ValueError:
                pass
            if number(last["pain_level"]) >= 7:
                alerts.append((f"{name}: high pain score", f"Latest pain score is {int(number(last['pain_level']))}/10.", "danger"))
            if number(last["avg_accuracy"]) < 50:
                alerts.append((f"{name}: low exercise accuracy", f"Latest accuracy is {number(last['avg_accuracy']):.1f}%.", "danger"))
            adaptive = self.repo.latest_adaptive_prescription(name)
            if adaptive:
                if str(adaptive["risk_level"]).lower() == "high":
                    alerts.append((f"{name}: adaptive high risk", esc(adaptive["override_recommendation"]), "danger"))
                elif number(adaptive["readiness_score"]) < 45:
                    alerts.append((f"{name}: low readiness score", f"Readiness is {number(adaptive['readiness_score']):.0f}/100.", "warning"))
            upper_limb = self.repo.latest_upper_limb_assessment(name)
            if upper_limb and number(upper_limb["compensation_score"]) >= 0.55:
                alerts.append((f"{name}: compensation detected", str(upper_limb["feedback"]), "warning"))
            if len(sessions) >= 2:
                delta = number(sessions[-1]["avg_hand_angle"]) - number(sessions[-2]["avg_hand_angle"])
                if delta >= 10:
                    alerts.append((f"{name}: significant improvement", f"ROM improved by {delta:.1f} degrees since the previous session.", ""))
                elif delta < -8:
                    alerts.append((f"{name}: slow recovery risk", f"ROM decreased by {abs(delta):.1f} degrees since the previous session.", "warning"))
        return alerts

