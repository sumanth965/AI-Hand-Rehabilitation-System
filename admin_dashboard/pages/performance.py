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



class PerformancePagesMixin:
    def performance(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        analytics = self.repo.exercise_analytics_data(patient)
        
        total_completions = sum(a["completed_count"] for a in analytics)
        total_compensations = sum(a["compensation_count"] for a in analytics)
        best = max(analytics, key=lambda item: item["avg_accuracy"], default=None)
        
        table = "".join(
            f"""
            <tr>
              <td>L{a['level']} - {esc(a['exercise_name'])}</td>
              <td>{a['completed_count']}</td>
              <td>{a['avg_duration']:.1f}s</td>
              <td>{a['avg_smoothness']:.1f}%</td>
              <td>{a['avg_accuracy']:.1f}%</td>
              <td>{a['avg_rom']:.1f}°</td>
              <td><span class="badge {'danger' if a['compensation_count'] > 5 else 'warning' if a['compensation_count'] > 0 else 'success'}">{a['compensation_count']}</span></td>
              <td style="color: {'#10b981' if a['improvement_percentage'] > 0 else '#ef4444' if a['improvement_percentage'] < 0 else 'inherit'}">{a['improvement_percentage']:+.1f}%</td>
            </tr>
            """
            for a in analytics
        ) or '<tr><td colspan="8" class="muted">No exercise data available.</td></tr>'
        
        cv_data = self.repo.coin_vault_analytics(patient)
        cv_section = ""
        if cv_data:
            cv_section = f"""
            <section class="card" style="margin-top:20px;">
              <div class="toolbar">
                <div>
                  <h2>Level 11: Coin Vault — In-Hand Manipulation Telemetry</h2>
                  <p class="muted" style="margin-top:4px;">Task-specific manipulation performance metrics derived from webcam hand landmark kinematics.</p>
                </div>
                <span class="badge primary">Difficulty Tier: {cv_data['difficulty_tier']}</span>
              </div>
              <div class="grid stats four" style="margin-top:16px;">
                {self.stat_card('Manipulation Success', f"{cv_data['manipulation_success_rate']:.1f}%", 'Task Performance')}
                {self.stat_card('Pickup Success', f"{cv_data['pickup_success_rate']:.1f}%", 'Pinch Target Acquisition')}
                {self.stat_card('Translation Success', f"{cv_data['translation_success_rate']:.1f}%", 'Finger-to-Palm Shift')}
                {self.stat_card('Placement Success', f"{cv_data['placement_success_rate']:.1f}%", 'Vault Receptacle Docking')}
              </div>
              <div class="grid stats three" style="margin-top:16px;">
                {self.stat_card('Unintended Drops', str(cv_data['unintended_drops']), 'Grip release outside targets')}
                {self.stat_card('Avg Manipulation Time', f"{cv_data['avg_manipulation_time']:.2f}s", 'Palm translation & hold')}
                {self.stat_card('Total Vault Sessions', str(cv_data['sessions_count']), 'Recorded therapeutic sessions')}
              </div>
            </section>
            """

        cs_data = self.repo.card_shift_analytics(patient)
        cs_section = ""
        if cs_data:
            cs_section = f"""
            <section class="card" style="margin-top:20px;">
              <div class="toolbar">
                <div>
                  <h2>Level 12: Card Shift Challenge — Dynamic In-Hand Manipulation</h2>
                  <p class="muted" style="margin-top:4px;">Finger-to-finger card shifting kinematics, latency, and sequence execution.</p>
                </div>
                <span class="badge primary">Difficulty Tier: {cs_data['difficulty_tier']}</span>
              </div>
              <div class="grid stats four" style="margin-top:16px;">
                {self.stat_card('Shift Success Rate', f"{cs_data['success_rate']:.1f}%", 'Task Accuracy')}
                {self.stat_card('Sequence Completion', f"{cs_data['sequence_completion_rate']:.1f}%", 'Pattern Consistency')}
                {self.stat_card('Avg Shift Latency', f"{cs_data['avg_latency']:.2f}s", f"Median: {cs_data['median_latency']:.2f}s")}
                {self.stat_card('Incorrect Contacts', str(cs_data['incorrect_finger_events']), 'Finger Targeting Errors')}
              </div>
              <div class="grid stats three" style="margin-top:16px;">
                {self.stat_card('Successful Shifts', str(cs_data['total_successes']), 'Completed card shifts')}
                {self.stat_card('Total Attempts', str(cs_data['total_attempts']), 'Shift motions detected')}
                {self.stat_card('Total Card Sessions', str(cs_data['sessions_count']), 'Recorded therapeutic sessions')}
              </div>
            </section>
            """

        fi_data = self.repo.finger_isolation_analytics(patient)
        fi_section = ""
        if fi_data:
            fi_section = f"""
            <section class="card" style="margin-top:20px;">
              <div class="toolbar">
                <div>
                  <h2>Level 13: Finger Isolation — Individual Digit Control</h2>
                  <p class="muted" style="margin-top:4px;">Independent finger flexion accuracy, unintended co-movements, and target dwell stability.</p>
                </div>
                <span class="badge primary">Difficulty Tier: {fi_data['difficulty_tier']}</span>
              </div>
              <div class="grid stats four" style="margin-top:16px;">
                {self.stat_card('Isolation Accuracy', f"{fi_data['isolation_accuracy']:.1f}%", 'Overall Digit Control')}
                {self.stat_card('Index (D2) Success', f"{fi_data['index_rate']:.1f}%", 'Index Finger Isolation')}
                {self.stat_card('Middle (D3) Success', f"{fi_data['middle_rate']:.1f}%", 'Middle Finger Isolation')}
                {self.stat_card('Ring / Pinky (D4/D5)', f"{(fi_data['ring_rate'] + fi_data['pinky_rate'])/2:.1f}%", f"D4: {fi_data['ring_rate']:.0f}% | D5: {fi_data['pinky_rate']:.0f}%")}
              </div>
              <div class="grid stats three" style="margin-top:16px;">
                {self.stat_card('Unintended Movements', str(fi_data['unintended_movements']), 'Co-movement events detected')}
                {self.stat_card('Avg Activation Time', f"{fi_data['avg_activation_time']:.2f}s", 'Target contact latency')}
                {self.stat_card('Dwell Stability', f"{fi_data['dwell_successes']} succ / {fi_data['dwell_failures']} fail", 'Target hold performance')}
              </div>
            </section>
            """

        wc_data = self.repo.wrist_control_analytics(patient)
        wc_section = ""
        if wc_data:
            wc_section = f"""
            <section class="card" style="margin-top:20px;">
              <div class="toolbar">
                <div>
                  <h2>Level 14: Wrist Flexion-Extension — Fine Angular Control</h2>
                  <p class="muted" style="margin-top:4px;">Biomechanical wrist flexion-extension kinematics, trajectory accuracy, and hold stability.</p>
                </div>
                <span class="badge primary">Difficulty Tier: {wc_data['difficulty_tier']}</span>
              </div>
              <div class="grid stats four" style="margin-top:16px;">
                {self.stat_card('Target Accuracy', f"{wc_data['target_accuracy']:.1f}%", 'Hit Rate')}
                {self.stat_card('Direction Accuracy', f"{wc_data['direction_accuracy']:.1f}%", 'Proper Motion Vector')}
                {self.stat_card('Hold Stability', f"{wc_data['avg_hold_stability']:.1f}%", 'Postural Steadiness')}
                {self.stat_card('Movement Time', f"{wc_data['avg_movement_time']:.2f}s", 'Execution Speed')}
              </div>
              <div class="grid stats three" style="margin-top:16px;">
                {self.stat_card('Target Error', f"{wc_data['avg_target_error']:.1f}px", 'Mean spatial deviation')}
                {self.stat_card('Overshoot', f"{wc_data['avg_overshoot']:.1f}px", 'Terminal damping error')}
                {self.stat_card('Timeouts / Misses', str(wc_data['target_timeouts']), 'Exceeded time allowance')}
              </div>
            </section>
            """

        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Exercise Analytics Dashboard</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid stats three" style="margin-top:16px">
          {self.stat_card('Top Performing Exercise', best['exercise_name'] if best else '-', f'{best["avg_accuracy"]:.1f}% avg accuracy' if best else '')}
          {self.stat_card('Total Exercise Completions', str(total_completions), 'Across all levels')}
          {self.stat_card('Compensations Logged', str(total_compensations), 'Clinical biomechanical alerts')}
        </section>
        {cv_section}
        {cs_section}
        {fi_section}
        {wc_section}
        <section class="card" style="margin-top:16px">
          <h2>Clinical Exercise Telemetry</h2>
          <div class="table-container" style="margin-top:24px;">
<table>
            <thead>
              <tr>
                <th>Exercise / Level</th>
                <th>Completions</th>
                <th>Avg Duration</th>
                <th>Avg Smoothness</th>
                <th>Avg Accuracy</th>
                <th>Avg ROM</th>
                <th>Compensations</th>
                <th>Improvement Rate</th>
              </tr>
            </thead>
            <tbody>{table}</tbody>
          </table>
</div>
        </section>
        """
        return Page("Exercise Analytics", body, "performance")

