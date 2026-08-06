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
        toggled_theme = "light" if theme != "light" else "dark"
        username_val = params.get("_username", "Therapist")
        avatar_initials = username_val[:2].capitalize()

        theme_icon = (
            '''<!-- Dark mode icons created by Sofyan Rofiq - Flaticon -->
               <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'''
            if theme == 'light' else
            '''<!-- Light mode icons created by Any Icon - Flaticon -->
               <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>'''
        )
        
        notification_href = "javascript:history.back()" if page.active == "notifications" else "/notifications"

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
            <div class="search-bar">
              <span class="search-icon" aria-hidden="true">
                <!-- Search icons created by Magnific - Flaticon -->
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              </span>
              <input type="text" placeholder="Search patients, sessions..." class="search-input" aria-label="Search patients and sessions">
            </div>
            <div class="topbar-actions">
              <span class="privacy-badge">
                <!-- Shield icons created by Maniprasanth - Flaticon -->
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                <span class="privacy-badge-label">Privacy Mode: Active</span>
              </span>
              <a class="icon-btn" href="{notification_href}" title="Notifications" aria-label="Notifications">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
              </a>
              <a class="icon-btn theme-toggle-btn" href="?theme={toggled_theme}" title="Toggle Theme" aria-label="Toggle color theme">
                {
                  '''
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                  '''
                  if theme == 'light' else
                  '''
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                  '''
                }
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

