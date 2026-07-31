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



class ReportPagesMixin:
    def reports(self, params: dict[str, str]) -> Page:
        selected = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in self.repo.patients())
        patient = self.repo.patient(selected) if selected else None
        summary = ""
        if patient:
            sessions = self.repo.sessions_chrono(selected)
            pred = recovery_prediction(sessions)
            summary = f"""
            <div class="grid three" style="margin-top:16px">
              {self.stat_card('Sessions', str(len(sessions)), selected)}
              {self.stat_card('Average Accuracy', f"{number(patient['avg_accuracy']):.1f}%", 'Exercise performance')}
              {self.stat_card('Average ROM', f"{number(patient['avg_rom']):.1f} deg", 'ROM analysis')}
            </div>
            <div class="card" style="margin-top:16px">
              <h2>Report Preview</h2>
              <p><strong>Patient:</strong> {esc(patient['name'])}</p>
              <p><strong>Injury:</strong> {esc(patient['injury_type'] or 'Not specified')}</p>
              <p><strong>Stage:</strong> {esc(patient['rehab_stage'] or 'Not specified')}</p>
              <p><strong>Recovery prediction:</strong> {f'{pred:.1f}%' if pred >= 0 else 'Need more data'}</p>
              <p><strong>Therapist observations:</strong> {esc(patient['therapist_notes'] or 'No profile observations recorded.')}</p>
              <div class="toolbar" style="justify-content:flex-start">
                <a class="button" href="/report.pdf?patient={quote(selected)}">Download PDF</a>
                <button type="button" class="button secondary" onclick="window.print()">Print Report</button>
              </div>
            </div>
            """
        body = f"""
        <section class="card">
          <h2>Recovery Reports</h2>
          <form method="get" class="toolbar">
            <select name="patient"><option value="">Select patient</option>{patient_options}</select>
            <button>Build Report</button>
          </form>
        </section>
        {summary}
        """
        return Page("Recovery Reports", body, "reports")

    def report_chart_image(self, sessions: list[sqlite3.Row]) -> io.BytesIO:
        labels = [short_date(row["timestamp"]) for row in sessions[-10:]]
        rom = [number(row["avg_hand_angle"]) for row in sessions[-10:]]
        acc = [number(row["avg_accuracy"]) for row in sessions[-10:]]
        pain_before = [number(row_value(row, "pain_before_session", row["pain_level"])) for row in sessions[-10:]]
        pain_after = [number(row_value(row, "pain_after_session", row["pain_level"])) for row in sessions[-10:]]
        recovery_scores = [calculated_functional_recovery_score(row) for row in sessions[-10:]]
        fig, ax = plt.subplots(figsize=(7.2, 3.1), dpi=120)
        ax.plot(labels, rom, marker="o", linewidth=2, label="ROM")
        ax.plot(labels, acc, marker="o", linewidth=2, label="Accuracy")
        ax.plot(labels, pain_before, marker="o", linewidth=2, label="Pain Before")
        ax.plot(labels, pain_after, marker="o", linewidth=2, label="Pain After")
        ax.plot(labels, recovery_scores, marker="o", linewidth=2, label="Recovery Score")
        ax.set_title("ROM, Accuracy, Pain, and Recovery Trend", loc="left", fontsize=11, fontweight="bold")
        ax.grid(True, color="#dbe7f0")
        ax.tick_params(axis="x", labelrotation=20, labelsize=7)
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        image = io.BytesIO()
        fig.savefig(image, format="png", bbox_inches="tight")
        plt.close(fig)
        image.seek(0)
        return image

    def report_pdf(self, patient_name: str) -> bytes:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.utils import ImageReader
            from reportlab.pdfgen import canvas
        except Exception as exc:
            return f"PDF export requires reportlab. Import error: {exc}".encode("utf-8")

        patient = self.repo.patient(patient_name)
        sessions = self.repo.sessions_chrono(patient_name)
        notes = self.repo.notes(patient_name)
        adaptive = self.repo.latest_adaptive_prescription(patient_name)
        metrics = self.repo.research_metrics(patient_name)
        clinical = self.repo.clinical_intel.get_clinical_profile(patient_name) if patient_name else None
        sensei = self.repo.sensei_history(patient_name, limit=8)
        pred = recovery_prediction(sessions)
        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=letter)
        width, height = letter
        y = height - 50
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(50, y, "AI Hand Rehabilitation - Therapist Report")
        y -= 32
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y, f"Generated: {datetime.now().strftime('%d %B %Y %H:%M')}")
        y -= 26
        if patient:
            fields = [
                ("Patient", patient["name"]),
                ("Age", patient["age"] or "-"),
                ("Gender", patient["gender"] or "-"),
                ("Injury Type", patient["injury_type"] or "-"),
                ("Rehabilitation Stage", patient["rehab_stage"] or "-"),
                ("Assigned Exercises", patient["assigned_exercises"] or "-"),
            ]
            for label, value in fields:
                pdf.drawString(50, y, f"{label}: {value}")
                y -= 16
        y -= 8
        avg_acc = sum(number(s["avg_accuracy"]) for s in sessions) / len(sessions) if sessions else 0
        avg_rom = sum(number(s["avg_hand_angle"]) for s in sessions) / len(sessions) if sessions else 0
        max_rom = max([number(s["avg_hand_angle"]) for s in sessions], default=0)
        avg_pain = sum(number(s["pain_level"]) for s in sessions) / len(sessions) if sessions else 0
        readiness = number(adaptive["readiness_score"]) if adaptive else number(clinical["health_score"] if clinical else 0)
        latest_session = sessions[-1] if sessions else None
        pain_before = number(row_value(latest_session, "pain_before_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_after = number(row_value(latest_session, "pain_after_session", row_value(latest_session, "pain_level", 0))) if latest_session else 0
        pain_difference = number(row_value(latest_session, "pain_difference", 0)) if latest_session else 0
        pain_trend = sum(number(row_value(row, "pain_difference", 0)) for row in sessions) / len(sessions) if sessions else 0
        recovery_score_value = calculated_functional_recovery_score(latest_session) if latest_session else 0
        recovery_category_value = recovery_category(recovery_score_value) if latest_session else "Not started"
        recovery_trend = (
            calculated_functional_recovery_score(sessions[-1]) - calculated_functional_recovery_score(sessions[0])
            if len(sessions) >= 2
            else 0.0
        )
        summary = [
            f"Completed Sessions: {len(sessions)}",
            f"Average Accuracy: {avg_acc:.1f}%",
            f"Average ROM: {avg_rom:.1f} degrees",
            f"Maximum ROM Achieved: {max_rom:.1f} degrees",
            f"Average Pain Score: {avg_pain:.1f}/10",
            f"Pain Before Latest Session: {pain_before:.0f}/10",
            f"Pain After Latest Session: {pain_after:.0f}/10",
            f"Pain Difference Latest Session: {pain_difference:+.0f}",
            f"Pain Improvement Trend: {pain_trend:+.1f} average after-before",
            f"Functional Recovery Score: {recovery_score_value:.0f}/100",
            f"Recovery Category: {recovery_category_value}",
            f"Recovery Progress Trend: {recovery_trend:+.1f} points",
            f"Readiness Score: {readiness:.0f}/100",
            f"Current Recovery Stage: {clinical['recovery_stage'] if clinical else 'Unknown'}",
            f"Recovery Prediction: {pred:.1f}%" if pred >= 0 else "Recovery Prediction: Need more data",
        ]
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Session Summary")
        y -= 18
        pdf.setFont("Helvetica", 10)
        for line in summary:
            pdf.drawString(60, y, line)
            y -= 15
        if adaptive:
            y -= 8
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(50, y, "Adaptive AI Prescription")
            y -= 18
            pdf.setFont("Helvetica", 9)
            adaptive_lines = [
                f"Readiness Score: {number(adaptive['readiness_score']):.0f}/100",
                f"Difficulty Tier: {int(number(adaptive['difficulty_tier']))}",
                f"AI Prescription: {int(number(adaptive['repetitions']))} reps, {number(adaptive['required_rom']):.0f} deg ROM, {number(adaptive['hold_seconds']):.1f}s holds",
                f"Risk Level: {adaptive['risk_level']}",
                f"Recovery Trend: {adaptive['recovery_trend']}",
                f"Progression Recommendation: {adaptive['progression']}",
                f"Adaptive Rationale: {adaptive['rationale']}",
                f"Override Recommendation: {adaptive['override_recommendation']}",
            ]
            for line in adaptive_lines:
                pdf.drawString(60, y, str(line)[:110])
                y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Research Metrics")
        y -= 18
        pdf.setFont("Helvetica", 9)
        research_lines = [
            f"Weekly ROM Improvement: {metrics['weekly_rom_improvement']:+.1f} degrees",
            f"Accuracy Improvement: {metrics['accuracy_improvement']:+.1f}%",
            f"Pain-Adjusted Performance: {metrics['pain_adjusted_performance']:.1f}",
            f"Session Adherence: {metrics['session_adherence']:.0f}%",
            f"Difficulty Progression: {metrics['difficulty_progression']:+.1f}",
            f"Forearm Progress: {metrics['forearm_progress']:+.1f}",
            f"Compensation Frequency: {metrics['compensation_frequency']:.0f}%",
            f"Shoulder / Elbow / Trunk Compensation: {metrics['shoulder_compensation']:.0f}% / {metrics['elbow_compensation']:.0f}% / {metrics['trunk_compensation']:.0f}%",
            f"Movement Efficiency: {metrics['movement_efficiency']:.0f}%",
        ]
        for line in research_lines:
            pdf.drawString(60, y, line)
            y -= 13
        if sessions:
            if y < 310:
                pdf.showPage()
                y = height - 50
            y -= 10
            pdf.setFont("Helvetica-Bold", 13)
            pdf.drawString(50, y, "Progress Charts")
            y -= 200
            chart = ImageReader(self.report_chart_image(sessions))
            pdf.drawImage(chart, 50, y, width=500, height=180, preserveAspectRatio=True, mask="auto")
            y -= 20
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Recent Sessions")
        y -= 18
        pdf.setFont("Helvetica", 9)
        for row in sessions[-10:]:
            if y < 80:
                pdf.showPage()
                y = height - 50
            line = (
                f"{short_date(row['timestamp'])} | {exercise_for_level(row['level'])} | "
                f"Acc {number(row['avg_accuracy']):.1f}% | ROM {number(row['avg_hand_angle']):.1f} | "
                f"Pain {int(number(row_value(row, 'pain_before_session', row['pain_level'])))}/10 to "
                f"{int(number(row_value(row, 'pain_after_session', row['pain_level'])))} /10 | "
                f"Recovery {calculated_functional_recovery_score(row):.0f}/100"
            )
            pdf.drawString(60, y, line[:110])
            y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Virtual Sensei Summary")
        y -= 18
        pdf.setFont("Helvetica", 9)
        sensei_lines = [f"{short_date(row['created_at'])}: {row['message']}" for row in sensei] or ["No Virtual Sensei messages recorded."]
        for line in sensei_lines:
            if y < 80:
                pdf.showPage()
                y = height - 50
            pdf.drawString(60, y, str(line)[:110])
            y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Therapist Observations")
        y -= 18
        pdf.setFont("Helvetica", 9)
        observation_lines = [
            f"{n['therapist_name']}: {n['note']} Recommendation: {n['recommendation'] or '-'}"
            for n in notes[:6]
        ] or ["No therapist notes recorded."]
        for line in observation_lines:
            for chunk in [line[i:i + 95] for i in range(0, len(line), 95)]:
                if y < 80:
                    pdf.showPage()
                    y = height - 50
                pdf.drawString(60, y, chunk)
                y -= 13
        pdf.save()
        return buf.getvalue()

