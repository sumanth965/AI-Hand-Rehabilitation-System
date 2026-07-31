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



class DigitalTwinPagesMixin:
    def digital_twin_page(self, params: dict[str, str]) -> Page:
        patients = self.repo.patients()
        selected = params.get("patient", "")
        if not selected and patients:
            selected = patients[0]["name"]
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in patients)
        if not selected:
            body = """
            <section class="card">
              <h2>Personalized Rehabilitation Digital Twin</h2>
              <p class="muted">Register a patient and complete sessions to generate a digital twin.</p>
            </section>
            """
            return Page("Digital Twin", body, "digital_twin")

        twin = self.repo.digital_twin_profile(selected)
        snapshots = list(reversed(self.repo.digital_twin_snapshots(selected, limit=16)))
        snap_labels = [short_date(row["created_at"]) for row in snapshots]
        readiness_series = [number(row["readiness_score"]) for row in snapshots]
        rom_series = [number(row["current_rom"]) for row in snapshots]
        risk_series = [number(row["stagnation_risk"]) for row in snapshots]

        scenario_cards = "".join(
            f"""
            <div class="card alert {'danger' if item.risk_level == 'High' else 'warning' if item.risk_level == 'Moderate' else ''}">
              <h2>{esc(item.name)} · {esc(item.strategy)}</h2>
              <div class="grid three">
                {self.stat_card('Timeline', f"{item.recovery_timeline_weeks:.1f} wk", 'To functional ROM target')}
                {self.stat_card('Expected ROM', f"{item.expected_rom:.1f} deg", '4-week forecast')}
                {self.stat_card('Expected Accuracy', f"{item.expected_accuracy:.1f}%", '4-week forecast')}
                {self.stat_card('Risk Level', item.risk_level, 'Scenario risk')}
                {self.stat_card('Fatigue Risk', f"{item.fatigue_risk:.0f}%", 'Load tolerance')}
                {self.stat_card('Compensation Risk', f"{item.compensation_risk:.0f}%", 'Movement quality')}
              </div>
              <p class="muted" style="margin-top:12px">{esc(item.explanation)}</p>
              <p><strong>Adherence:</strong> {esc(item.adherence_impact)}</p>
            </div>
            """
            for item in twin.scenarios
        )
        risk_cards = "".join(
            self.stat_card(label.replace("_", " ").title(), f"{value:.0f}%", "Predicted risk")
            for label, value in twin.risks.items()
        )
        milestones = "".join(f"<li>{esc(item)}</li>" for item in twin.milestones)
        exercise_mix = ", ".join(twin.recommendations.get("best_exercise_mix", []))
        weekly = twin.recommendations.get("weekly_targets", {})
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Personalized Rehabilitation Digital Twin</h2>
            <select name="patient">{patient_options}</select>
            <button>Build Twin</button>
          </form>
          <p class="muted">{esc(twin.explanation)}</p>
        </section>
        <section class="grid three" style="margin-top:16px">
          {self.stat_card('Current ROM', f"{twin.current_rom:.1f} deg", f"Velocity {twin.recovery_velocity:+.1f} deg/wk")}
          {self.stat_card('Current Accuracy', f"{twin.current_accuracy:.1f}%", f"Pain {twin.current_pain:.0f}/10")}
          {self.stat_card('Readiness', f"{twin.readiness_score:.0f}/100", f"Consistency {twin.consistency_score:.0f}%")}
          {self.stat_card('Fatigue', f"{twin.fatigue_index:.0f}%", 'Recent load estimate')}
          {self.stat_card('Compensation', f"{twin.compensation_score:.0f}%", 'Historical movement quality')}
          {self.stat_card('Forearm Quality', f"{twin.forearm_quality:.0f}%", 'Smoothness minus compensation')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('Digital Twin Snapshot Trend', {'Readiness': readiness_series, 'ROM': rom_series, 'Stagnation Risk': risk_series}, snap_labels, 'score')}</div>
          <div class="card">
            <h2>Personalized Recommendations</h2>
            <table>
              <tbody>
                <tr><th>Best Strategy</th><td>{esc(twin.recommendations.get('best_strategy', '-'))}</td></tr>
                <tr><th>Exercise Mix</th><td>{esc(exercise_mix)}</td></tr>
                <tr><th>Optimal Duration</th><td>{esc(twin.recommendations.get('optimal_session_duration', '-'))}</td></tr>
                <tr><th>Weekly Targets</th><td>{esc(json.dumps(weekly, sort_keys=True))}</td></tr>
                <tr><th>Progression Plan</th><td>{esc(twin.recommendations.get('difficulty_progression_plan', '-'))}</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="grid three" style="margin-top:16px">{risk_cards}</section>
        <section class="grid" style="margin-top:16px">{scenario_cards}</section>
        <section class="card" style="margin-top:16px">
          <h2>Milestone Predictions</h2>
          <ul>{milestones}</ul>
        </section>
        """
        return Page("Digital Twin", body, "digital_twin")

