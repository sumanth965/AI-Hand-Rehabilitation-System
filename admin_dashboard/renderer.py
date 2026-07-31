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
      <style>{self.css()}</style>
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


    def css(self) -> str:
        return """
    /* =================================================================
       1. DESIGN TOKENS
       ================================================================= */
    :root {
      --bg-canvas: #F5F7FA;
      --bg-primary: #FFFFFF;
      --bg-secondary: #EFF2F7;
      --bg-elevated: rgba(255, 255, 255, 0.92);
      --border-subtle: #E5E7EB;
      --border-strong: #D1D5DB;

      --text-primary: #1F2937;
      --text-secondary: #4B5563;
      --text-muted: #6B7280;

      --accent: #2563EB;
      --accent-strong: #4F46E5;
      --accent-soft: rgba(37, 99, 235, 0.07);
      --accent-contrast: #ffffff;

      --success: #16A34A;
      --success-soft: rgba(22, 163, 74, 0.07);
      --danger: #DC2626;
      --danger-soft: rgba(220, 38, 38, 0.07);
      --warning: #F59E0B;
      --warning-soft: rgba(245, 158, 11, 0.07);

      --shadow-sm: 0 4px 12px rgba(15, 23, 42, 0.05);
      --shadow-md: 0 12px 30px rgba(15, 23, 42, 0.08);
      --shadow-lg: 0 20px 50px rgba(15, 23, 42, 0.12);

      --radius-sm: 12px;
      --radius-md: 16px;
      --radius-lg: 20px;

      --space-1: 4px;
      --space-2: 8px;
      --space-3: 16px;
      --space-4: 24px;
      --space-5: 32px;
      --space-6: 40px;

      --sidebar-width: 260px;
      --sidebar-width-collapsed: 76px;
      --topbar-height: 68px;

      --font-sans: "Segoe UI", Arial, Helvetica, -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: "SFMono-Regular", ui-monospace, Menlo, Consolas, monospace;

      color-scheme: light;
    }

    html[data-theme="dark"] {
      --bg-canvas: #0C0E14;
      --bg-primary: #14161E;
      --bg-secondary: #1C1E28;
      --bg-elevated: rgba(20, 22, 30, 0.92);
      --border-subtle: #282A36;
      --border-strong: #3A3D4C;

      --text-primary: #F3F4F6;
      --text-secondary: #A0A5B5;
      --text-muted: #6B7280;

      --accent: #5B8DEF;
      --accent-strong: #818CF8;
      --accent-soft: rgba(91, 141, 239, 0.12);
      --accent-contrast: #0a1628;

      --success: #4ade80;
      --success-soft: rgba(74, 222, 128, 0.10);
      --danger: #f87171;
      --danger-soft: rgba(248, 113, 113, 0.10);
      --warning-soft: rgba(245, 158, 11, 0.10);

      --shadow-sm: 0 4px 12px rgba(0, 0, 0, 0.35);
      --shadow-md: 0 12px 30px rgba(0, 0, 0, 0.40);
      --shadow-lg: 0 20px 50px rgba(0, 0, 0, 0.50);

      color-scheme: dark;
    }

    /* =================================================================
       2. RESET & BASE
       ================================================================= */
    *, *::before, *::after { box-sizing: border-box; }
    html { -webkit-text-size-adjust: 100%; scroll-behavior: smooth; }

    body {
      margin: 0;
      font-family: var(--font-sans);
      font-size: 14.5px;
      line-height: 1.6;
      background: var(--bg-canvas);
      color: var(--text-primary);
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      transition: background-color 0.3s ease, color 0.3s ease;
      animation: fadeIn 0.35s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    h1, h2, h3, h4 { margin: 0; font-weight: 700; letter-spacing: -0.025em; color: var(--text-primary); }
    h1 { font-size: 28px; font-weight: 800; }
    h2 { font-size: 18px; margin: 0 0 16px; }
    h3 { font-size: 15px; }
    p { margin: 0; color: var(--text-secondary); line-height: 1.65; }

    a { color: inherit; text-decoration: none; transition: color 0.2s ease; }

    button {
      font-family: inherit;
      border: none;
      background: none;
      cursor: pointer;
      color: inherit;
    }

    input {
      font-family: inherit;
      color: var(--text-primary);
    }

    :focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
      border-radius: var(--radius-sm);
    }

    .glass-panel {
      background: var(--bg-elevated);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-subtle);
    }

    .muted { color: var(--text-muted); }

    /* =================================================================
       3. SHELL / LAYOUT
       ================================================================= */
    .app-shell {
      display: grid;
      grid-template-columns: var(--sidebar-width) 1fr;
      min-height: 100vh;
    }

    .sidebar-toggle-input { display: none; }

    /* Sidebar --------------------------------------------------------------- */
    .sidebar {
      position: sticky;
      top: 0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      padding: var(--space-4) var(--space-3);
      gap: var(--space-3);
      border-radius: 0;
      background: #17181c;
      color: #ffffff;
      border: none;
      contain: layout style;
      z-index: 30;
      transition: width 0.25s ease, padding 0.25s ease;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      padding: var(--space-2);
    }

    .brand-mark {
      width: 40px;
      height: 40px;
      min-width: 40px;
      border-radius: var(--radius-md);
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: var(--accent-contrast);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 14px;
      box-shadow: var(--shadow-sm);
    }

    .brand-text { display: flex; flex-direction: column; line-height: 1.25; overflow: hidden; }
    .brand-text strong { font-size: 15px; white-space: nowrap; color: #ffffff; }
    .brand-text span { font-size: 12px; color: rgba(255, 255, 255, 0.5); white-space: nowrap; }

    .sidebar-close-btn {
      display: none;
      margin-left: auto;
      width: 32px;
      height: 32px;
      align-items: center;
      justify-content: center;
      border-radius: var(--radius-sm);
      color: var(--text-muted);
      cursor: pointer;
    }
    .sidebar-close-btn:hover { background: var(--bg-secondary); color: var(--text-primary); }

    .nav-menu {
      display: flex;
      flex-direction: column;
      gap: var(--space-1);
      overflow-y: auto;
      scrollbar-width: none; /* Firefox */
      -ms-overflow-style: none;  /* IE and Edge */
    }
    
    .nav-menu::-webkit-scrollbar {
      display: none; /* Chrome, Safari and Opera */
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      padding: 12px 16px;
      border-radius: 20px;
      color: rgba(255, 255, 255, 0.7);
      background: rgba(255, 255, 255, 0.05);
      font-size: 14px;
      font-weight: 500;
      min-height: 44px;
      border: none;
      margin-bottom: 8px;
      transition: background-color 0.18s ease, color 0.18s ease, transform 0.12s ease;
      white-space: nowrap;
    }

    .nav-item:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #ffffff;
      transform: translateY(-1px);
    }

    .nav-item:active { transform: scale(0.98); }

    .nav-item.active {
      background: #1cd0a0;
      color: #0b1220;
      font-weight: 650;
    }

    .nav-item.utility-link {
      background: transparent;
      border-radius: 0;
      margin-bottom: 0;
      padding: 10px 16px;
      color: rgba(255, 255, 255, 0.6);
    }
    
    .nav-item.utility-link:hover {
      color: #ffffff;
      transform: none;
    }

    .nav-icon {
      width: 24px;
      min-width: 24px;
      height: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      border-radius: 6px;
      background: transparent;
    }

    .nav-item.active .nav-icon,
    .nav-item:hover .nav-icon {
      background: transparent;
    }

    .nav-divider {
      height: 1px;
      background: var(--border-subtle);
      margin: var(--space-2) var(--space-1);
    }

    .text-danger { color: var(--danger) !important; }
    .text-danger:hover { background: var(--danger-soft) !important; color: var(--danger) !important; }

    .sidebar-scrim {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.45);
      z-index: 20;
    }

    /* =================================================================
       4. MAIN CONTENT AREA
       ================================================================= */
    .main {
      min-width: 0;
      padding: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      background: var(--bg-canvas);
    }

    /* =================================================================
       5. TOPBAR / HEADER
       ================================================================= */
    .topbar {
      position: sticky;
      top: 0;
      z-index: 15;
      display: flex;
      align-items: center;
      gap: 20px;
      min-height: var(--topbar-height);
      padding: 14px 36px;
      background: var(--bg-primary);
      border-bottom: 1px solid var(--border-subtle);
      box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
      backdrop-filter: none;
      -webkit-backdrop-filter: none;
    }

    .hamburger-btn { display: none; }

    .search-bar {
      flex: 1;
      max-width: 440px;
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--bg-canvas);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 0 16px;
      height: 44px;
      transition: border-color 0.3s ease, box-shadow 0.3s ease;
    }
    .search-bar:focus-within {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }

    .search-icon { color: var(--text-muted); font-size: 14px; }

    .search-input {
      flex: 1;
      border: none;
      background: transparent;
      font-size: 14px;
      font-family: var(--font-sans);
      height: 100%;
      color: var(--text-primary);
    }
    .search-input:focus { outline: none; }
    .search-input::placeholder { color: var(--text-muted); }

    .topbar-actions {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .privacy-badge {
      font-size: 13px;
      color: var(--success);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
      background: var(--success-soft);
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(22, 163, 74, 0.15);
      white-space: nowrap;
    }

    .icon-btn {
      width: 42px;
      height: 42px;
      min-width: 42px;
      min-height: 42px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: var(--radius-sm);
      font-size: 16px;
      color: var(--text-secondary);
      background: var(--bg-canvas);
      border: 1px solid var(--border-subtle);
      transition: all 0.3s ease;
      cursor: pointer;
    }
    .icon-btn:hover {
      background: var(--accent-soft);
      color: var(--accent);
      border-color: var(--accent);
      transform: translateY(-2px);
      box-shadow: var(--shadow-sm);
    }
    .icon-btn:active { transform: scale(0.95); }

    /* =================================================================
       6. SIDEBAR PROFILE (in sidebar)
       ================================================================= */
    .therapist-profile {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      padding: 6px 10px 6px 6px;
      border-radius: 999px;
      background: transparent;
      border: none;
      min-height: 44px;
    }
    .therapist-profile:hover { background: transparent; }

    .sidebar-profile {
      padding: 0 var(--space-2);
      margin-bottom: var(--space-4);
      min-height: auto;
    }
    .sidebar-profile .profile-info strong { color: #ffffff; }
    .sidebar-profile .profile-info span { color: rgba(255, 255, 255, 0.5); }

    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      font-weight: 700;
      box-shadow: 0 3px 10px rgba(37, 99, 235, 0.22);
    }

    .profile-info { display: flex; flex-direction: column; line-height: 1.2; text-align: left; }
    .profile-info strong { font-size: 13.5px; font-weight: 600; }
    .profile-info span { font-size: 11px; color: var(--text-muted); }

    /* =================================================================
       7. PAGE HEADER
       ================================================================= */
    .page-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 32px 36px 20px;
      flex-wrap: wrap;
    }
    .page-header h1 {
      font-size: 28px;
      font-weight: 800;
      letter-spacing: -0.03em;
      margin: 0 0 4px;
    }
    .page-header p {
      font-size: 14.5px;
      margin-top: 4px;
      max-width: 560px;
      color: var(--text-muted);
    }

    .date-chip {
      font-family: var(--font-mono);
      font-size: 12.5px;
      color: var(--accent);
      font-weight: 600;
      background: var(--accent-soft);
      border: 1px solid rgba(37, 99, 235, 0.12);
      padding: 9px 18px;
      border-radius: var(--radius-sm);
      white-space: nowrap;
    }
    .pill {
      padding: 8px 16px;
      border: 1px solid var(--border-subtle);
      background: var(--bg-primary);
      border-radius: var(--radius-sm);
      color: var(--accent);
      font-size: 13px;
      font-weight: 600;
    }

    .page-content {
      padding: 0 36px 40px;
      animation: contentSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    @keyframes contentSlideIn {
      from { opacity: 0; transform: translateY(10px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    /* =================================================================
       8. GRID LAYOUTS
       ================================================================= */
    .main > section { padding: 0 36px 32px; }

    .grid { display: grid; gap: 28px; }
    .stats { grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }
    .two   { grid-template-columns: minmax(0, 1.25fr) minmax(340px, 0.75fr); }
    .three { grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); }

    /* =================================================================
       9. CARDS — Premium glass-like panels
       ================================================================= */
    .card {
      background: var(--bg-primary);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 28px;
      box-shadow: var(--shadow-sm);
      transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                  box-shadow 0.3s ease,
                  border-color 0.3s ease;
    }
    .card:hover {
      transform: translateY(-6px);
      box-shadow: var(--shadow-md);
      border-color: rgba(37, 99, 235, 0.18);
    }
    .card.interactive:hover,
    a.card:hover,
    button.card:hover {
      transform: translateY(-6px);
      box-shadow: var(--shadow-md);
      border-color: rgba(37, 99, 235, 0.22);
    }

    /* =================================================================
       10. KPI / STAT CARDS
       ================================================================= */
    .grid.stats .card {
      min-height: 190px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      padding: 32px;
      border-left: 4px solid var(--accent);
      background: linear-gradient(135deg, var(--bg-primary) 80%, var(--accent-soft) 100%);
    }
    .grid.stats .card:nth-child(2) { border-left-color: var(--success); background: linear-gradient(135deg, var(--bg-primary) 80%, var(--success-soft) 100%); }
    .grid.stats .card:nth-child(3) { border-left-color: #4F46E5; background: linear-gradient(135deg, var(--bg-primary) 80%, rgba(79, 70, 229, 0.06) 100%); }
    .grid.stats .card:nth-child(4) { border-left-color: var(--warning); background: linear-gradient(135deg, var(--bg-primary) 80%, var(--warning-soft) 100%); }
    .grid.stats .card:nth-child(5) { border-left-color: #06B6D4; background: linear-gradient(135deg, var(--bg-primary) 80%, rgba(6, 182, 212, 0.06) 100%); }
    .grid.stats .card:nth-child(6) { border-left-color: #8B5CF6; background: linear-gradient(135deg, var(--bg-primary) 80%, rgba(139, 92, 246, 0.06) 100%); }
    .grid.stats .card:nth-child(7) { border-left-color: var(--danger); background: linear-gradient(135deg, var(--bg-primary) 80%, var(--danger-soft) 100%); }
    .grid.stats .card:nth-child(8) { border-left-color: #F97316; background: linear-gradient(135deg, var(--bg-primary) 80%, rgba(249, 115, 22, 0.06) 100%); }

    .stat-label {
      color: var(--text-muted);
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .stat-value {
      margin-top: 14px;
      font-size: 44px;
      font-weight: 800;
      color: var(--text-primary);
      line-height: 1;
      letter-spacing: -0.03em;
    }
    .stat-sub {
      margin-top: 10px;
      color: var(--text-muted);
      font-size: 13.5px;
      font-weight: 500;
      line-height: 1.5;
    }

    /* =================================================================
       11. TOOLBAR
       ================================================================= */
    .toolbar {
      display: flex;
      gap: 14px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }

    /* =================================================================
       12. FORM ELEMENTS
       ================================================================= */
    input:not(.search-input), select, textarea {
      width: 100%;
      border: 1px solid var(--border-subtle);
      background: var(--bg-canvas);
      color: var(--text-primary);
      border-radius: var(--radius-sm);
      padding: 11px 16px;
      font-family: var(--font-sans);
      font-size: 14px;
      transition: border-color 0.3s ease, box-shadow 0.3s ease;
      outline: none;
    }
    input:focus:not(.search-input), select:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
    textarea { min-height: 100px; resize: vertical; }
    .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; }
    .full { grid-column: 1 / -1; }
    label { display: flex; flex-direction: column; gap: 7px; font-size: 13px; font-weight: 600; color: var(--text-primary); }

    /* =================================================================
       13. BUTTONS
       ================================================================= */
    button, .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 0;
      border-radius: var(--radius-sm);
      padding: 11px 24px;
      min-height: 42px;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: #ffffff;
      font-family: var(--font-sans);
      font-weight: 600;
      font-size: 13.5px;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 3px 10px rgba(37, 99, 235, 0.20);
      text-decoration: none;
    }
    button:hover, .button:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 18px rgba(37, 99, 235, 0.28);
      filter: brightness(1.05);
    }
    button:active, .button:active {
      transform: translateY(0);
      box-shadow: 0 1px 4px rgba(37, 99, 235, 0.12);
    }
    .button.secondary {
      background: var(--bg-primary);
      color: var(--text-primary);
      border: 1px solid var(--border-subtle);
      box-shadow: var(--shadow-sm);
    }
    .button.secondary:hover {
      background: var(--accent-soft);
      border-color: var(--accent);
      color: var(--accent);
      box-shadow: var(--shadow-md);
    }
    .button.danger, button.danger {
      background: linear-gradient(135deg, #DC2626, #991b1b);
      box-shadow: 0 3px 10px rgba(220, 38, 38, 0.20);
    }
    .button.danger:hover, button.danger:hover {
      box-shadow: 0 6px 18px rgba(220, 38, 38, 0.28);
    }

    /* =================================================================
       14. TABLES
       ================================================================= */
    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      margin-top: 8px;
    }
    th, td {
      padding: 14px 18px;
      border-bottom: 1px solid var(--border-subtle);
      text-align: left;
      vertical-align: middle;
      font-size: 13.5px;
    }
    th {
      color: var(--text-muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      border-bottom-width: 2px;
      border-bottom-color: var(--border-strong);
      background: var(--bg-secondary);
      position: sticky;
      top: var(--topbar-height);
      z-index: 5;
    }
    tr:last-child td { border-bottom: none; }
    tr { transition: background-color 0.2s ease; }
    tr:hover td { background: var(--accent-soft); }
    td { color: var(--text-secondary); }

    /* =================================================================
       15. PROGRESS BARS
       ================================================================= */
    .progress {
      height: 8px;
      border-radius: 10px;
      background: var(--bg-secondary);
      overflow: hidden;
      margin-top: 10px;
      border: 1px solid var(--border-subtle);
    }
    .progress span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--success));
      border-radius: 10px;
      transition: width 0.6s ease;
    }

    /* =================================================================
       16. BADGES
       ================================================================= */
    .badge {
      padding: 5px 14px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 600;
      background: var(--accent-soft);
      color: var(--accent);
      display: inline-block;
      transition: all 0.3s ease;
    }
    .badge.success { background: var(--success-soft); color: var(--success); }
    .badge.warning { background: var(--warning-soft); color: #D97706; }
    .badge.danger  { background: var(--danger-soft);  color: var(--danger); }

    /* =================================================================
       17. ALERTS
       ================================================================= */
    .alert {
      border-left: 4px solid var(--accent);
      padding: 18px 24px;
      border-radius: var(--radius-md);
      background: var(--accent-soft);
      margin-bottom: 14px;
    }
    .alert.warning { border-left-color: var(--warning); background: var(--warning-soft); }
    .alert.warning .badge { color: #D97706; background: rgba(245, 158, 11, 0.14); }
    .alert.danger  { border-left-color: var(--danger);  background: var(--danger-soft); }
    .alert.danger .badge  { color: var(--danger); background: rgba(220, 38, 38, 0.14); }

    /* =================================================================
       18. CHARTS
       ================================================================= */
    .chart {
      width: 100%;
      border-radius: var(--radius-md);
      border: 1px solid var(--border-subtle);
      background: var(--bg-primary);
      box-shadow: var(--shadow-sm);
    }
    html[data-theme="dark"] .chart { filter: brightness(0.88) contrast(1.12); }

    /* =================================================================
       19. TABS & PAGINATION
       ================================================================= */
    .tabs { display: flex; gap: 10px; margin-bottom: 24px; flex-wrap: wrap; }
    .pagination { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }

    /* =================================================================
       20. SKELETONS
       ================================================================= */
    .skeleton {
      position: relative;
      overflow: hidden;
      background: var(--bg-secondary);
      border-radius: var(--radius-sm);
    }
    .skeleton::after {
      content: "";
      position: absolute;
      inset: 0;
      transform: translateX(-100%);
      background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.12), transparent);
      animation: skeletonSweep 1.4s infinite;
    }
    @keyframes skeletonSweep { 100% { transform: translateX(100%); } }

    /* =================================================================
       21. RESPONSIVE — Tablet (768–1024px)
       ================================================================= */
    @media (max-width: 1024px) {
      .app-shell { grid-template-columns: var(--sidebar-width-collapsed) 1fr; }

      .sidebar { width: var(--sidebar-width-collapsed); padding: var(--space-3) var(--space-2); }
      .brand-text, .nav-label { display: none; }
      .brand { justify-content: center; }
      .nav-item { justify-content: center; padding: 10px; }
      .nav-item.active { border-left-width: 3px; }

      .main { padding: 0; }
      .topbar { padding: 12px 20px; }
      .page-header, .page-content, .main > section { padding-left: 24px; padding-right: 24px; }
      .search-bar { max-width: 280px; }
      .profile-info { display: none; }
      .sidebar-profile { display: none; }
      .stats, .two, .three, .form-grid { grid-template-columns: 1fr 1fr; }
    }

    /* =================================================================
       22. RESPONSIVE — Mobile (<768px)
       ================================================================= */
    @media (max-width: 767px) {
      .app-shell { grid-template-columns: 1fr; }

      .sidebar {
        position: fixed; top: 0; left: 0;
        width: 82vw; max-width: 300px;
        padding: var(--space-4) var(--space-3);
        transform: translateX(-100%);
        box-shadow: var(--shadow-lg);
        transition: transform 0.28s ease;
      }
      .brand-text, .nav-label { display: flex; }
      .brand { justify-content: flex-start; }
      .nav-item { justify-content: flex-start; }
      .sidebar-close-btn { display: flex; }
      .hamburger-btn { display: flex; }
      .sidebar-profile { display: flex; }

      .sidebar-toggle-input:checked ~ .app-shell .sidebar { transform: translateX(0); }
      .sidebar-toggle-input:checked ~ .app-shell .sidebar-scrim { display: block; }

      .main { padding: 0; }
      .topbar { padding: 10px 16px; flex-wrap: wrap; row-gap: var(--space-2); }
      .page-header, .page-content, .main > section { padding-left: 16px; padding-right: 16px; }

      .search-bar { order: 3; max-width: none; width: 100%; }
      .topbar-actions { gap: 6px; }
      .privacy-badge-label { display: none; }
      .profile-info { display: none; }

      .page-header { flex-direction: column; align-items: flex-start; padding-top: 24px; }
      .page-header h1 { font-size: 22px; }
      .date-chip { align-self: flex-start; }

      .stats, .two, .three, .grid, .form-grid { grid-template-columns: 1fr; }
      .stat-value { font-size: 32px; }
      .grid.stats .card { min-height: 160px; padding: 24px; }
      .icon-btn, .therapist-profile, .nav-item { min-height: 44px; min-width: 44px; }
      h1 { font-size: 22px; }
    }

    /* =================================================================
       23. ACCESSIBILITY — Reduced motion
       ================================================================= */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
      }
    }
    """