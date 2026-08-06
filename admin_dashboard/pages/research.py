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



class ResearchPagesMixin:
    def research_dashboard(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        
        sessions = self.repo.sessions_chrono(patient)
        labels = [short_date(row["timestamp"]) for row in sessions[-16:]]
        
        # 1. Movement Quality Trend
        mq_trend = [number(row.get("movement_quality_score", number(row["avg_accuracy"]) * 0.65 + 25)) for row in sessions[-16:]]
        
        # 2. ROM Improvement Trend
        rom_trend = [number(row["avg_hand_angle"]) for row in sessions[-16:]]
        
        # 3. Pain Delta
        pain_before = [number(row_value(row, "pain_before_session", row["pain_level"])) for row in sessions[-16:]]
        pain_after = [number(row_value(row, "pain_after_session", row["pain_level"])) for row in sessions[-16:]]
        
        # 4. Recovery Prediction Accuracy
        actual_rec = [min(100.0, number(row["avg_hand_angle"]) / 90.0 * 100.0) for row in sessions[-16:]]
        predicted_rec = []
        for index in range(len(sessions[-16:])):
            pred = recovery_prediction(sessions[: max(0, len(sessions) - len(sessions[-16:])) + index + 1])
            predicted_rec.append(pred if pred >= 0 else actual_rec[index])
            
        # 5. Readiness History
        prescriptions = list(reversed(self.repo.adaptive_history(patient, limit=16)))
        readiness_labels = [short_date(row["created_at"]) for row in prescriptions]
        readiness_scores = [number(row["readiness_score"]) for row in prescriptions]
        
        # 6. Difficulty Adjustments
        difficulty_tiers = [number(row.get("difficulty_tier", 2.0)) for row in prescriptions]
        
        # 7. Therapist Agreement Rate
        override_stats = self.repo.override_stats(patient)
        agreement_rate = override_stats["agreement_rate"]
        
        overrides = self.repo.override_history(patient, limit=200)
        agree_cnt = sum(1 for r in overrides if str(r["decision"]).lower() == "accept")
        modify_cnt = sum(1 for r in overrides if str(r["decision"]).lower() == "modify")
        reject_cnt = sum(1 for r in overrides if str(r["decision"]).lower() == "reject")
        total_decisions = len(overrides)
        
        # 8. Demographic Success Rates
        demographics = {"Child": 0.0, "Young Adult": 0.0, "Adult": 0.0, "Senior": 0.0}
        try:
            conn = sqlite3.connect(self.repo.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT AVG(s.functional_recovery_score) 
                FROM sessions s JOIN patients p ON s.patient_id = p.name
                WHERE p.age_group = 'child'
            """)
            demographics["Child"] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT AVG(s.functional_recovery_score) 
                FROM sessions s JOIN patients p ON s.patient_id = p.name
                WHERE p.age_group = 'young_adult'
            """)
            demographics["Young Adult"] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT AVG(s.functional_recovery_score) 
                FROM sessions s JOIN patients p ON s.patient_id = p.name
                WHERE p.age_group = 'adult'
            """)
            demographics["Adult"] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT AVG(s.functional_recovery_score) 
                FROM sessions s JOIN patients p ON s.patient_id = p.name
                WHERE p.age_group = 'senior'
            """)
            demographics["Senior"] = cursor.fetchone()[0] or 0.0
            
            conn.close()
        except Exception as e:
            print(f"Demographics query failed: {e}")

        # Build Demographic Progress Bars HTML
        demo_html = ""
        for group, val in demographics.items():
            demo_html += f"""
            <div style="margin-bottom: 12px;">
              <div class="toolbar" style="font-size: 13px; margin-bottom: 4px;">
                <span>{group}</span>
                <strong>{val:.1f}% Recovery</strong>
              </div>
              <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden;">
                <div style="width: {val}%; height: 100%; background: linear-gradient(90deg, #0088ff, #00ffcc); border-radius: 4px;"></div>
              </div>
            </div>
            """

        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Clinical Research Portal</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        
        <section class="grid stats three" style="margin-top:16px">
          {self.stat_card('AI Agreement Rate', f"{agreement_rate:.1f}%", f"{agree_cnt} Agree / {modify_cnt} Modify / {reject_cnt} Reject")}
          {self.stat_card('Clinical Success Index', f"{demographics['Adult']:.1f}%", 'Average recovery score (Adults)')}
          {self.stat_card('Research Datapoints', f"{len(sessions)} Sessions", 'Confidential biomechanical dataset')}
        </section>

        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('Movement Quality Trends', {'Movement Quality (%)': mq_trend}, labels, '%')}</div>
          <div class="card">{self.chart('ROM Improvement Over Time', {'Range of Motion (deg)': rom_trend}, labels, 'deg')}</div>
          <div class="card">{self.chart('Pain Delta Reduction', {'Pain Before': pain_before, 'Pain After': pain_after}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Recovery Prediction Accuracy', {'Actual Recovery': actual_rec, 'Predicted Recovery': predicted_rec}, labels, '%')}</div>
          <div class="card">{self.chart('Patient Readiness Score History', {'Readiness Score': readiness_scores}, readiness_labels, 'score')}</div>
          <div class="card">
            <h2>Clinical Success by Demographic</h2>
            <div style="margin-top: 15px;">
              {demo_html}
            </div>
          </div>
        </section>
        """
        return Page("Clinical Research Portal", body, "research")

