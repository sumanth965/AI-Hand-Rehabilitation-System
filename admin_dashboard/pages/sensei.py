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



class SenseiPagesMixin:
    def sensei_review(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        rows = self.repo.sensei_history(patient, limit=120)
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['created_at']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{esc(row_value(row, 'deterministic_message', row['message']))}</td>
              <td>{esc(row_value(row, 'llm_enhanced_message', ''))}</td>
              <td>{esc(row_value(row, 'coaching_trigger', self.sensei_trigger(row)))}</td>
              <td>{esc(row_value(row, 'decision_source', 'Adaptive AI Engine'))}</td>
              <td>{esc(row_value(row, 'llm_status', 'not_requested'))}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="8" class="muted">No Virtual Sensei messages recorded yet.</td></tr>'
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Virtual Sensei Review Panel</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
          <input id="senseiSearch" oninput="filterTable('senseiSearch','senseiTable')" placeholder="Search coaching messages">
          <div class="table-container" style="margin-top:24px;">
            <table id="senseiTable">
              <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Generated Coaching Message</th><th>LLM Enhanced Message</th><th>Coaching Trigger</th><th>Decision Source</th><th>LLM Status</th></tr></thead>
              <tbody>{table_rows}</tbody>
            </table>
          </div>
        </section>
        """
        return Page("Virtual Sensei Review", body, "sensei")

    def sensei_trigger(self, row: sqlite3.Row) -> str:
        stored_trigger = row_value(row, "coaching_trigger", "")
        if stored_trigger:
            return str(stored_trigger)
        try:
            data = json.loads(row["context_json"] or "{}")
            for key in ("trigger", "reason", "why", "event"):
                if data.get(key):
                    return str(data[key])
            if data:
                return ", ".join(f"{k}: {v}" for k, v in list(data.items())[:2])
        except Exception:
            pass
        message = str(row["message"] or "").lower()
        if "improved" in message:
            return "Performance improvement detected"
        if "pain" in message:
            return "Pain score safety cue"
        if "smooth" in message or "rotation" in message:
            return "Movement quality coaching"
        return "Session performance feedback"

