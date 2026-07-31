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



class AnalyticsPagesMixin:
    def analytics(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        sessions = self.repo.sessions_chrono(patient)
        labels = [short_date(row["timestamp"]) for row in sessions[-16:]]
        acc = [number(row["avg_accuracy"]) for row in sessions[-16:]]
        rom = [number(row["avg_hand_angle"]) for row in sessions[-16:]]
        pain = [number(row["pain_level"]) for row in sessions[-16:]]
        pain_before = [number(row_value(row, "pain_before_session", row["pain_level"])) for row in sessions[-16:]]
        pain_after = [number(row_value(row, "pain_after_session", row["pain_level"])) for row in sessions[-16:]]
        pain_difference = [number(row_value(row, "pain_difference", 0)) for row in sessions[-16:]]
        recovery_scores = [calculated_functional_recovery_score(row) for row in sessions[-16:]]
        latest = sessions[-1] if sessions else None
        latest_recovery = calculated_functional_recovery_score(latest) if latest else 0.0
        latest_category = recovery_category(latest_recovery) if latest else "Not started"
        avg_pain_delta = sum(pain_difference) / len(pain_difference) if pain_difference else 0.0
        actual_recovery = [min(100.0, number(row["avg_hand_angle"]) / 90.0 * 100.0) for row in sessions[-16:]]
        predicted_recovery = []
        for index in range(len(sessions[-16:])):
            pred = recovery_prediction(sessions[: max(0, len(sessions) - len(sessions[-16:])) + index + 1])
            predicted_recovery.append(pred if pred >= 0 else actual_recovery[index] if index < len(actual_recovery) else 0)
        prescriptions = list(reversed(self.repo.adaptive_history(patient, limit=16)))
        readiness_labels = [short_date(row["created_at"]) for row in prescriptions]
        readiness = [number(row["readiness_score"]) for row in prescriptions]
        daily_rom = self.bucket_metric(sessions, "%d %b", "avg_hand_angle")
        weekly_rom = self.bucket_metric(sessions, "%Y-W%W", "avg_hand_angle")
        monthly_rom = self.bucket_metric(sessions, "%Y-%m", "avg_hand_angle")
        weekly = self.bucket_progress(sessions, "%Y-W%W")
        monthly = self.bucket_progress(sessions, "%Y-%m")
        daily_pain = self.bucket_derived(sessions, "%d %b", lambda row: number(row_value(row, "pain_difference", 0)))
        weekly_pain = self.bucket_derived(sessions, "%Y-W%W", lambda row: number(row_value(row, "pain_difference", 0)))
        monthly_pain = self.bucket_derived(sessions, "%Y-%m", lambda row: number(row_value(row, "pain_difference", 0)))
        daily_recovery = self.bucket_derived(sessions, "%d %b", calculated_functional_recovery_score)
        weekly_recovery = self.bucket_derived(sessions, "%Y-W%W", calculated_functional_recovery_score)
        monthly_recovery = self.bucket_derived(sessions, "%Y-%m", calculated_functional_recovery_score)
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Progress Analytics</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid three" style="margin-top:16px">
          {self.stat_card('Recovery Score', f"{latest_recovery:.0f}/100", latest_category)}
          {self.stat_card('Pain Improvement', f"{avg_pain_delta:+.1f}", 'Average after-before change')}
          {self.stat_card('Latest Pain Summary', f"{pain_before[-1]:.0f}/10 to {pain_after[-1]:.0f}/10" if pain_before else '-', f"Difference {pain_difference[-1]:+.0f}" if pain_difference else 'No pain data')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('ROM Progress - Daily', {'Daily ROM': daily_rom[1]}, daily_rom[0], 'degrees')}</div>
          <div class="card">{self.chart('ROM Progress - Weekly', {'Weekly ROM': weekly_rom[1]}, weekly_rom[0], 'degrees')}</div>
          <div class="card">{self.chart('ROM Progress - Monthly', {'Monthly ROM': monthly_rom[1]}, monthly_rom[0], 'degrees')}</div>
          <div class="card">{self.chart('Accuracy Trends', {'Session Accuracy': acc}, labels, '%')}</div>
          <div class="card">{self.chart('Weekly Improvement', {'Weekly Accuracy': weekly[1]}, weekly[0], '%')}</div>
          <div class="card">{self.chart('Monthly Accuracy', {'Monthly Accuracy': monthly[1]}, monthly[0], '%')}</div>
          <div class="card">{self.chart('Pain Reduction Over Time', {'Pain Score': pain}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Pain Before vs Pain After', {'Before': pain_before, 'After': pain_after}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Daily Pain Trend', {'Pain Difference': daily_pain[1]}, daily_pain[0], 'after-before')}</div>
          <div class="card">{self.chart('Weekly Pain Trend', {'Pain Difference': weekly_pain[1]}, weekly_pain[0], 'after-before')}</div>
          <div class="card">{self.chart('Monthly Pain Trend', {'Pain Difference': monthly_pain[1]}, monthly_pain[0], 'after-before')}</div>
          <div class="card">{self.chart('Functional Recovery Score', {'Recovery Score': recovery_scores}, labels, 'score')}</div>
          <div class="card">{self.chart('Daily Recovery Score', {'Recovery Score': daily_recovery[1]}, daily_recovery[0], 'score')}</div>
          <div class="card">{self.chart('Weekly Recovery Score', {'Recovery Score': weekly_recovery[1]}, weekly_recovery[0], 'score')}</div>
          <div class="card">{self.chart('Monthly Recovery Score', {'Recovery Score': monthly_recovery[1]}, monthly_recovery[0], 'score')}</div>
          <div class="card">{self.chart('Recovery Prediction Trends', {'Predicted Recovery': predicted_recovery, 'Actual Recovery': actual_recovery}, labels, '%')}</div>
          <div class="card">{self.chart('Readiness Score Trends', {'Readiness Score': readiness}, readiness_labels, 'score')}</div>
          <div class="card">{self.chart('Session ROM and Accuracy', {'ROM': rom, 'Accuracy': acc}, labels, 'value')}</div>
        </section>
        """
        return Page("Progress Analytics", body, "analytics")

