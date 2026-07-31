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



class PatientPagesMixin:
    def patients(self, params: dict[str, str]) -> Page:
        q = params.get("q", "").lower()
        stage = params.get("stage", "")
        selected = params.get("patient", "")
        rows = self.repo.patients()
        if q:
            rows = [row for row in rows if q in " ".join(str(row[k] or "") for k in row.keys()).lower()]
        if stage:
            rows = [row for row in rows if row["rehab_stage"] == stage]
        selected_row = self.repo.patient(selected) if selected else None
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(row['id_number'] or '-')}</td>
              <td><a href="/patients?patient={quote(row['name'])}"><strong>{esc(row['name'])}</strong></a><div class="muted">{esc(row['gender'] or 'Gender not set')}</div></td>
              <td>{esc(row['age'] or '-')}</td>
              <td>{esc(row['injury_type'] or row['age_group'] or 'Not specified')}</td>
              <td>{esc(short_date(row['registration_date']))}</td>
              <td>{esc(short_date(row['last_session']))}</td>
              <td><span class="badge">{esc(self.recovery_status(row))}</span></td>
              <td>{int(row['sessions_count'])}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_rom']):.1f} deg</td>
              <td><a class="button secondary" href="/patients?patient={quote(row['name'])}">View Profile</a></td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="11" class="muted">No matching patients.</td></tr>'
        profile = self.patient_profile(selected_row) if selected_row else self.patient_form(None)
        body = f"""
        <section class="grid two">
          <div class="card">
            <div class="toolbar">
              <h2>Patient Management</h2>
              <form method="get" class="toolbar">
                <input name="q" value="{esc(params.get('q',''))}" placeholder="Search patients">
                <select name="stage">
                  {self.option('', 'All stages', stage)}
                  {self.option('Acute', 'Acute', stage)}
                  {self.option('Subacute', 'Subacute', stage)}
                  {self.option('Chronic', 'Chronic', stage)}
                  {self.option('Maintenance', 'Maintenance', stage)}
                </select>
                <button>Filter</button>
              </form>
            </div>
            <div class="table-container">
              <table id="patientsTable">
                <thead><tr><th onclick="sortTable('patientsTable',0)">Patient ID</th><th onclick="sortTable('patientsTable',1)">Patient Name</th><th>Age</th><th>Condition / Injury</th><th>Registration Date</th><th>Last Session Date</th><th>Recovery Status</th><th>Sessions</th><th>Accuracy</th><th>ROM</th><th></th></tr></thead>
                <tbody>{table_rows}</tbody>
              </table>
            </div>
          </div>
          {profile}
        </section>
        """
        return Page("Patient Management", body, "patients")

    def patient_form(self, row: sqlite3.Row | None) -> str:
        name = row["name"] if row else ""
        return f"""
        <div class="card">
          <h2>{'Edit Patient Profile' if row else 'Register Patient'}</h2>
          <form method="post" action="/patients/save" class="form-grid">
            <label>Name<input name="name" value="{esc(name)}" {'readonly' if row else ''} required></label>
            <label>ID Number (Login)<input name="id_number" value="{esc(row['id_number'] if row else '')}" placeholder="Optional custom ID"></label>
            <label>Age<input name="age" type="number" min="0" max="120" value="{esc(row['age'] if row else '')}"></label>
            <label>Gender<input name="gender" value="{esc(row['gender'] if row else '')}" placeholder="Female, Male, Other"></label>
            <label>Age group<input name="age_group" value="{esc(row['age_group'] if row else '')}" placeholder="adult, senior"></label>
            <label>Injury type<input name="injury_type" value="{esc(row['injury_type'] if row else '')}" placeholder="Stroke, fracture, tendon injury"></label>
            <label>Rehabilitation stage
              <select name="rehab_stage">
                {self.option('', 'Select stage', row['rehab_stage'] if row else '')}
                {self.option('Acute', 'Acute', row['rehab_stage'] if row else '')}
                {self.option('Subacute', 'Subacute', row['rehab_stage'] if row else '')}
                {self.option('Chronic', 'Chronic', row['rehab_stage'] if row else '')}
                {self.option('Maintenance', 'Maintenance', row['rehab_stage'] if row else '')}
              </select>
            </label>
            <label class="full">Assigned exercises<textarea name="assigned_exercises">{esc(row['assigned_exercises'] if row else '')}</textarea></label>
            <label class="full">Therapist notes<textarea name="therapist_notes">{esc(row['therapist_notes'] if row else '')}</textarea></label>
            <div class="full toolbar">
              <button>Save Patient</button>
              {f'<a class="button secondary" href="/patients?patient={quote(name)}">View History</a>' if row else ''}
            </div>
          </form>
        </div>
        """

    def patient_profile(self, row: sqlite3.Row) -> str:
        sessions = self.repo.sessions(row["name"], limit=12)
        sessions_chrono = self.repo.sessions_chrono(row["name"])
        adaptive = self.repo.latest_adaptive_prescription(row["name"])
        forearm = self.repo.latest_forearm_assessment(row["name"])
        upper_limb = self.repo.latest_upper_limb_assessment(row["name"])
        coaching = self.repo.sensei_history(row["name"], limit=10)
        clinical = self.repo.clinical_intel.get_clinical_profile(row["name"])
        pred = recovery_prediction(sessions_chrono)
        readiness = number(adaptive["readiness_score"]) if adaptive else clinical["health_score"]
        latest_session = sessions_chrono[-1] if sessions_chrono else None
        recovery_score_value = calculated_functional_recovery_score(latest_session) if latest_session else 0.0
        recovery_category_value = recovery_category(recovery_score_value) if latest_session else "Not started"
        pain_before = number(row_value(latest_session, "pain_before_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_after = number(row_value(latest_session, "pain_after_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_delta = number(row_value(latest_session, "pain_difference", 0)) if latest_session else 0
        recent_notes = self.repo.notes(row["name"])[:5]
        notes_rows = "".join(
            f"<tr><td>{esc(short_date(note['created_at']))}</td><td>{esc(note['therapist_name'])}</td><td>{esc(note['note'])}</td><td>{esc(note['recommendation'])}</td></tr>"
            for note in recent_notes
        ) or '<tr><td colspan="4" class="muted">No therapist notes recorded.</td></tr>'
        history = "".join(
            f"<tr><td>{esc(short_date(s['timestamp']))}</td><td>{esc(exercise_for_level(s['level']))}</td><td>{number(s['avg_accuracy']):.1f}%</td><td>{number(s['avg_hand_angle']):.1f} deg</td><td>{esc(format_duration(s['duration']))}</td></tr>"
            for s in sessions
        ) or '<tr><td colspan="5" class="muted">No rehabilitation history yet.</td></tr>'
        if adaptive:
            adaptive_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>AI Prescription Panel</h2>
              <div class="grid three">
                {self.stat_card('Difficulty Tier', str(int(number(adaptive['difficulty_tier']))), f"{adaptive['progression'].title()} progression")}
                {self.stat_card('Readiness Score', f"{number(adaptive['readiness_score']):.0f}/100", 'Adaptive AI Engine')}
                {self.stat_card('Risk Level', adaptive['risk_level'].title(), f"Recovery: {adaptive['recovery_trend']}")}
                {self.stat_card('Target / Speed', f"{number(adaptive['target_scale']):.2f}x / {number(adaptive['speed_scale']):.2f}x", 'Exercise adaptation')}
                {self.stat_card('ROM / Reps', f"{number(adaptive['required_rom']):.0f} deg / {int(number(adaptive['repetitions']))}", f"{number(adaptive['hold_seconds']):.1f}s hold")}
                {self.stat_card('Rotation Tolerance', f"{number(adaptive['rotation_tolerance']):.0f} deg", f"{number(adaptive['time_limit']):.0f}s time limit")}
              </div>
              <p class="muted" style="margin-top:12px">{esc(adaptive['rationale'])}</p>
              <p><strong>Override recommendation:</strong> {esc(adaptive['override_recommendation'])}</p>
              <p><strong>Decision source:</strong> Adaptive AI Engine; <strong>Safety logic:</strong> Rule-Based Logic; <strong>LLM:</strong> Optional communication enhancement only.</p>
            </div>
            """
        else:
            adaptive_panel = '<div class="card muted" style="margin-top:16px">No adaptive AI recommendation has been generated yet.</div>'

        if forearm:
            forearm_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Forearm Classification</h2>
              <div class="table-container">
                <table>
                  <tbody>
                    <tr><th>Latest Class</th><td>{esc(forearm['movement_class'])}</td></tr>
                    <tr><th>Rotation Angle</th><td>{number(forearm['rotation_angle']):.1f} deg</td></tr>
                    <tr><th>Smoothness</th><td>{number(forearm['smoothness']) * 100:.0f}%</td></tr>
                    <tr><th>Compensation</th><td>{number(forearm['compensation_score']) * 100:.0f}%</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            """
        else:
            forearm_panel = '<div class="card muted" style="margin-top:16px">No forearm classification recorded yet.</div>'
        if upper_limb:
            upper_limb_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Upper Limb Compensation</h2>
              <div class="grid three">
                {self.stat_card('Compensation', f"{number(upper_limb['compensation_score']) * 100:.0f}%", esc(upper_limb['feedback']))}
                {self.stat_card('Efficiency', f"{number(upper_limb['movement_efficiency']):.0f}%", f"{esc(upper_limb['side'])} side")}
                {self.stat_card('Trunk Lean', f"{number(upper_limb['trunk_lean_angle']):.1f} deg", 'Pose estimate')}
              </div>
              <div class="table-container">
                <table style="margin-top:12px">
                  <tbody>
                    <tr><th>Shoulder Angle</th><td>{number(upper_limb['shoulder_angle']):.1f} deg</td></tr>
                    <tr><th>Elbow Angle</th><td>{number(upper_limb['elbow_angle']):.1f} deg</td></tr>
                    <tr><th>Shoulder / Elbow / Trunk Compensation</th><td>{number(upper_limb['shoulder_compensation']) * 100:.0f}% / {number(upper_limb['elbow_compensation']) * 100:.0f}% / {number(upper_limb['trunk_compensation']) * 100:.0f}%</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            """
        else:
            upper_limb_panel = '<div class="card muted" style="margin-top:16px">No upper limb compensation assessment recorded yet.</div>'

        if coaching:
            coaching_rows = "".join(
                f"<tr><td>{esc(short_date(c['created_at']))}</td><td>{esc(exercise_for_level(c['level']))}</td><td>{esc(row_value(c, 'deterministic_message', c['message']))}</td><td>{esc(row_value(c, 'llm_enhanced_message', ''))}</td><td>{esc(row_value(c, 'coaching_trigger', self.sensei_trigger(c)))}</td></tr>"
                for c in coaching
            )
            coaching_panel = f"""
            <div class="card" style="margin-top:16px">
              <h2>Virtual Sensei Panel</h2>
              <div class="table-container">
                <table><thead><tr><th>Date</th><th>Exercise</th><th>Generated Coaching Message</th><th>LLM Enhanced Message</th><th>Coaching Trigger</th></tr></thead><tbody>{coaching_rows}</tbody></table>
              </div>
            </div>
            """
        else:
            coaching_panel = '<div class="card muted" style="margin-top:16px">No coaching history generated yet.</div>'

        insights_html = "".join(f"<li>{esc(i)}</li>" for i in clinical["insights"])
        recs_html = "".join(f"<li>{esc(r)}</li>" for r in clinical["recommendations"])
        risks_html = "".join(f'<span class="badge" style="color:var(--danger)">{esc(r)}</span>' for r in clinical["detected_risks"]) or '<span class="muted">No immediate risks detected.</span>'
        
        clinical_panel = f"""
        <div class="card" style="margin-top:16px; border-left: 4px solid var(--primary)">
          <h2>Clinical Health & Decision Support</h2>
          <div class="grid three">
            {self.stat_card('Health Score', f"{clinical['health_score']}/100", f"Trend: {clinical['trend']}")}
            {self.stat_card('Recovery Stage', clinical['recovery_stage'], 'Based on ROM progression')}
            {self.stat_card('Risk Level', clinical['risk_level'], 'Clinical risk assessment')}
          </div>
          <div style="margin-top:16px">
            <h3>Detected Risks</h3>
            <div style="display:flex; gap:8px; flex-wrap:wrap">{risks_html}</div>
          </div>
          <div class="grid two" style="margin-top:16px">
            <div>
              <h3>Rehabilitation Insights</h3>
              <ul style="margin:0; padding-left:20px">{insights_html}</ul>
            </div>
            <div>
              <h3>Therapist Recommendations</h3>
              <ul style="margin:0; padding-left:20px">{recs_html}</ul>
            </div>
          </div>
        </div>
        """

        return f"""
        <div>
          <div class="card" style="margin-bottom:16px">
            <div class="toolbar">
              <h2>Patient Profile</h2>
              <a class="button" href="/report.pdf?patient={quote(row['name'])}">Download PDF Report</a>
            </div>
            <div class="table-container">
              <table>
                <tbody>
                  <tr><th>Patient ID</th><td>{esc(row['id_number'] or row['name'])}</td><th>Name</th><td>{esc(row['name'])}</td></tr>
                  <tr><th>Age</th><td>{esc(row['age'] or '-')}</td><th>Gender</th><td>{esc(row['gender'] or '-')}</td></tr>
                  <tr><th>Condition</th><td>{esc(row['injury_type'] or '-')}</td><th>Registration Date</th><td>{esc(short_date(row['registration_date']))}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="grid three" style="margin-bottom:16px">
            {self.stat_card('Total Sessions', str(int(number(row['sessions_count']))), 'Stored rehabilitation sessions')}
            {self.stat_card('Recovery Prediction', f"{pred:.1f}%" if pred >= 0 else 'Need more data', 'Projected ROM trend')}
            {self.stat_card('Current Recovery Stage', clinical['recovery_stage'], f"Status: {self.recovery_status(row)}")}
            {self.stat_card('Readiness Score', f"{readiness:.0f}/100", 'Adaptive or clinical readiness')}
            {self.stat_card('Overall Accuracy', f"{number(row['avg_accuracy']):.1f}%", 'Average across sessions')}
            {self.stat_card('Maximum ROM Achieved', f"{number(row['max_rom']):.1f} deg", 'Best recorded hand angle')}
            {self.stat_card('Recovery Score', f"{recovery_score_value:.0f}/100", recovery_category_value)}
            {self.stat_card('Pain Summary', f"{pain_before:.0f}/10 to {pain_after:.0f}/10", f"Difference {pain_delta:+.0f}")}
            {self.stat_card('Exercise Compliance', 'Future Feature', 'Assigned vs completed sessions')}
          </div>
          <div class="card" style="margin-top:16px">
            <h2>Therapist Notes Panel</h2>
            <div class="table-container">
              <table><thead><tr><th>Date</th><th>Therapist</th><th>Clinical Observations</th><th>Latest Recommendations</th></tr></thead><tbody>{notes_rows}</tbody></table>
            </div>
          </div>
          <div class="card muted" style="margin-top:16px">
            <h2>Compensation Analysis (Coming Soon)</h2>
            <p>Future MediaPipe Hands + MediaPipe Pose integration for shoulder lifting, elbow drift, trunk leaning, and compensatory movement score.</p>
          </div>
          {self.patient_form(row)}
          {clinical_panel}
          <div class="card" style="margin-top:16px">
            <div class="toolbar">
              <h2>Complete Rehabilitation History</h2>
              <form method="post" action="/patients/delete" onsubmit="return confirm('Delete this patient profile and notes? Session records are preserved.');">
                <input type="hidden" name="name" value="{esc(row['name'])}">
                <button class="danger">Delete Patient</button>
              </form>
            </div>
            <div class="table-container">
              <table><thead><tr><th>Date</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead><tbody>{history}</tbody></table>
            </div>
          </div>
          {adaptive_panel}
          {coaching_panel}
          {forearm_panel}
          {upper_limb_panel}
        </div>
        """

    def recovery_status(self, row: sqlite3.Row) -> str:
        clinical = self.repo.clinical_intel.get_clinical_profile(row["name"])
        return recovery_status_from_metrics(
            number(row["avg_accuracy"]),
            number(row["avg_rom"]),
            clinical["risk_level"],
            int(number(row["sessions_count"])),
        )

    def prediction_badge(self, patient: str) -> str:
        pred = recovery_prediction(self.repo.sessions_chrono(patient))
        if pred < 0:
            return '<span class="badge">Need data</span>'
        return f'<span class="badge">{pred:.1f}%</span>'

