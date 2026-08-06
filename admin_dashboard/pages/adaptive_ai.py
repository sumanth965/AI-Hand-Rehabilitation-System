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



class AdaptiveAIPagesMixin:
    def adaptive_ai(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        prescriptions = self.repo.adaptive_history(patient, limit=40)
        metrics = self.repo.research_metrics(patient)
        override_stats = self.repo.override_stats(patient)
        overrides = self.repo.override_history(patient, limit=20)
        upper_rows = list(reversed(self.repo.upper_limb_history(patient, limit=16)))
        upper_labels = [short_date(row["created_at"]) for row in upper_rows]
        compensation_series = [number(row["compensation_score"]) * 100.0 for row in upper_rows]
        efficiency_series = [number(row["movement_efficiency"]) for row in upper_rows]
        current = prescriptions[0] if prescriptions else None
        current_panel = ""
        if current:
            current_panel = f"""
            <section class="card" style="margin-top:16px">
              <h2>AI Prescription Panel</h2>
              <p class="muted">Decision Source: Adaptive AI Rehabilitation Engine</p>
            </section>
            <section class="grid stats three" style="margin-top:24px; margin-bottom:32px;">
              {self.stat_card('Current Difficulty Tier', str(int(number(current['difficulty_tier']))), esc(exercise_for_level(current['level'])), '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>')}
              {self.stat_card('Readiness Score', f"{number(current['readiness_score']):.0f}/100", f"Recovery: {esc(current['recovery_trend'])}", '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>')}
              {self.stat_card('Risk Level', str(current['risk_level']).title(), 'Safety decision from engine', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>')}
              {self.stat_card('Target Size', f"{number(current['target_scale']):.2f}x", f"Speed {number(current['speed_scale']):.2f}x", '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle><circle cx="12" cy="12" r="2"></circle></svg>')}
              {self.stat_card('ROM Requirement', f"{number(current['required_rom']):.0f} deg", f"Tolerance {number(current['rotation_tolerance']):.0f} deg", '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"></path><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>')}
              {self.stat_card('Repetitions / Hold', f"{int(number(current['repetitions']))} reps", f"{number(current['hold_seconds']):.1f}s holds", '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>')}
              {self.stat_card('Progression Recommendation', str(current['progression']).title(), esc(current['override_recommendation']), '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 2 13 9 20 9"></polyline><path d="M13 2L20 9"></path><path d="M12 21H3v-8l9-9"></path></svg>')}
              {self.stat_card('Guidance Level', str(current['guidance_level']).title(), f"{number(current['time_limit']):.0f}s time limit", '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>')}
              {self.stat_card('Adaptive Rationale', self.short_text(current['rationale'], 32), 'Explainable AI decision', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>')}
            </section>
            """

        rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['created_at']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{number(row['readiness_score']):.0f}/100</td>
              <td>{int(number(row['difficulty_tier']))}</td>
              <td>{esc(str(row['progression']).title())}</td>
              <td>{esc(str(row['risk_level']).title())}</td>
              <td>{esc(row['recovery_trend'])}</td>
              <td>{number(row['ai_confidence_score']):.0f}%</td>
              <td>{number(row['recommendation_reliability']):.0f}%</td>
            </tr>
            """
            for row in prescriptions
        ) or '<tr><td colspan="10" class="muted">No adaptive prescriptions recorded.</td></tr>'

        decision_cards = "".join(
            f"""
            <div class="card alert {'danger' if row['risk_level'] == 'high' else 'warning' if row['risk_level'] == 'moderate' else ''}">
              <div class="toolbar"><h2>{esc(row['patient_id'])} · L{int(number(row['level']))}</h2><span class="badge">{number(row['readiness_score']):.0f}/100</span></div>
              <p class="muted">{esc(row['rationale'])}</p>
              <p><strong>Explainable AI:</strong> {esc(self.explainable_why(row))}</p>
              <p><strong>Override:</strong> {esc(row['override_recommendation'])}</p>
              {self.override_form(row)}
            </div>
            """
            for row in prescriptions[:6]
        ) or '<div class="card muted">Adaptive decisions will appear after completed sessions.</div>'
        override_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['created_at']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(row['therapist_id'])}</td>
              <td>{esc(str(row['decision']).title())}</td>
              <td>{esc(row['reason'])}</td>
              <td>{esc(row['therapist_reason'])}</td>
            </tr>
            """
            for row in overrides
        ) or '<tr><td colspan="6" class="muted">No therapist overrides recorded.</td></tr>'
        common_reasons = "".join(
            f'<span class="pill">{esc(reason)} · {count}</span>'
            for reason, count in override_stats["common_reasons"]
        ) or '<span class="pill">No override patterns yet</span>'

        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Adaptive AI Rehabilitation Engine</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        {current_panel}
        <section class="card" style="margin-top:16px">
          <h2>System Transparency</h2>
          <div class="toolbar" style="justify-content:flex-start">
            <span class="pill">Decision Source: Adaptive AI Engine</span>
            <span class="pill">Safety Logic: Rule-Based Logic</span>
            <span class="pill">Communication: Optional LLM Enhancement</span>
          </div>
        </section>
        <section class="grid stats three" style="margin-top:24px; margin-bottom:32px;">
          {self.stat_card('Weekly ROM Gain', f"{metrics['weekly_rom_improvement']:+.1f} deg", 'Research endpoint', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>')}
          {self.stat_card('Accuracy Change', f"{metrics['accuracy_improvement']:+.1f}%", 'Recent performance delta', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline></svg>')}
          {self.stat_card('Pain-Adjusted Score', f"{metrics['pain_adjusted_performance']:.1f}", 'Accuracy weighted by pain', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>')}
          {self.stat_card('Session Adherence', f"{metrics['session_adherence']:.0f}%", 'Consistency estimate', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>')}
          {self.stat_card('Difficulty Progression', f"{metrics['difficulty_progression']:+.1f}", 'Tier movement', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 2 13 9 20 9"></polyline><path d="M13 2L20 9"></path><path d="M12 21H3v-8l9-9"></path></svg>')}
          {self.stat_card('Forearm Progress', f"{metrics['forearm_progress']:+.1f}", 'Smoothness minus compensation', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>')}
          {self.stat_card('Compensation Frequency', f"{metrics['compensation_frequency']:.0f}%", 'Frames/sessions above threshold', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>')}
          {self.stat_card('Shoulder / Elbow / Trunk', f"{metrics['shoulder_compensation']:.0f}% / {metrics['elbow_compensation']:.0f}% / {metrics['trunk_compensation']:.0f}%", 'Average compensation', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>')}
          {self.stat_card('Movement Efficiency', f"{metrics['movement_efficiency']:.0f}%", 'Upper limb quality', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>')}
        </section>
        <section class="grid stats three" style="margin-top:24px; margin-bottom:32px;">
          {self.stat_card('AI Confidence', f"{override_stats['ai_confidence']:.0f}%", 'Learned from therapist decisions', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>')}
          {self.stat_card('Override Probability', f"{override_stats['override_probability'] * 100:.0f}%", 'Human-in-the-loop estimate', '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>')}
          {self.stat_card('AI Agreement Rate', f"{override_stats['agreement_rate']:.1f}%", f"Based on {override_stats['total']} total reviews", '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>')}
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Most Common Override Reasons</h2>
          <div class="toolbar" style="justify-content:flex-start">{common_reasons}</div>
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('Biomechanical Compensation Trend', {'Compensation': compensation_series, 'Efficiency': efficiency_series}, upper_labels, '%')}</div>
          <div class="card">{self.chart('Adaptive Readiness Trend', {'Readiness': [number(row['readiness_score']) for row in reversed(prescriptions[-16:])]}, [short_date(row['created_at']) for row in reversed(prescriptions[-16:])], 'score')}</div>
        </section>
        <section class="grid two" style="margin-top:16px">{decision_cards}</section>
        <section class="card" style="margin-top:16px">
          <h2>Prescription History</h2>
          <div class="table-container" style="margin-top:16px;">
            <table>
              <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Readiness</th><th>Tier</th><th>Decision</th><th>Risk</th><th>Recovery</th><th>AI Confidence</th><th>Reliability</th></tr></thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Override History</h2>
          <div class="table-container" style="margin-top:16px;">
            <table>
              <thead><tr><th>Date</th><th>Patient</th><th>Therapist</th><th>Decision</th><th>Reason</th><th>Notes</th></tr></thead>
              <tbody>{override_rows}</tbody>
            </table>
          </div>
        </section>
        """
        return Page("Adaptive AI", body, "adaptive")

    def explainable_why(self, row: sqlite3.Row) -> str:
        try:
            data = json.loads(row["explanation_json"] or "{}")
            if data.get("why"):
                return str(data["why"])
        except Exception:
            pass
        return row["rationale"]

    def override_form(self, row: sqlite3.Row) -> str:
        reasons = [
            "Patient Pain Too High",
            "Fatigue Detected",
            "Therapist Observed Compensation",
            "Patient Motivation Issues",
            "Clinical Safety Concern",
            "Progression Too Conservative",
            "Clinical judgement",
        ]
        reason_options = "".join(f"<option>{esc(reason)}</option>" for reason in reasons)
        rid = int(number(row['id']))
        return f"""
        <form method="post" action="/adaptive/override" id="form_{rid}">
          <input type="hidden" name="prescription_id" value="{rid}">
          <input type="hidden" id="decision_{rid}" name="decision" value="accept">
          
          <div style="display: flex; gap: 10px; margin: 12px 0 8px;">
            <button type="button" style="flex: 1; padding: 9px 16px; background: linear-gradient(135deg, #10b981, #059669); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13.5px; box-shadow: 0 2px 8px rgba(16,185,129,0.2); transition: all 0.2s ease;" onclick="document.getElementById('decision_{rid}').value='accept'; document.getElementById('form_{rid}').submit();">✓ Agree</button>
            <button type="button" style="flex: 1; padding: 9px 16px; background: linear-gradient(135deg, #f59e0b, #d97706); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13.5px; box-shadow: 0 2px 8px rgba(245,158,11,0.2); transition: all 0.2s ease;" onclick="var p = document.getElementById('params_{rid}'); p.style.display = (p.style.display === 'none') ? 'grid' : 'none';">✎ Modify</button>
            <button type="button" style="flex: 1; padding: 9px 16px; background: linear-gradient(135deg, #ef4444, #dc2626); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13.5px; box-shadow: 0 2px 8px rgba(239,68,68,0.2); transition: all 0.2s ease;" onclick="document.getElementById('decision_{rid}').value='reject'; document.getElementById('form_{rid}').submit();">✗ Reject</button>
          </div>
          
          <div id="params_{rid}" class="form-grid" style="display:none; border: 1px solid var(--line); padding: 16px; border-radius: 10px; margin-top: 12px; background: var(--bg);">
            <label>Therapist<input name="therapist_id" value="Therapist"></label>
            <label>Reason<select name="reason">{reason_options}</select></label>
            <label>Difficulty Tier<input name="difficulty_tier" type="number" min="1" max="5" value="{int(number(row['difficulty_tier']))}"></label>
            <label>ROM Requirement<input name="required_rom" type="number" step="0.1" value="{number(row['required_rom']):.1f}"></label>
            <label>Repetitions<input name="repetitions" type="number" min="1" value="{int(number(row['repetitions']))}"></label>
            <label>Hold Duration<input name="hold_seconds" type="number" step="0.1" value="{number(row['hold_seconds']):.1f}"></label>
            <label>Progression<select name="progression">
              {self.option('advance', 'Advance', row['progression'])}
              {self.option('maintain', 'Maintain', row['progression'])}
              {self.option('support', 'Support', row['progression'])}
              {self.option('regress', 'Regress', row['progression'])}
            </select></label>
            <label class="full">Therapist Reason<textarea name="therapist_reason" placeholder="Clinical reasoning, observation, or safety note"></textarea></label>
            <button class="full" type="button" style="background: linear-gradient(135deg, var(--primary), var(--primary-2)); color: white; padding: 10px; border: none; border-radius: 8px; font-weight: 600; font-size: 13.5px; cursor: pointer;" onclick="document.getElementById('decision_{rid}').value='modify'; document.getElementById('form_{rid}').submit();">Save Modification</button>
          </div>
        </form>
        """

