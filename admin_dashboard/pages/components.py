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



class ComponentsMixin:
    def css(self) -> str:
        return """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root {
  --bg: #f8fafc;
  --panel: rgba(255, 255, 255, 0.88);
  --panel-2: rgba(241, 245, 249, 0.9);
  --text: #1e293b;
  --muted: #64748b;
  --line: rgba(226, 232, 240, 0.8);
  --primary: #2563EB;
  --primary-2: #06B6D4;
  --success: #22C55E;
  --warning: #F59E0B;
  --danger: #EF4444;
  --shadow: 0 4px 20px -4px rgba(0, 0, 0, 0.06), 0 2px 8px -2px rgba(0, 0, 0, 0.03);
  --shadow-hover: 0 12px 28px -6px rgba(37, 99, 235, 0.12), 0 4px 10px -4px rgba(37, 99, 235, 0.06);
  --glass-border: rgba(226, 232, 240, 0.6);
}
[data-theme="dark"] {
  --bg: #0f172a;
  --panel: rgba(30, 41, 59, 0.88);
  --panel-2: rgba(51, 65, 85, 0.8);
  --text: #f1f5f9;
  --muted: #94a3b8;
  --line: rgba(51, 65, 85, 0.8);
  --primary: #3b82f6;
  --primary-2: #22d3ee;
  --shadow: 0 4px 20px -4px rgba(0, 0, 0, 0.35);
  --shadow-hover: 0 12px 28px -6px rgba(59, 130, 246, 0.2);
  --glass-border: rgba(255, 255, 255, 0.06);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 14.5px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  transition: background-color 0.3s ease, color 0.3s ease;
}
a { color: inherit; text-decoration: none; }

/* Layout Elements */
.glass-panel {
  background: var(--panel);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--glass-border);
}
.sidebar {
  position: fixed; inset: 0 auto 0 0; width: 270px; padding: 28px 18px;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--line);
  z-index: 100;
  box-shadow: 2px 0 20px rgba(0,0,0,0.03);
}
.brand { display: flex; gap: 14px; align-items: center; margin-bottom: 32px; padding: 0 8px; }
.brand-mark {
  width: 44px; height: 44px; border-radius: 10px;
  display: grid; place-items: center;
  color: white; background: linear-gradient(135deg, var(--primary), var(--primary-2));
  font-weight: 800; font-size: 17px;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.22);
}
.brand strong { display: block; font-size: 16px; font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
.brand span, .topbar p, .muted { color: var(--muted); font-size: 13px; font-weight: 500; }

.nav-menu { display: flex; flex-direction: column; gap: 3px; flex-grow: 1; overflow-y: auto; }
.nav-item {
  display: flex; align-items: center; gap: 11px;
  padding: 11px 14px; border-radius: 8px;
  color: var(--muted); font-weight: 600; font-size: 13.5px;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.nav-icon { font-size: 16px; opacity: 0.75; }
.nav-item.active, .nav-item:hover {
  background: var(--panel-2); color: var(--primary);
  transform: translateX(3px);
}
.nav-item.active .nav-icon { opacity: 1; }
.nav-divider { height: 1px; background: var(--line); margin: 14px 0; }
.text-danger:hover { color: var(--danger) !important; background: rgba(239, 68, 68, 0.1) !important; }

.main { margin-left: 270px; padding: 0; min-height: 100vh; display: flex; flex-direction: column; }
.topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 24px;
  padding: 14px 36px; border-bottom: 1px solid var(--line);
  position: sticky; top: 0; z-index: 90;
}
.search-bar {
  display: flex; align-items: center; gap: 10px;
  background: var(--bg); border: 1px solid var(--line);
  padding: 9px 16px; border-radius: 8px;
  width: 100%; max-width: 380px; transition: all 0.2s ease;
}
.search-bar:focus-within { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
.search-input { border: none; background: transparent; width: 100%; outline: none; padding: 0; color: var(--text); font-family: 'Inter', sans-serif; font-size: 14px; }
.search-input:focus { box-shadow: none; }

.topbar-actions { display: flex; align-items: center; gap: 14px; }
.icon-btn {
  display: grid; place-items: center;
  width: 38px; height: 38px; border-radius: 8px;
  background: var(--bg); color: var(--text); border: 1px solid var(--line);
  font-size: 15px; transition: all 0.2s ease;
}
.icon-btn:hover { background: var(--panel-2); transform: translateY(-1px); }

.therapist-profile { display: flex; align-items: center; gap: 12px; margin-left: 12px; padding-left: 16px; border-left: 1px solid var(--line); cursor: pointer; }
.avatar {
  width: 40px; height: 40px; border-radius: 8px;
  background: linear-gradient(135deg, var(--primary-2), var(--primary));
  color: white; display: grid; place-items: center; font-weight: 700; font-size: 14px;
}
.profile-info { display: flex; flex-direction: column; }
.profile-info strong { font-size: 13.5px; font-weight: 600; color: var(--text); }
.profile-info span { font-size: 12px; color: var(--muted); }

.page-header { padding: 28px 36px 12px; display: flex; align-items: center; justify-content: space-between; }
h1 { margin: 0 0 6px; font-size: 26px; font-weight: 800; letter-spacing: -0.025em; }
h2 { margin: 0 0 14px; font-size: 17px; font-weight: 700; letter-spacing: -0.01em; }
.date-chip, .pill {
  padding: 7px 14px; border: 1px solid var(--line);
  background: var(--panel); border-radius: 8px;
  color: var(--primary); font-size: 13px; font-weight: 600;
  box-shadow: 0 1px 4px rgba(0,0,0,0.02);
}

/* Sections */
.main > section { padding: 0 36px 28px; }
.grid { display: grid; gap: 20px; }
.stats { grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.two { grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.8fr); }
.three { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }

.card {
  background: var(--panel);
  border: 1px solid var(--glass-border);
  border-radius: 10px;
  padding: 22px;
  box-shadow: var(--shadow);
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s ease;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.card:hover { transform: translateY(-3px); box-shadow: var(--shadow-hover); }

.stat-label { color: var(--muted); font-size: 12.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; display: flex; align-items: center; gap: 8px; }
.stat-value { margin-top: 10px; font-size: 30px; font-weight: 800; color: var(--text); line-height: 1.1; letter-spacing: -0.02em; }
.stat-sub { margin-top: 8px; color: var(--muted); font-size: 13px; font-weight: 500; line-height: 1.4; }

.toolbar { display: flex; gap: 12px; align-items: center; justify-content: space-between; margin-bottom: 20px; flex-wrap: wrap; }
input:not(.search-input), select, textarea {
  width: 100%; border: 1px solid var(--line);
  background: var(--bg); color: var(--text);
  border-radius: 8px; padding: 10px 14px;
  font: inherit; font-size: 14px;
  transition: all 0.2s ease; outline: none;
}
input:focus:not(.search-input), select:focus, textarea:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); }
textarea { min-height: 100px; resize: vertical; }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
.full { grid-column: 1 / -1; }
label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; color: var(--text); }

button, .button {
  display: inline-flex; align-items: center; justify-content: center;
  border: 0; border-radius: 8px; padding: 10px 22px;
  background: linear-gradient(135deg, var(--primary), var(--primary-2));
  color: white; font-weight: 600; font-size: 13.5px; cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.18);
}
button:hover, .button:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(37, 99, 235, 0.25); }
button:active, .button:active { transform: translateY(0); }
.button.secondary { background: var(--bg); color: var(--text); border: 1px solid var(--line); box-shadow: none; }
.button.secondary:hover { background: var(--panel-2); border-color: var(--primary); box-shadow: 0 3px 10px rgba(0,0,0,0.04); }
.button.danger, button.danger { background: linear-gradient(135deg, var(--danger), #b91c1c); box-shadow: 0 3px 10px rgba(239, 68, 68, 0.18); }

table { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 6px; }
th, td { padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; font-size: 13.5px; }
th { color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; border-bottom-width: 2px; }
tr:last-child td { border-bottom: none; }
tr { transition: background-color 0.15s ease; }
tr:hover td { background: var(--bg); }

.progress { height: 7px; border-radius: 8px; background: var(--bg); overflow: hidden; margin-top: 8px; border: 1px solid var(--line); }
.progress span { display: block; height: 100%; background: linear-gradient(90deg, var(--primary), var(--success)); border-radius: 8px; }
.badge { padding: 5px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; background: rgba(37, 99, 235, 0.1); color: var(--primary); display: inline-block; transition: all 0.2s ease; }
.badge.success { background: rgba(34, 197, 94, 0.1); color: var(--success); }
.badge.warning { background: rgba(245, 158, 11, 0.1); color: var(--warning); }
.badge.danger { background: rgba(239, 68, 68, 0.1); color: var(--danger); }

.alert { border-left: 4px solid var(--primary); padding-left: 18px; border-radius: 8px; background: rgba(37, 99, 235, 0.03); }
.alert.warning { border-left-color: var(--warning); background: rgba(245, 158, 11, 0.03); }
.alert.warning .badge { color: var(--warning); background: rgba(245, 158, 11, 0.1); }
.alert.danger { border-left-color: var(--danger); background: rgba(239, 68, 68, 0.03); }
.alert.danger .badge { color: var(--danger); background: rgba(239, 68, 68, 0.1); }

.chart { width: 100%; border-radius: 8px; border: 1px solid var(--line); background: #ffffff; mix-blend-mode: normal; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }
[data-theme="dark"] .chart { filter: brightness(0.9) contrast(1.1); }
.tabs { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
.pagination { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

@media (max-width: 1024px) {
  .sidebar { width: 230px; }
  .main { margin-left: 230px; }
  .topbar, .page-header, .main > section { padding-left: 20px; padding-right: 20px; }
}
@media (max-width: 768px) {
  .sidebar { position: static; width: 100%; border-right: none; border-bottom: 1px solid var(--line); padding: 18px; }
  .nav-menu { flex-direction: row; flex-wrap: wrap; gap: 6px; }
  .nav-item { padding: 9px 12px; flex: 1; min-width: 120px; justify-content: center; font-size: 13px; }
  .nav-divider { display: none; }
  .main { margin-left: 0; }
  .topbar { flex-direction: column; align-items: stretch; gap: 14px; }
  .search-bar { max-width: none; }
  .therapist-profile { border-left: none; padding-left: 0; margin-left: auto; }
  .stats, .two, .three, .form-grid { grid-template-columns: 1fr; }
  .page-header { flex-direction: column; align-items: flex-start; gap: 14px; }
  h1 { font-size: 22px; }
  .stat-value { font-size: 26px; }
}
"""

    def js(self) -> str:
        return """
function filterTable(inputId, tableId) {
  const q = document.getElementById(inputId)?.value.toLowerCase() || "";
  document.querySelectorAll(`#${tableId} tbody tr`).forEach(row => {
    row.style.display = row.innerText.toLowerCase().includes(q) ? "" : "none";
  });
}
function sortTable(tableId, column) {
  const table = document.getElementById(tableId);
  const body = table.querySelector("tbody");
  const rows = Array.from(body.querySelectorAll("tr"));
  const asc = table.dataset.sort !== String(column);
  rows.sort((a, b) => {
    const av = a.children[column].innerText.trim();
    const bv = b.children[column].innerText.trim();
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!Number.isNaN(an) && !Number.isNaN(bn)) return asc ? an - bn : bn - an;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  table.dataset.sort = asc ? String(column) : "";
  rows.forEach(row => body.appendChild(row));
}
"""

    def chart(self, title: str, series: dict[str, list[float]], labels: list[str], ylabel: str = "") -> str:
        fig, ax = plt.subplots(figsize=(8.5, 3.6), dpi=130)
        fig.patch.set_facecolor("#ffffff")
        ax.set_facecolor("#ffffff")
        colors = ["#0077b6", "#1da365", "#dc8f14", "#cc404a", "#5d5fef"]
        for index, (name, values) in enumerate(series.items()):
            ax.plot(labels, values, marker="o", linewidth=2.4, color=colors[index % len(colors)], label=name)
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color="#1c2735")
        ax.set_ylabel(ylabel, color="#66778a")
        ax.grid(True, color="#dbe7f0", linewidth=.8)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8, colors="#66778a")
        ax.tick_params(axis="y", colors="#66778a")
        for spine in ax.spines.values():
            spine.set_color("#d2e0ec")
        if len(series) > 1:
            ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f'<img class="chart" alt="{esc(title)}" src="data:image/png;base64,{encoded}">'

    def stat_card(self, label: str, value: str, sub: str = "", icon: str = "") -> str:
        icon_html = f'<div class="stat-icon">{icon}</div>' if icon else ''
        return f"""
        <section class="card">
          <div class="stat-header">
            <div class="stat-label">{esc(label)}</div>
            {icon_html}
          </div>
          <div class="stat-value">{esc(value)}</div>
          <div class="stat-sub">{esc(sub)}</div>
        </section>
        """

    def option(self, value: str, label: str, selected: str) -> str:
        return f'<option value="{esc(value)}" {"selected" if value == selected else ""}>{esc(label)}</option>'

    def short_text(self, value: Any, max_words: int = 18) -> str:
        words = str(value or "").split()
        if len(words) <= max_words:
            return " ".join(words) if words else "-"
        return " ".join(words[:max_words]) + "..."

