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



class NotesPagesMixin:
    def notes(self, params: dict[str, str]) -> Page:
        selected = params.get("patient", "")
        selected_session = params.get("session_id", "")
        selected_date = params.get("date", "")
        patients = self.repo.patients()
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in patients)
        session_options = "".join(
            f'<option value="{row["id"]}" {"selected" if str(row["id"]) == selected_session else ""}>{esc(short_date(row["timestamp"]))} - {esc(exercise_for_level(row["level"]))}</option>'
            for row in self.repo.sessions(selected, limit=30)
        )
        notes = self.repo.notes(selected, selected_session, selected_date)
        note_rows = "".join(
            f"""
            <div class="card">
              <div class="toolbar"><strong>{esc(row['patient_name'])}</strong><span class="badge">{esc(row['therapist_name'])}</span></div>
              <p><strong>Clinical observation:</strong> {esc(row['clinical_observation'] or row['note'])}</p>
              <p>{esc(row['note'])}</p>
              <p class="muted"><strong>Recommendation:</strong> {esc(row['recommendation'] or '-')}</p>
              <p class="muted"><strong>Modified:</strong> {esc(short_date(row['modified_at']))}</p>
              <form method="post" action="/notes/save" class="form-grid">
                <input type="hidden" name="note_id" value="{int(number(row['id']))}">
                <input type="hidden" name="patient_name" value="{esc(row['patient_name'])}">
                <input type="hidden" name="session_id" value="{esc(row['session_id'] or '')}">
                <label>Therapist<input name="therapist_name" value="{esc(row['therapist_name'])}"></label>
                <label class="full">Edit note<textarea name="note" required>{esc(row['note'])}</textarea></label>
                <label class="full">Clinical observation<textarea name="clinical_observation">{esc(row['clinical_observation'])}</textarea></label>
                <label class="full">Recommendation<textarea name="recommendation">{esc(row['recommendation'])}</textarea></label>
                <button class="full">Update Note</button>
              </form>
              <span class="muted">Created {esc(short_date(row['created_at']))}</span>
            </div>
            """
            for row in notes
        ) or '<div class="card muted">No therapist notes recorded.</div>'
        body = f"""
        <section class="grid two">
          <div class="card">
            <h2>Therapist Notes</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <select name="session_id"><option value="">All sessions</option>{session_options}</select>
              <input name="date" type="date" value="{esc(selected_date)}">
              <button>Filter</button>
            </form>
            <form method="post" action="/notes/save" class="form-grid">
              <label>Patient<select name="patient_name" required><option value="">Select patient</option>{patient_options}</select></label>
              <label>Session<select name="session_id"><option value="">General note</option>{session_options}</select></label>
              <label>Therapist<input name="therapist_name" value="Therapist"></label>
              <label class="full">Note text<textarea name="note" required></textarea></label>
              <label class="full">Clinical observation<textarea name="clinical_observation"></textarea></label>
              <label class="full">Recommendation<textarea name="recommendation"></textarea></label>
              <button class="full">Add Note</button>
            </form>
          </div>
          <div class="grid">{note_rows}</div>
        </section>
        """
        return Page("Therapist Notes", body, "notes")

