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



class HomePageMixin:
    def home(self) -> Page:
        stats = self.repo.dashboard_stats()
        recent = self.repo.sessions(limit=8)
        patients = self.repo.patients()
        recent_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['timestamp']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_hand_angle']):.1f} deg</td>
              <td>{esc(format_duration(row['duration']))}</td>
            </tr>
            """
            for row in recent
        ) or '<tr><td colspan="6" class="muted">No session data yet.</td></tr>'
        alert_cards = self.alert_cards()
        body = f"""
        <section class="grid stats">
          {self.stat_card('Total Patients', str(stats['patients']), 'Registered or session-linked patients')}
          {self.stat_card('Active Patients', str(stats['active_patients']), 'Patients seen in the last 7 days')}
          {self.stat_card('Total Rehabilitation Sessions', str(stats['completed_sessions']), f"{stats['active_sessions']} sessions this week")}
          {self.stat_card('Average Recovery Progress', f"{stats['avg_recovery']:.1f}%", 'Linear trend projection where available')}
          {self.stat_card('Average Accuracy', f"{stats['overall_accuracy']:.1f}%", 'Average exercise success rate')}
          {self.stat_card('Average ROM', f"{stats['avg_rom']:.1f} deg", 'Mean recorded hand angle')}
          {self.stat_card('Patients At Risk', str(stats['patients_at_risk']), 'High pain, high risk, or flagged trend')}
          {self.stat_card('Average Pain Score', f"{stats['avg_pain']:.1f}/10", 'Mean recorded pre-session NRS')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">
            <div class="toolbar"><h2>Recent Patient Activity</h2><a class="button secondary" href="/sessions">View all</a></div>
            <table>
              <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead>
              <tbody>{recent_rows}</tbody>
            </table>
          </div>
          <div class="grid">{alert_cards}</div>
        </section>
        """
        return Page("Dashboard Home", body, "home")

