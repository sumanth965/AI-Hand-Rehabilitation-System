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
          <nav class="nav-menu" aria-label="Main">
            {nav_html}
            <div class="nav-divider" role="separator"></div>
            <a class="nav-item" href="#" aria-label="Settings"><span class="nav-icon" aria-hidden="true">⚙️</span><span class="nav-label">Settings</span></a>
            <a class="nav-item text-danger" href="/logout" aria-label="Logout"><span class="nav-icon" aria-hidden="true">🚪</span><span class="nav-label">Logout</span></a>
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
              <button class="therapist-profile" type="button" aria-haspopup="true" aria-label="Therapist profile menu">
                <div class="avatar" aria-hidden="true">{esc(avatar_initials)}</div>
                <div class="profile-info">
                  <strong>{esc(username_val)}</strong>
                  <span>Admin</span>
                </div>
              </button>
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
    /* =====================================================================
       Design tokens
       ===================================================================== */
    :root {
      --bg-canvas: #f4f7fa;
      --bg-primary: #ffffff;
      --bg-secondary: #f8fafc;
      --bg-elevated: rgba(255, 255, 255, 0.72);
      --border-subtle: #e2e8f0;
      --border-strong: #cbd5e1;

      --text-primary: #0f172a;
      --text-secondary: #475569;
      --text-muted: #94a3b8;

      --accent: #0e7c86;
      --accent-strong: #0a5f68;
      --accent-soft: #e6f4f5;
      --accent-contrast: #ffffff;

      --success: #22c55e;
      --success-soft: rgba(34, 197, 94, 0.1);
      --danger: #ef4444;
      --danger-soft: rgba(239, 68, 68, 0.1);
      --warning: #f59e0b;

      --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
      --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.08);
      --shadow-lg: 0 12px 28px rgba(15, 23, 42, 0.12);

      --radius-sm: 8px;
      --radius-md: 10px;
      --radius-lg: 12px;

      --space-1: 4px;
      --space-2: 8px;
      --space-3: 16px;
      --space-4: 24px;
      --space-5: 32px;
      --space-6: 40px;

      --sidebar-width: 260px;
      --sidebar-width-collapsed: 76px;
      --topbar-height: 68px;

      --font-sans: "Inter", "Roboto", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      --font-mono: "SFMono-Regular", ui-monospace, "Roboto Mono", Menlo, Consolas, monospace;

      color-scheme: light;
    }

    html[data-theme="dark"] {
      --bg-canvas: #0b1220;
      --bg-primary: #111a2b;
      --bg-secondary: #16223a;
      --bg-elevated: rgba(17, 26, 43, 0.72);
      --border-subtle: #22314d;
      --border-strong: #2e3f61;

      --text-primary: #f1f5f9;
      --text-secondary: #b6c2d9;
      --text-muted: #7688a8;

      --accent: #35c6d1;
      --accent-strong: #6fdbe4;
      --accent-soft: rgba(53, 198, 209, 0.14);
      --accent-contrast: #06222a;

      --success: #4ade80;
      --success-soft: rgba(74, 222, 128, 0.14);
      --danger: #f87171;
      --danger-soft: rgba(248, 113, 113, 0.14);

      --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.35);
      --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
      --shadow-lg: 0 16px 32px rgba(0, 0, 0, 0.5);

      color-scheme: dark;
    }

    /* =====================================================================
       Reset & base
       ===================================================================== */
    *, *::before, *::after { box-sizing: border-box; }

    html { -webkit-text-size-adjust: 100%; }

    body {
      margin: 0;
      font-family: var(--font-sans);
      background: var(--bg-canvas);
      color: var(--text-primary);
      -webkit-font-smoothing: antialiased;
      transition: background-color 0.3s ease, color 0.3s ease;
      animation: theme-fade-in 0.35s ease;
    }

    @keyframes theme-fade-in {
      from { opacity: 0.4; }
      to { opacity: 1; }
    }

    h1, h2, h3, h4 { margin: 0; font-weight: 650; letter-spacing: -0.01em; }
    p { margin: 0; color: var(--text-secondary); }

    a { color: inherit; text-decoration: none; }

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
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 1px solid var(--border-subtle);
    }

    /* =====================================================================
       Shell / layout
       ===================================================================== */
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
      gap: var(--space-4);
      border-radius: 0;
      border-right: 1px solid var(--border-subtle);
      border-top: none;
      border-bottom: none;
      border-left: none;
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
    .brand-text strong { font-size: 15px; white-space: nowrap; }
    .brand-text span { font-size: 12px; color: var(--text-muted); white-space: nowrap; }

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
      padding: 10px var(--space-2);
      border-radius: var(--radius-sm);
      color: var(--text-secondary);
      font-size: 14px;
      font-weight: 500;
      min-height: 44px;
      border-left: 3px solid transparent;
      transition: background-color 0.18s ease, color 0.18s ease, transform 0.12s ease, border-color 0.18s ease;
      white-space: nowrap;
    }

    .nav-item:hover {
      background: var(--accent-soft);
      color: var(--accent-strong);
      transform: translateX(2px);
    }

    .nav-item:active { transform: scale(0.98) translateX(2px); }

    .nav-item.active {
      background: var(--accent-soft);
      color: var(--accent-strong);
      border-left-color: var(--accent);
      font-weight: 650;
    }

    .nav-icon {
      width: 24px;
      min-width: 24px;
      height: 24px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      border-radius: 6px;
      background: transparent;
    }

    .nav-item.active .nav-icon,
    .nav-item:hover .nav-icon {
      background: var(--bg-primary);
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

    /* Main / content --------------------------------------------------------- */
    .main {
      min-width: 0;
      contain: layout style;
      padding: 0 var(--space-5) var(--space-6);
    }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 15;
      display: flex;
      align-items: center;
      gap: var(--space-3);
      min-height: var(--topbar-height);
      padding: var(--space-2) var(--space-4);
      margin: 0 calc(var(--space-5) * -1);
      border-radius: 0;
      border-top: none;
      border-left: none;
      border-right: none;
    }

    .hamburger-btn {
      display: none;
    }

    .search-bar {
      flex: 1;
      max-width: 420px;
      display: flex;
      align-items: center;
      gap: var(--space-2);
      background: var(--bg-secondary);
      border: 1px solid var(--border-subtle);
      border-radius: 999px;
      padding: 0 var(--space-3);
      height: 40px;
      transition: box-shadow 0.18s ease, border-color 0.18s ease;
    }

    .search-bar:focus-within {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }

    .search-icon { color: var(--text-muted); font-size: 13px; }

    .search-input {
      flex: 1;
      border: none;
      background: transparent;
      font-size: 14px;
      height: 100%;
    }
    .search-input:focus { outline: none; }
    .search-input::placeholder { color: var(--text-muted); }

    .topbar-actions {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: var(--space-2);
    }

    .privacy-badge {
      font-size: 13px;
      color: var(--success);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;
      background: var(--success-soft);
      padding: 6px 12px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(34, 197, 94, 0.2);
      white-space: nowrap;
    }

    .icon-btn {
      width: 40px;
      height: 40px;
      min-width: 44px;
      min-height: 44px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: var(--radius-sm);
      font-size: 16px;
      color: var(--text-secondary);
      background: var(--bg-secondary);
      border: 1px solid var(--border-subtle);
      transition: background-color 0.18s ease, transform 0.12s ease, box-shadow 0.18s ease;
    }
    .icon-btn:hover { background: var(--accent-soft); color: var(--accent-strong); box-shadow: var(--shadow-sm); }
    .icon-btn:active { transform: scale(0.94); }

    .therapist-profile {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      padding: 6px 10px 6px 6px;
      border-radius: 999px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-subtle);
      min-height: 44px;
      transition: background-color 0.18s ease, box-shadow 0.18s ease;
    }
    .therapist-profile:hover { background: var(--accent-soft); box-shadow: var(--shadow-sm); }

    .avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--accent), var(--accent-strong));
      color: var(--accent-contrast);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: 700;
    }

    .profile-info { display: flex; flex-direction: column; line-height: 1.2; text-align: left; }
    .profile-info strong { font-size: 13px; }
    .profile-info span { font-size: 11px; color: var(--text-muted); }

    /* Page header ------------------------------------------------------------ */
    .page-header {
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      gap: var(--space-3);
      padding: var(--space-5) 0 var(--space-4);
      flex-wrap: wrap;
    }

    .page-header h1 { font-size: 24px; color: var(--text-primary); }
    .page-header p { font-size: 14px; margin-top: 4px; max-width: 520px; }

    .date-chip {
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--text-muted);
      background: var(--bg-secondary);
      border: 1px solid var(--border-subtle);
      padding: 8px 14px;
      border-radius: var(--radius-sm);
      white-space: nowrap;
    }

    .page-content {
      animation: content-enter 0.3s ease;
    }

    @keyframes content-enter {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* =====================================================================
       Shared card / grid primitives available to page mixins
       ===================================================================== */
    .grid {
      display: grid;
      gap: var(--space-4);
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }

    .card {
      background: var(--bg-primary);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
      box-shadow: var(--shadow-sm);
      transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    }

    .card.interactive:hover,
    a.card:hover,
    button.card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-md);
      border-color: var(--border-strong);
    }

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
      background: linear-gradient(90deg, transparent, rgba(148, 163, 184, 0.18), transparent);
      animation: skeleton-sweep 1.4s infinite;
    }
    @keyframes skeleton-sweep {
      100% { transform: translateX(100%); }
    }

    /* =====================================================================
       Tablet (768px - 1024px): icon-only collapsible sidebar
       ===================================================================== */
    @media (max-width: 1024px) {
      .app-shell {
        grid-template-columns: var(--sidebar-width-collapsed) 1fr;
      }

      .sidebar { width: var(--sidebar-width-collapsed); padding: var(--space-3) var(--space-2); }

      .brand-text, .nav-label { display: none; }
      .brand { justify-content: center; }
      .nav-item { justify-content: center; padding: 10px; }
      .nav-item.active { border-left-width: 3px; }

      .main { padding: 0 var(--space-3) var(--space-5); }
      .topbar { margin: 0 calc(var(--space-3) * -1); padding: var(--space-2) var(--space-3); }
      .search-bar { max-width: 260px; }
      .profile-info { display: none; }
    }

    /* =====================================================================
       Mobile (<768px): hidden sidebar + hamburger drawer
       ===================================================================== */
    @media (max-width: 767px) {
      .app-shell { grid-template-columns: 1fr; }

      .sidebar {
        position: fixed;
        top: 0;
        left: 0;
        width: 82vw;
        max-width: 300px;
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

      .sidebar-toggle-input:checked ~ .app-shell .sidebar {
        transform: translateX(0);
      }
      .sidebar-toggle-input:checked ~ .app-shell .sidebar-scrim {
        display: block;
      }

      .main { padding: 0 var(--space-3) var(--space-4); }
      .topbar {
        margin: 0 calc(var(--space-3) * -1);
        padding: var(--space-2) var(--space-3);
        flex-wrap: wrap;
        row-gap: var(--space-2);
      }

      .search-bar { order: 3; max-width: none; width: 100%; }
      .topbar-actions { gap: 6px; }
      .privacy-badge-label { display: none; }
      .profile-info { display: none; }

      .page-header { flex-direction: column; align-items: flex-start; padding-top: var(--space-4); }
      .page-header h1 { font-size: 20px; }
      .date-chip { align-self: flex-start; }

      .grid { grid-template-columns: 1fr; }

      .icon-btn, .therapist-profile, .nav-item { min-height: 44px; min-width: 44px; }
    }

    /* Respect reduced motion preferences */
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
      }
    }
    """