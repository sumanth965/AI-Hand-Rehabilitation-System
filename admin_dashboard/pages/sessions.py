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



class SessionPagesMixin:
    def sessions_page(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        exercise_filter = params.get("exercise", "")
        min_pain = number(params.get("min_pain"), -1)
        rows = self.repo.sessions(patient)
        if exercise_filter:
            rows = [row for row in rows if str(int(number(row["level"]))) == exercise_filter]
        if min_pain >= 0:
            rows = [row for row in rows if number(row["pain_level"]) >= min_pain]
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        exercise_options = "".join(self.option(str(level), name, exercise_filter) for level, name in LEVEL_NAMES.items())
        comparison_rows = rows[:2]
        comparison = ""
        if len(comparison_rows) == 2:
            a, b = comparison_rows[1], comparison_rows[0]
            comparison = f"""
            <div class="grid three" style="margin-top:16px">
              {self.stat_card('Accuracy Change', f"{number(b['avg_accuracy']) - number(a['avg_accuracy']):+.1f}%", 'Latest vs previous filtered session')}
              {self.stat_card('ROM Change', f"{number(b['avg_hand_angle']) - number(a['avg_hand_angle']):+.1f} deg", 'Latest vs previous filtered session')}
              {self.stat_card('Pain Change', f"{number(b['pain_level']) - number(a['pain_level']):+.0f}/10", 'Latest vs previous filtered session')}
            </div>
            """
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['timestamp']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{esc(format_duration(row['duration']))}</td>
              <td>{number(row['max_finger_extension']):.1f}px</td>
              <td>{number(row['avg_hand_angle']):.1f} deg</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{int(number(row_value(row, 'pain_before_session', row['pain_level'])))}/10</td>
              <td>{int(number(row_value(row, 'pain_after_session', row['pain_level'])))}/10</td>
              <td>{int(number(row_value(row, 'pain_difference', 0))):+d}</td>
              <td>{calculated_functional_recovery_score(row):.1f}/100</td>
              <td>{fatigue_score(row):.1f}/10</td>
              <td>{esc(tremor_rating_for_sessions(self.repo.sessions_chrono(row['patient_id'])))}</td>
              <td>{int(number(row['score']))}</td>
              <td>{self.prediction_badge(row['patient_id'])}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="15" class="muted">No sessions found.</td></tr>'
        body = f"""
        <section class="card">
          <div class="toolbar">
            <h2>Session History</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <select name="exercise"><option value="">All exercises</option>{exercise_options}</select>
              <select name="min_pain">
                {self.option('-1', 'Any pain score', params.get('min_pain', '-1'))}
                {self.option('4', 'Pain 4+', params.get('min_pain', '-1'))}
                {self.option('7', 'Pain 7+', params.get('min_pain', '-1'))}
              </select>
              <button>Filter</button>
            </form>
          </div>
          <input id="sessionSearch" oninput="filterTable('sessionSearch','sessionsTable')" placeholder="Search session table">
          {comparison}
          <table id="sessionsTable" style="margin-top:12px">
            <thead><tr>
              <th onclick="sortTable('sessionsTable',0)">Session Date</th><th>Patient</th><th>Exercise Name</th><th>Duration</th><th>Max Extension</th><th>ROM</th><th>Accuracy</th><th>Pain Before</th><th>Pain After</th><th>Pain Difference</th><th>Recovery Score</th><th>Fatigue Score</th><th>Tremor</th><th>Score</th><th>Recovery Prediction</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
          <div class="pagination"><span class="pill">Client-side sorting, filtering, and table search enabled</span></div>
        </section>
        """
        return Page("Session History", body, "sessions")

    def bucket_progress(self, sessions: list[sqlite3.Row], fmt: str) -> tuple[list[str], list[float]]:
        return self.bucket_metric(sessions, fmt, "avg_accuracy")

    def bucket_metric(self, sessions: list[sqlite3.Row], fmt: str, column: str) -> tuple[list[str], list[float]]:
        buckets: dict[str, list[float]] = {}
        for row in sessions:
            try:
                key = datetime.fromisoformat(str(row["timestamp"])).strftime(fmt)
            except ValueError:
                key = str(row["timestamp"])[:7]
            buckets.setdefault(key, []).append(number(row[column]))
        labels = list(buckets.keys())[-12:]
        values = [sum(buckets[label]) / len(buckets[label]) for label in labels]
        return labels, values

    def bucket_derived(self, sessions: list[sqlite3.Row], fmt: str, value_fn) -> tuple[list[str], list[float]]:
        buckets: dict[str, list[float]] = {}
        for row in sessions:
            try:
                key = datetime.fromisoformat(str(row["timestamp"])).strftime(fmt)
            except ValueError:
                key = str(row["timestamp"])[:7]
            buckets.setdefault(key, []).append(number(value_fn(row)))
        labels = list(buckets.keys())[-12:]
        values = [sum(buckets[label]) / len(buckets[label]) for label in labels]
        return labels, values

