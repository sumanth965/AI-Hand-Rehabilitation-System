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

from .pages.home import HomePageMixin
from .pages.auth import AuthPagesMixin
from .pages.patients import PatientPagesMixin
from .pages.sessions import SessionPagesMixin
from .pages.analytics import AnalyticsPagesMixin
from .pages.adaptive_ai import AdaptiveAIPagesMixin
from .pages.digital_twin import DigitalTwinPagesMixin
from .pages.sensei import SenseiPagesMixin
from .pages.risks import RiskPagesMixin
from .pages.reports import ReportPagesMixin
from .pages.performance import PerformancePagesMixin
from .pages.research import ResearchPagesMixin
from .pages.notes import NotesPagesMixin
from .pages.notifications import NotificationPagesMixin
from .pages.audit import AuditPagesMixin
from .pages.components import ComponentsMixin

class DashboardRenderer(HomePageMixin, AuthPagesMixin, PatientPagesMixin, SessionPagesMixin, AnalyticsPagesMixin, AdaptiveAIPagesMixin, DigitalTwinPagesMixin, SenseiPagesMixin, RiskPagesMixin, ReportPagesMixin, PerformancePagesMixin, ResearchPagesMixin, NotesPagesMixin, NotificationPagesMixin, AuditPagesMixin, ComponentsMixin):

    def __init__(self, repo: DashboardRepository):
        self.repo = repo

    def layout(self, page: Page, params: dict[str, str] | None = None) -> bytes:
        params = params or {}
        theme = params.get("theme", "light")
        nav = [
            ("home", "/", "Overview", "D"),
            ("patients", "/patients", "Patients", "P"),
            ("sessions", "/sessions", "Sessions", "S"),
            ("analytics", "/analytics", "Analytics", "A"),
            ("adaptive", "/adaptive", "AI Insights", "AI"),
            ("sensei", "/sensei", "Sensei Review", "V"),
            ("risks", "/risks", "Risk Detection", "R"),
            ("reports", "/reports", "Reports", "PDF"),
            ("digital_twin", "/digital-twin", "Digital Twin", "DT"),
            ("performance", "/performance", "Exercise Stats", "E"),
            ("research", "/research", "Research Portal", "📊"),
            ("notes", "/notes", "Notes", "N"),
            ("security", "/security", "Security", "🔒"),
            ("audit", "/audit-logs", "Audit Logs", "📋"),
        ]
        nav_html = "".join(
            f'<a class="nav-item {"active" if key == page.active else ""}" '
            f'href="{href}" aria-current="{"page" if key == page.active else "false"}">'
            f'<span class="nav-icon" aria-hidden="true">{icon}</span>'
            f'<span class="nav-label">{label}</span></a>'
            for key, href, label, icon in nav
        )
        toggled_theme = "dark" if theme != "dark" else "light"
        username_val = params.get("_username", "Therapist")
        avatar_initials = username_val[:2].capitalize()

        html_doc = f"""<!doctype html>
    <html lang="en" data-theme="{esc(theme)}">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{esc(page.title)} - Therapist Dashboard</title>
      <link rel="stylesheet" href="/static/css/root.css">
      <link rel="stylesheet" href="/static/css/layout.css">
      <link rel="stylesheet" href="/static/css/dashboard.css">
    </head>
    <body>
      <input type="checkbox" id="sidebar-toggle" class="sidebar-toggle-input" aria-hidden="true">

      <div class="app-shell">
        <aside class="sidebar glass-panel" aria-label="Primary navigation">
          <div class="brand">
            <div class="brand-mark" aria-hidden="true">HR</div>
            <div class="brand-text">
              <strong>Hand Rehab</strong>
              <span>Therapist Console</span>
            </div>
            <label for="sidebar-toggle" class="sidebar-close-btn" role="button" tabindex="0" aria-label="Close navigation">✕</label>
          </div>
          <div class="therapist-profile sidebar-profile">
            <div class="avatar" aria-hidden="true">{esc(avatar_initials)}</div>
            <div class="profile-info">
              <strong>{esc(username_val)}</strong>
              <span>Therapist</span>
            </div>
          </div>
          <nav class="nav-menu" aria-label="Main">
            {nav_html}
            <div class="nav-spacer" style="flex-grow: 1;"></div>
            <a class="nav-item utility-link" href="#" aria-label="Settings"><span class="nav-icon" aria-hidden="true">⚙️</span><span class="nav-label">Settings</span></a>
            <a class="nav-item utility-link text-danger" href="/logout" aria-label="Logout"><span class="nav-icon" aria-hidden="true">🚪</span><span class="nav-label">Logout</span></a>
          </nav>
        </aside>

        <label for="sidebar-toggle" class="sidebar-scrim" aria-hidden="true"></label>

        <main class="main" id="main-content">
          <header class="topbar glass-panel">
            <label for="sidebar-toggle" class="hamburger-btn icon-btn" role="button" tabindex="0" aria-label="Toggle navigation menu">☰</label>
            <div class="search-bar">
              <span class="search-icon" aria-hidden="true">🔍</span>
              <input type="text" placeholder="Search patients, sessions..." class="search-input" aria-label="Search patients and sessions">
            </div>
            <div class="topbar-actions">
              <span class="privacy-badge">🛡️ <span class="privacy-badge-label">Privacy Mode: Active</span></span>
              <a class="icon-btn" href="/notifications" title="Notifications" aria-label="Notifications">🔔</a>
              <a class="icon-btn theme-toggle-btn" href="?theme={toggled_theme}" title="Toggle Theme" aria-label="Toggle color theme">
                {'🌙' if theme == 'light' else '☀️'}
              </a>
            </div>
          </header>

          <div class="page-header">
            <div>
              <h1>{esc(page.title)}</h1>
              <p>Centralized rehabilitation monitoring for clinical review and decision support.</p>
            </div>
            <div class="date-chip">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</div>
          </div>

          <div class="page-content">
            {page.body}
          </div>
        </main>
      </div>

      <script>{self.js()}</script>
      {page.scripts}
    </body>
    </html>"""
        return html_doc.encode("utf-8")
