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
          {self.stat_card('Total Patients', str(stats['patients']), 'Registered or session-linked patients', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>')}
          {self.stat_card('Active Patients', str(stats['active_patients']), 'Patients seen in the last 7 days', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>')}
          {self.stat_card('Total Rehabilitation Sessions', str(stats['completed_sessions']), f"{stats['active_sessions']} sessions this week", '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>')}
          {self.stat_card('Average Recovery Progress', f"{stats['avg_recovery']:.1f}%", 'Linear trend projection where available', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>')}
          {self.stat_card('Average Accuracy', f"{stats['overall_accuracy']:.1f}%", 'Average exercise success rate', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>')}
          {self.stat_card('Average ROM', f"{stats['avg_rom']:.1f} deg", 'Mean recorded hand angle', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"></path><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"></path><path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"></path><path d="M6 14v-1a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"></path><path d="M18 11a4 4 0 0 1 4 4v3a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"></path></svg>')}
          {self.stat_card('Patients At Risk', str(stats['patients_at_risk']), 'High pain, high risk, or flagged trend', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>')}
          {self.stat_card('Average Pain Score', f"{stats['avg_pain']:.1f}/10", 'Mean recorded pre-session NRS', '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">
            <div class="toolbar"><h2>Recent Patient Activity</h2><a class="button secondary" href="/sessions">View all</a></div>
            <div class="table-container" style="margin-top:24px;">
<table>
              <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead>
              <tbody>{recent_rows}</tbody>
            </table>
</div>
          </div>
          <div class="grid">{alert_cards}</div>
        </section>
        """
        return Page("Dashboard Home", body, "home")

