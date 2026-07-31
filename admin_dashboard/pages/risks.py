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



class RiskPagesMixin:
    def risks_page(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patients = [self.repo.patient(patient)] if patient and self.repo.patient(patient) else self.repo.patients()
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        cards: list[str] = []
        rows: list[str] = []
        for row in patients:
            if not row:
                continue
            risk_items = self.patient_risks(row)
            for label, severity, detail in risk_items:
                level_class = "danger" if severity == "High" else "warning" if severity == "Moderate" else ""
                cards.append(f'<div class="card alert {level_class}"><h2>{esc(label)}</h2><p><strong>{esc(row["name"])}</strong></p><p class="muted">{esc(detail)}</p><span class="badge">{esc(severity)}</span></div>')
                rows.append(f"<tr><td>{esc(row['name'])}</td><td>{esc(label)}</td><td>{esc(severity)}</td><td>{esc(detail)}</td><td>{esc(short_date(row['last_session']))}</td></tr>")
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Risk Detection Panel</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid three" style="margin-top:16px">{''.join(cards) or '<div class="card muted">No active rehabilitation risks detected.</div>'}</section>
        <section class="card" style="margin-top:16px">
          <h2>Risk Register</h2>
          <table>
            <thead><tr><th>Patient</th><th>Risk</th><th>Severity</th><th>Clinical Detail</th><th>Last Session</th></tr></thead>
            <tbody>{''.join(rows) or '<tr><td colspan="5" class="muted">No active risk items.</td></tr>'}</tbody>
          </table>
        </section>
        """
        return Page("Risk Detection", body, "risks")

    def patient_risks(self, patient: sqlite3.Row) -> list[tuple[str, str, str]]:
        name = patient["name"]
        sessions = self.repo.sessions_chrono(name)
        clinical = self.repo.clinical_intel.get_clinical_profile(name)
        upper = self.repo.latest_upper_limb_assessment(name)
        risks: list[tuple[str, str, str]] = []
        if sessions:
            recent = sessions[-3:]
            avg_pain = sum(number(row["pain_level"]) for row in recent) / len(recent)
            if avg_pain >= 6:
                risks.append(("High Pain Risk", "High", f"Recent average pain is {avg_pain:.1f}/10."))
            if len(recent) >= 3:
                rom_delta = number(recent[-1]["avg_hand_angle"]) - number(recent[0]["avg_hand_angle"])
                acc_delta = number(recent[-1]["avg_accuracy"]) - number(recent[0]["avg_accuracy"])
                if abs(rom_delta) < 2 and acc_delta <= 2:
                    risks.append(("Recovery Stagnation", "Moderate", "ROM and accuracy have not meaningfully improved over the last three sessions."))
                if fatigue_score(recent[-1]) >= 7:
                    risks.append(("Fatigue Risk", "High", f"Derived fatigue score is {fatigue_score(recent[-1]):.1f}/10."))
            try:
                last_dt = datetime.fromisoformat(str(sessions[-1]["timestamp"]))
                days_since = (datetime.now() - last_dt).days
                if days_since > 7:
                    risks.append(("Missed Sessions", "Moderate" if days_since <= 14 else "High", f"No session recorded for {days_since} days."))
            except ValueError:
                pass
        else:
            risks.append(("Missed Sessions", "Moderate", "Patient has no stored rehabilitation sessions."))
        if upper and number(upper["compensation_score"]) >= 0.45:
            risks.append(("Compensation Risk", "High", f"Latest compensation score is {number(upper['compensation_score']) * 100:.0f}%."))
        for detected in clinical["detected_risks"]:
            if not any(label == detected for label, _, _ in risks):
                risks.append((detected, "High" if detected in ("High Pain Risk", "Dropout Risk") else "Moderate", "Flagged by clinical intelligence layer."))
        return risks

