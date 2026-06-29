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


DB_PATH = "rehab_data.db"
REPORT_DIR = "reports"
HOST = "127.0.0.1"
PORT = 8080


LEVEL_NAMES = {
    1: "Flexibility - Bubble Reach",
    2: "Strength - Palm Catch",
    3: "Fine Motor - Pinch Transfer",
    4: "Coordination - Path Tracing",
    5: "Grip Release - Open/Close Cycle",
    6: "Cognitive Motor - Sequence Tap",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def short_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(value.replace("Z", "")).strftime("%d %b %Y")
    except ValueError:
        return value[:16]


def minutes(seconds: Any) -> float:
    return number(seconds) / 60.0


def format_duration(seconds: Any) -> str:
    total = int(number(seconds))
    return f"{total // 60:02d}:{total % 60:02d}"


def exercise_for_level(level: Any) -> str:
    return LEVEL_NAMES.get(int(number(level)), "Therapeutic Exercise")


def trend(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return values[-1] - values[0]


def recovery_prediction(sessions: list[sqlite3.Row]) -> float:
    values = [number(row["avg_hand_angle"]) for row in sessions if row["avg_hand_angle"] is not None]
    if len(values) < 3:
        return -1.0
    xs = list(range(len(values)))
    x_mean = sum(xs) / len(xs)
    y_mean = sum(values) / len(values)
    denom = sum((x - x_mean) ** 2 for x in xs) or 1.0
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denom
    predicted = y_mean + slope * (len(values) + 3)
    current = max(y_mean, 1.0)
    return max(0.0, min(100.0, (predicted / current) * 100.0))


def tremor_rating_for_sessions(sessions: list[sqlite3.Row]) -> str:
    if len(sessions) < 3:
        return "Not recorded"
    rom_values = [number(row["avg_hand_angle"]) for row in sessions[-6:]]
    mean = sum(rom_values) / len(rom_values)
    variance = sum((value - mean) ** 2 for value in rom_values) / len(rom_values)
    stdev = math.sqrt(variance)
    if stdev < 5:
        return "Low"
    if stdev < 12:
        return "Moderate"
    return "High"


@dataclass
class Page:
    title: str
    body: str
    active: str = "home"
    scripts: str = ""


class DashboardRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_patient_profiles (
                    patient_name TEXT PRIMARY KEY,
                    gender TEXT DEFAULT '',
                    injury_type TEXT DEFAULT '',
                    rehab_stage TEXT DEFAULT '',
                    assigned_exercises TEXT DEFAULT '',
                    therapist_notes TEXT DEFAULT '',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_name TEXT NOT NULL,
                    session_id INTEGER,
                    note_type TEXT DEFAULT 'Observation',
                    note TEXT NOT NULL,
                    recommendation TEXT DEFAULT '',
                    next_plan TEXT DEFAULT '',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Ensure patients table exists and has id_number in case dashboard is run before the game
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    name TEXT PRIMARY KEY,
                    age INTEGER,
                    age_group TEXT,
                    cal_fist_val REAL DEFAULT 0.12,
                    cal_max_ext REAL DEFAULT 170.0,
                    cal_min_ang REAL DEFAULT 15.0,
                    cal_max_ang REAL DEFAULT 90.0,
                    cal_active INTEGER DEFAULT 0,
                    id_number TEXT UNIQUE
                )
            """)
            try:
                conn.execute(f"SELECT id_number FROM patients LIMIT 1")
            except sqlite3.OperationalError:
                try:
                    conn.execute(f"ALTER TABLE patients ADD COLUMN id_number TEXT")
                    conn.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_id_number ON patients(id_number)")
                except Exception:
                    pass
            conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, tuple(params))
            conn.commit()

    def scalar(self, sql: str, params: Iterable[Any] = (), default: Any = 0) -> Any:
        rows = self.query(sql, params)
        if not rows:
            return default
        value = rows[0][0]
        return default if value is None else value

    def patients(self) -> list[sqlite3.Row]:
        rows = self.query(
            """
            SELECT
                p.name,
                p.age,
                p.age_group,
                COALESCE(p.id_number, '') AS id_number,
                COALESCE(d.gender, '') AS gender,
                COALESCE(d.injury_type, '') AS injury_type,
                COALESCE(d.rehab_stage, '') AS rehab_stage,
                COALESCE(d.assigned_exercises, '') AS assigned_exercises,
                COALESCE(d.therapist_notes, '') AS therapist_notes,
                COUNT(s.id) AS sessions_count,
                COALESCE(AVG(s.avg_accuracy), 0) AS avg_accuracy,
                COALESCE(AVG(s.avg_hand_angle), 0) AS avg_rom,
                MAX(s.timestamp) AS last_session
            FROM patients p
            LEFT JOIN dashboard_patient_profiles d ON d.patient_name = p.name
            LEFT JOIN sessions s ON s.patient_id = p.name
            GROUP BY p.name
            UNION
            SELECT
                s.patient_id AS name,
                NULL AS age,
                '' AS age_group,
                '' AS id_number,
                COALESCE(d.gender, '') AS gender,
                COALESCE(d.injury_type, '') AS injury_type,
                COALESCE(d.rehab_stage, '') AS rehab_stage,
                COALESCE(d.assigned_exercises, '') AS assigned_exercises,
                COALESCE(d.therapist_notes, '') AS therapist_notes,
                COUNT(s.id) AS sessions_count,
                COALESCE(AVG(s.avg_accuracy), 0) AS avg_accuracy,
                COALESCE(AVG(s.avg_hand_angle), 0) AS avg_rom,
                MAX(s.timestamp) AS last_session
            FROM sessions s
            LEFT JOIN patients p ON p.name = s.patient_id
            LEFT JOIN dashboard_patient_profiles d ON d.patient_name = s.patient_id
            WHERE p.name IS NULL
            GROUP BY s.patient_id
            """
        )
        return sorted(rows, key=lambda row: str(row["name"] or "").lower())

    def patient(self, name: str) -> sqlite3.Row | None:
        rows = [row for row in self.patients() if row["name"] == name]
        return rows[0] if rows else None

    def save_patient(self, form: dict[str, str]) -> None:
        name = form.get("name", "").strip()
        if not name:
            return
        age = form.get("age", "").strip()
        age_value = int(age) if age.isdigit() else None
        age_group = form.get("age_group", "").strip()
        id_number = form.get("id_number", "").strip() or None
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO patients (name, age, age_group, id_number)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET age = excluded.age, age_group = excluded.age_group, id_number = excluded.id_number
                """,
                (name, age_value, age_group, id_number),
            )
            conn.execute(
                """
                INSERT INTO dashboard_patient_profiles
                    (patient_name, gender, injury_type, rehab_stage, assigned_exercises,
                     therapist_notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(patient_name) DO UPDATE SET
                    gender = excluded.gender,
                    injury_type = excluded.injury_type,
                    rehab_stage = excluded.rehab_stage,
                    assigned_exercises = excluded.assigned_exercises,
                    therapist_notes = excluded.therapist_notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    name,
                    form.get("gender", "").strip(),
                    form.get("injury_type", "").strip(),
                    form.get("rehab_stage", "").strip(),
                    form.get("assigned_exercises", "").strip(),
                    form.get("therapist_notes", "").strip(),
                ),
            )
            conn.commit()

    def delete_patient(self, name: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM patients WHERE name = ?", (name,))
            conn.execute("DELETE FROM dashboard_patient_profiles WHERE patient_name = ?", (name,))
            conn.execute("DELETE FROM dashboard_notes WHERE patient_name = ?", (name,))
            conn.commit()

    def sessions(self, patient: str = "", limit: int | None = None) -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE patient_id = ?"
            params.append(patient)
        sql = f"SELECT * FROM sessions {where} ORDER BY datetime(timestamp) DESC, id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return self.query(sql, params)

    def sessions_chrono(self, patient: str = "") -> list[sqlite3.Row]:
        rows = self.sessions(patient)
        return list(reversed(rows))

    def notes(self, patient: str = "") -> list[sqlite3.Row]:
        params: list[Any] = []
        where = ""
        if patient:
            where = "WHERE n.patient_name = ?"
            params.append(patient)
        return self.query(
            f"""
            SELECT n.*, s.timestamp, s.level
            FROM dashboard_notes n
            LEFT JOIN sessions s ON s.id = n.session_id
            {where}
            ORDER BY datetime(n.created_at) DESC, n.id DESC
            """,
            params,
        )

    def save_note(self, form: dict[str, str]) -> None:
        patient = form.get("patient_name", "").strip()
        note = form.get("note", "").strip()
        if not patient or not note:
            return
        session_id = form.get("session_id", "").strip()
        self.execute(
            """
            INSERT INTO dashboard_notes
                (patient_name, session_id, note_type, note, recommendation, next_plan)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                patient,
                int(session_id) if session_id.isdigit() else None,
                form.get("note_type", "Observation").strip(),
                note,
                form.get("recommendation", "").strip(),
                form.get("next_plan", "").strip(),
            ),
        )

    def dashboard_stats(self) -> dict[str, Any]:
        patients = self.patients()
        sessions = self.sessions()
        total_seconds = sum(number(row["duration"]) for row in sessions)
        patient_predictions = [
            recovery_prediction(self.sessions_chrono(row["name"]))
            for row in patients
        ]
        predictions = [p for p in patient_predictions if p >= 0]
        seven_days_ago = datetime.now() - timedelta(days=7)
        active = 0
        for row in sessions:
            try:
                if datetime.fromisoformat(str(row["timestamp"])) >= seven_days_ago:
                    active += 1
            except ValueError:
                pass
        return {
            "patients": len(patients),
            "active_sessions": active,
            "completed_sessions": len(sessions),
            "avg_recovery": sum(predictions) / len(predictions) if predictions else 0,
            "overall_accuracy": sum(number(r["avg_accuracy"]) for r in sessions) / len(sessions) if sessions else 0,
            "avg_rom": sum(number(r["avg_hand_angle"]) for r in sessions) / len(sessions) if sessions else 0,
            "therapy_hours": total_seconds / 3600.0,
        }


class DashboardRenderer:
    def __init__(self, repo: DashboardRepository):
        self.repo = repo

    def layout(self, page: Page, params: dict[str, str] | None = None) -> bytes:
        params = params or {}
        theme = params.get("theme", "light")
        nav = [
            ("home", "/", "Dashboard"),
            ("patients", "/patients", "Patients"),
            ("sessions", "/sessions", "Sessions"),
            ("analytics", "/analytics", "Analytics"),
            ("reports", "/reports", "Reports"),
            ("performance", "/performance", "Performance"),
            ("notes", "/notes", "Notes"),
            ("notifications", "/notifications", "Alerts"),
        ]
        nav_html = "".join(
            f'<a class="nav-item {"active" if key == page.active else ""}" href="{href}">{label}</a>'
            for key, href, label in nav
        )
        toggled_theme = "dark" if theme != "dark" else "light"
        html_doc = f"""<!doctype html>
<html lang="en" data-theme="{esc(theme)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(page.title)} - Therapist Dashboard</title>
  <style>{self.css()}</style>
</head>
<body>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <div>
        <strong>Hand Rehab</strong>
        <span>Therapist Console</span>
      </div>
    </div>
    <nav>{nav_html}</nav>
    <a class="theme-toggle" href="?theme={toggled_theme}">{'Dark' if toggled_theme == 'dark' else 'Light'} mode</a>
  </aside>
  <main class="main">
    <header class="topbar">
      <div>
        <h1>{esc(page.title)}</h1>
        <p>Centralized rehabilitation monitoring for clinical review and decision support.</p>
      </div>
      <div class="date-chip">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</div>
    </header>
    {page.body}
  </main>
  <script>{self.js()}</script>
  {page.scripts}
</body>
</html>"""
        return html_doc.encode("utf-8")

    def css(self) -> str:
        return """
:root {
  --bg: #f5f8fc;
  --panel: #ffffff;
  --panel-2: #eef5fa;
  --text: #1c2735;
  --muted: #66778a;
  --line: #d2e0ec;
  --primary: #0077b6;
  --primary-2: #00a0a8;
  --success: #1da365;
  --warning: #dc8f14;
  --danger: #cc404a;
  --shadow: 0 14px 34px rgba(39, 64, 91, .10);
}
[data-theme="dark"] {
  --bg: #101820;
  --panel: #172432;
  --panel-2: #1d3040;
  --text: #ecf4fb;
  --muted: #a6b6c6;
  --line: #2b4256;
  --shadow: 0 18px 42px rgba(0, 0, 0, .28);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
}
a { color: inherit; text-decoration: none; }
.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 250px;
  padding: 22px 16px;
  background: var(--panel);
  border-right: 1px solid var(--line);
}
.brand { display: flex; gap: 12px; align-items: center; margin-bottom: 28px; }
.brand-mark {
  width: 42px; height: 42px; border-radius: 8px;
  display: grid; place-items: center;
  color: white; background: linear-gradient(135deg, var(--primary), var(--primary-2));
  font-weight: 800;
}
.brand strong { display: block; }
.brand span, .topbar p, .muted { color: var(--muted); font-size: 13px; }
.nav-item, .theme-toggle {
  display: block;
  padding: 11px 12px;
  border-radius: 8px;
  margin: 4px 0;
  color: var(--muted);
}
.nav-item.active, .nav-item:hover, .theme-toggle:hover {
  background: var(--panel-2);
  color: var(--primary);
}
.theme-toggle { position: absolute; bottom: 18px; left: 16px; right: 16px; }
.main { margin-left: 250px; padding: 26px; min-height: 100vh; }
.topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
  margin-bottom: 22px;
}
h1 { margin: 0 0 6px; font-size: 28px; letter-spacing: 0; }
h2 { margin: 0 0 14px; font-size: 19px; }
.date-chip, .pill {
  padding: 9px 12px;
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 8px;
  color: var(--muted);
}
.grid { display: grid; gap: 16px; }
.stats { grid-template-columns: repeat(4, minmax(160px, 1fr)); }
.two { grid-template-columns: minmax(0, 1.15fr) minmax(320px, .85fr); }
.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 18px;
  box-shadow: var(--shadow);
}
.stat-label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }
.stat-value { margin-top: 8px; font-size: 30px; font-weight: 800; }
.stat-sub { margin-top: 6px; color: var(--muted); font-size: 13px; }
.toolbar {
  display: flex; gap: 10px; align-items: center; justify-content: space-between;
  margin-bottom: 14px; flex-wrap: wrap;
}
input, select, textarea {
  width: 100%;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--text);
  border-radius: 8px;
  padding: 10px 11px;
  font: inherit;
}
textarea { min-height: 96px; resize: vertical; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.full { grid-column: 1 / -1; }
button, .button {
  border: 0;
  border-radius: 8px;
  padding: 10px 13px;
  background: var(--primary);
  color: white;
  font-weight: 700;
  cursor: pointer;
}
.button.secondary { background: var(--panel-2); color: var(--primary); border: 1px solid var(--line); }
.button.danger, button.danger { background: var(--danger); }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 11px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
tr:hover td { background: var(--panel-2); }
.progress { height: 9px; border-radius: 999px; background: var(--panel-2); overflow: hidden; }
.progress span { display: block; height: 100%; background: linear-gradient(90deg, var(--primary), var(--success)); }
.badge { padding: 4px 8px; border-radius: 999px; font-size: 12px; background: var(--panel-2); color: var(--primary); }
.alert { border-left: 4px solid var(--primary); }
.alert.warning { border-left-color: var(--warning); }
.alert.danger { border-left-color: var(--danger); }
.chart { width: 100%; border-radius: 8px; border: 1px solid var(--line); background: white; }
.tabs { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.pagination { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
@media (max-width: 980px) {
  .sidebar { position: static; width: auto; }
  .theme-toggle { position: static; }
  .main { margin-left: 0; padding: 18px; }
  .stats, .two, .three, .form-grid { grid-template-columns: 1fr; }
  .topbar { align-items: flex-start; flex-direction: column; }
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

    def stat_card(self, label: str, value: str, sub: str = "") -> str:
        return f"""
        <section class="card">
          <div class="stat-label">{esc(label)}</div>
          <div class="stat-value">{esc(value)}</div>
          <div class="stat-sub">{esc(sub)}</div>
        </section>
        """

    def home(self) -> Page:
        stats = self.repo.dashboard_stats()
        recent = self.repo.sessions(limit=8)
        patients = self.repo.patients()
        recent_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['timestamp']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_hand_angle']):.1f} deg</td>
              <td>{esc(format_duration(row['duration']))}</td>
            </tr>
            """
            for row in recent
        ) or '<tr><td colspan="6" class="muted">No session data yet.</td></tr>'
        alert_cards = self.alert_cards()
        body = f"""
        <section class="grid stats">
          {self.stat_card('Total Patients', str(stats['patients']), 'Registered or session-linked patients')}
          {self.stat_card('Active Sessions', str(stats['active_sessions']), 'Sessions recorded in the last 7 days')}
          {self.stat_card('Completed Sessions', str(stats['completed_sessions']), 'All stored rehabilitation sessions')}
          {self.stat_card('Avg Recovery', f"{stats['avg_recovery']:.1f}%", 'Linear trend projection where available')}
          {self.stat_card('Overall Accuracy', f"{stats['overall_accuracy']:.1f}%", 'Average exercise success rate')}
          {self.stat_card('Average ROM', f"{stats['avg_rom']:.1f} deg", 'Mean recorded hand angle')}
          {self.stat_card('Therapy Hours', f"{stats['therapy_hours']:.1f}", 'Total guided session duration')}
          {self.stat_card('Profiles Reviewed', str(len(patients)), 'Available patient records')}
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">
            <div class="toolbar"><h2>Recent Patient Activity</h2><a class="button secondary" href="/sessions">View all</a></div>
            <table>
              <thead><tr><th>Date</th><th>Patient</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead>
              <tbody>{recent_rows}</tbody>
            </table>
          </div>
          <div class="grid">{alert_cards}</div>
        </section>
        """
        return Page("Dashboard Home", body, "home")

    def patients(self, params: dict[str, str]) -> Page:
        q = params.get("q", "").lower()
        stage = params.get("stage", "")
        selected = params.get("patient", "")
        rows = self.repo.patients()
        if q:
            rows = [row for row in rows if q in " ".join(str(row[k] or "") for k in row.keys()).lower()]
        if stage:
            rows = [row for row in rows if row["rehab_stage"] == stage]
        selected_row = self.repo.patient(selected) if selected else None
        table_rows = "".join(
            f"""
            <tr>
              <td><a href="/patients?patient={quote(row['name'])}"><strong>{esc(row['name'])}</strong></a><div class="muted">{esc(row['injury_type'] or 'No injury type set')}</div></td>
              <td>{esc(row['id_number'] or '-')}</td>
              <td>{esc(row['age'] or '-')}</td>
              <td>{esc(row['gender'] or '-')}</td>
              <td>{esc(row['rehab_stage'] or '-')}</td>
              <td>{int(row['sessions_count'])}</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{number(row['avg_rom']):.1f} deg</td>
              <td>{esc(short_date(row['last_session']))}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="8" class="muted">No matching patients.</td></tr>'
        profile = self.patient_profile(selected_row) if selected_row else self.patient_form(None)
        body = f"""
        <section class="grid two">
          <div class="card">
            <div class="toolbar">
              <h2>Patient Management</h2>
              <form method="get" class="toolbar">
                <input name="q" value="{esc(params.get('q',''))}" placeholder="Search patients">
                <select name="stage">
                  {self.option('', 'All stages', stage)}
                  {self.option('Acute', 'Acute', stage)}
                  {self.option('Subacute', 'Subacute', stage)}
                  {self.option('Chronic', 'Chronic', stage)}
                  {self.option('Maintenance', 'Maintenance', stage)}
                </select>
                <button>Filter</button>
              </form>
            </div>
            <table id="patientsTable">
              <thead><tr><th onclick="sortTable('patientsTable',0)">Name</th><th>ID Number</th><th>Age</th><th>Gender</th><th>Stage</th><th>Sessions</th><th>Accuracy</th><th>ROM</th><th>Last Visit</th></tr></thead>
              <tbody>{table_rows}</tbody>
            </table>
          </div>
          {profile}
        </section>
        """
        return Page("Patient Management", body, "patients")

    def patient_form(self, row: sqlite3.Row | None) -> str:
        name = row["name"] if row else ""
        return f"""
        <div class="card">
          <h2>{'Edit Patient Profile' if row else 'Register Patient'}</h2>
          <form method="post" action="/patients/save" class="form-grid">
            <label>Name<input name="name" value="{esc(name)}" {'readonly' if row else ''} required></label>
            <label>ID Number (Login)<input name="id_number" value="{esc(row['id_number'] if row else '')}" placeholder="Optional custom ID"></label>
            <label>Age<input name="age" type="number" min="0" max="120" value="{esc(row['age'] if row else '')}"></label>
            <label>Gender<input name="gender" value="{esc(row['gender'] if row else '')}" placeholder="Female, Male, Other"></label>
            <label>Age group<input name="age_group" value="{esc(row['age_group'] if row else '')}" placeholder="adult, senior"></label>
            <label>Injury type<input name="injury_type" value="{esc(row['injury_type'] if row else '')}" placeholder="Stroke, fracture, tendon injury"></label>
            <label>Rehabilitation stage
              <select name="rehab_stage">
                {self.option('', 'Select stage', row['rehab_stage'] if row else '')}
                {self.option('Acute', 'Acute', row['rehab_stage'] if row else '')}
                {self.option('Subacute', 'Subacute', row['rehab_stage'] if row else '')}
                {self.option('Chronic', 'Chronic', row['rehab_stage'] if row else '')}
                {self.option('Maintenance', 'Maintenance', row['rehab_stage'] if row else '')}
              </select>
            </label>
            <label class="full">Assigned exercises<textarea name="assigned_exercises">{esc(row['assigned_exercises'] if row else '')}</textarea></label>
            <label class="full">Therapist notes<textarea name="therapist_notes">{esc(row['therapist_notes'] if row else '')}</textarea></label>
            <div class="full toolbar">
              <button>Save Patient</button>
              {f'<a class="button secondary" href="/patients?patient={quote(name)}">View History</a>' if row else ''}
            </div>
          </form>
        </div>
        """

    def patient_profile(self, row: sqlite3.Row) -> str:
        sessions = self.repo.sessions(row["name"], limit=12)
        history = "".join(
            f"<tr><td>{esc(short_date(s['timestamp']))}</td><td>{esc(exercise_for_level(s['level']))}</td><td>{number(s['avg_accuracy']):.1f}%</td><td>{number(s['avg_hand_angle']):.1f} deg</td><td>{esc(format_duration(s['duration']))}</td></tr>"
            for s in sessions
        ) or '<tr><td colspan="5" class="muted">No rehabilitation history yet.</td></tr>'
        return f"""
        <div>
          {self.patient_form(row)}
          <div class="card" style="margin-top:16px">
            <div class="toolbar">
              <h2>Complete Rehabilitation History</h2>
              <form method="post" action="/patients/delete" onsubmit="return confirm('Delete this patient profile and notes? Session records are preserved.');">
                <input type="hidden" name="name" value="{esc(row['name'])}">
                <button class="danger">Delete Patient</button>
              </form>
            </div>
            <table><thead><tr><th>Date</th><th>Exercise</th><th>Accuracy</th><th>ROM</th><th>Duration</th></tr></thead><tbody>{history}</tbody></table>
          </div>
        </div>
        """

    def option(self, value: str, label: str, selected: str) -> str:
        return f'<option value="{esc(value)}" {"selected" if value == selected else ""}>{esc(label)}</option>'

    def sessions_page(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        rows = self.repo.sessions(patient)
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        table_rows = "".join(
            f"""
            <tr>
              <td>{esc(short_date(row['timestamp']))}</td>
              <td>{esc(row['patient_id'])}</td>
              <td>{esc(exercise_for_level(row['level']))}</td>
              <td>{esc(format_duration(row['duration']))}</td>
              <td>{number(row['max_finger_extension']):.1f}px</td>
              <td>{number(row['avg_hand_angle']):.1f} deg</td>
              <td>{number(row['avg_accuracy']):.1f}%</td>
              <td>{int(number(row['pain_level']))}/10</td>
              <td>{esc(tremor_rating_for_sessions(self.repo.sessions_chrono(row['patient_id'])))}</td>
              <td>{int(number(row['score']))}</td>
              <td>{self.prediction_badge(row['patient_id'])}</td>
            </tr>
            """
            for row in rows
        ) or '<tr><td colspan="11" class="muted">No sessions found.</td></tr>'
        body = f"""
        <section class="card">
          <div class="toolbar">
            <h2>Session History</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <button>Filter</button>
            </form>
          </div>
          <input id="sessionSearch" oninput="filterTable('sessionSearch','sessionsTable')" placeholder="Search session table">
          <table id="sessionsTable" style="margin-top:12px">
            <thead><tr>
              <th onclick="sortTable('sessionsTable',0)">Date</th><th>Patient</th><th>Exercise</th><th>Duration</th><th>Max ROM</th><th>Avg ROM</th><th>Accuracy</th><th>Pain</th><th>Tremor</th><th>Score</th><th>Recovery</th>
            </tr></thead>
            <tbody>{table_rows}</tbody>
          </table>
          <div class="pagination"><span class="pill">Client-side sorting, filtering, and table search enabled</span></div>
        </section>
        """
        return Page("Session History", body, "sessions")

    def prediction_badge(self, patient: str) -> str:
        pred = recovery_prediction(self.repo.sessions_chrono(patient))
        if pred < 0:
            return '<span class="badge">Need data</span>'
        return f'<span class="badge">{pred:.1f}%</span>'

    def analytics(self, params: dict[str, str]) -> Page:
        patient = params.get("patient", "")
        sessions = self.repo.sessions_chrono(patient)
        labels = [short_date(row["timestamp"]) for row in sessions[-16:]]
        acc = [number(row["avg_accuracy"]) for row in sessions[-16:]]
        rom = [number(row["avg_hand_angle"]) for row in sessions[-16:]]
        pain = [number(row["pain_level"]) for row in sessions[-16:]]
        completion = [1 if number(row["avg_accuracy"]) >= 60 else 0 for row in sessions[-16:]]
        weekly = self.bucket_progress(sessions, "%Y-W%W")
        monthly = self.bucket_progress(sessions, "%Y-%m")
        patient_options = "".join(self.option(row["name"], row["name"], patient) for row in self.repo.patients())
        body = f"""
        <section class="card">
          <form method="get" class="toolbar">
            <h2>Progress Analytics</h2>
            <select name="patient"><option value="">All patients</option>{patient_options}</select>
            <button>Apply</button>
          </form>
        </section>
        <section class="grid two" style="margin-top:16px">
          <div class="card">{self.chart('ROM Improvement', {'Average ROM': rom}, labels, 'degrees')}</div>
          <div class="card">{self.chart('Accuracy Trend', {'Accuracy': acc}, labels, '%')}</div>
          <div class="card">{self.chart('Pain Level Trend', {'Pain': pain}, labels, 'NRS')}</div>
          <div class="card">{self.chart('Exercise Completion Rate', {'Completed': completion}, labels, 'completed')}</div>
          <div class="card">{self.chart('Weekly Progress', {'Weekly Accuracy': weekly[1]}, weekly[0], '%')}</div>
          <div class="card">{self.chart('Monthly Progress', {'Monthly Accuracy': monthly[1]}, monthly[0], '%')}</div>
        </section>
        """
        return Page("Progress Analytics", body, "analytics")

    def bucket_progress(self, sessions: list[sqlite3.Row], fmt: str) -> tuple[list[str], list[float]]:
        buckets: dict[str, list[float]] = {}
        for row in sessions:
            try:
                key = datetime.fromisoformat(str(row["timestamp"])).strftime(fmt)
            except ValueError:
                key = str(row["timestamp"])[:7]
            buckets.setdefault(key, []).append(number(row["avg_accuracy"]))
        labels = list(buckets.keys())[-12:]
        values = [sum(buckets[label]) / len(buckets[label]) for label in labels]
        return labels, values

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
              <a class="button" href="/report.pdf?patient={quote(selected)}">Download PDF Report</a>
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

    def performance(self, params: dict[str, str]) -> Page:
        rows = self.repo.sessions()
        by_exercise: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            by_exercise.setdefault(exercise_for_level(row["level"]), []).append(row)
        perf_rows = []
        for exercise, items in by_exercise.items():
            attempts = len(items)
            correct = sum(1 for row in items if number(row["avg_accuracy"]) >= 60)
            incorrect = attempts - correct
            avg_accuracy = sum(number(row["avg_accuracy"]) for row in items) / attempts if attempts else 0
            time_spent = sum(number(row["duration"]) for row in items)
            perf_rows.append((exercise, attempts, correct, incorrect, avg_accuracy, time_spent))
        best = max(perf_rows, key=lambda item: item[4], default=None)
        weakest = min(perf_rows, key=lambda item: item[4], default=None)
        table = "".join(
            f"""
            <tr><td>{esc(ex)}</td><td>{done}</td><td>{correct}</td><td>{incorrect}</td><td>{acc:.1f}%</td><td>{time_spent/60:.1f} min</td></tr>
            """
            for ex, done, correct, incorrect, acc, time_spent in perf_rows
        ) or '<tr><td colspan="6" class="muted">No exercise data available.</td></tr>'
        body = f"""
        <section class="grid three">
          {self.stat_card('Best Exercise', best[0] if best else '-', f'{best[4]:.1f}% accuracy' if best else '')}
          {self.stat_card('Weakest Exercise', weakest[0] if weakest else '-', f'{weakest[4]:.1f}% accuracy' if weakest else '')}
          {self.stat_card('Exercises Completed', str(sum(item[1] for item in perf_rows)), 'Session-level completions')}
        </section>
        <section class="card" style="margin-top:16px">
          <h2>Exercise Performance</h2>
          <table><thead><tr><th>Exercise</th><th>Completed</th><th>Correct</th><th>Incorrect</th><th>Accuracy</th><th>Time Spent</th></tr></thead><tbody>{table}</tbody></table>
        </section>
        """
        return Page("Exercise Performance", body, "performance")

    def notes(self, params: dict[str, str]) -> Page:
        selected = params.get("patient", "")
        patients = self.repo.patients()
        patient_options = "".join(self.option(row["name"], row["name"], selected) for row in patients)
        session_options = "".join(
            f'<option value="{row["id"]}">{esc(short_date(row["timestamp"]))} - {esc(exercise_for_level(row["level"]))}</option>'
            for row in self.repo.sessions(selected, limit=30)
        )
        note_rows = "".join(
            f"""
            <div class="card">
              <div class="toolbar"><strong>{esc(row['patient_name'])}</strong><span class="badge">{esc(row['note_type'])}</span></div>
              <p>{esc(row['note'])}</p>
              <p class="muted"><strong>Recommendation:</strong> {esc(row['recommendation'] or '-')}</p>
              <p class="muted"><strong>Next plan:</strong> {esc(row['next_plan'] or '-')}</p>
              <span class="muted">{esc(short_date(row['created_at']))}</span>
            </div>
            """
            for row in self.repo.notes(selected)
        ) or '<div class="card muted">No therapist notes recorded.</div>'
        body = f"""
        <section class="grid two">
          <div class="card">
            <h2>Therapist Notes</h2>
            <form method="get" class="toolbar">
              <select name="patient"><option value="">All patients</option>{patient_options}</select>
              <button>Filter</button>
            </form>
            <form method="post" action="/notes/save" class="form-grid">
              <label>Patient<select name="patient_name" required><option value="">Select patient</option>{patient_options}</select></label>
              <label>Session<select name="session_id"><option value="">General note</option>{session_options}</select></label>
              <label>Type<select name="note_type"><option>Observation</option><option>Recommendation</option><option>Next Session Plan</option><option>Risk Note</option></select></label>
              <label class="full">Observation<textarea name="note" required></textarea></label>
              <label class="full">Recommendation<textarea name="recommendation"></textarea></label>
              <label class="full">Next rehabilitation session plan<textarea name="next_plan"></textarea></label>
              <button class="full">Add Note</button>
            </form>
          </div>
          <div class="grid">{note_rows}</div>
        </section>
        """
        return Page("Therapist Notes", body, "notes")

    def notifications(self) -> Page:
        body = f'<section class="grid two">{self.alert_cards(full=True)}</section>'
        return Page("Notifications", body, "notifications")

    def alert_cards(self, full: bool = False) -> str:
        alerts = self.alerts()
        if not alerts:
            alerts = [("No critical alerts", "All tracked sessions are within expected monitoring thresholds.", "")]
        return "".join(
            f'<div class="card alert {esc(level)}"><h2>{esc(title)}</h2><p class="muted">{esc(message)}</p></div>'
            for title, message, level in alerts[:12 if full else 4]
        )

    def alerts(self) -> list[tuple[str, str, str]]:
        alerts: list[tuple[str, str, str]] = []
        now = datetime.now()
        for patient in self.repo.patients():
            name = patient["name"]
            sessions = self.repo.sessions_chrono(name)
            if not sessions:
                alerts.append((f"{name}: no completed sessions", "Patient is registered but has no stored rehabilitation session.", "warning"))
                continue
            last = sessions[-1]
            try:
                last_dt = datetime.fromisoformat(str(last["timestamp"]))
                if now - last_dt > timedelta(days=7):
                    alerts.append((f"{name}: missed therapy", f"Last session was on {short_date(last['timestamp'])}.", "warning"))
            except ValueError:
                pass
            if number(last["pain_level"]) >= 7:
                alerts.append((f"{name}: high pain score", f"Latest pain score is {int(number(last['pain_level']))}/10.", "danger"))
            if number(last["avg_accuracy"]) < 50:
                alerts.append((f"{name}: low exercise accuracy", f"Latest accuracy is {number(last['avg_accuracy']):.1f}%.", "danger"))
            if len(sessions) >= 2:
                delta = number(sessions[-1]["avg_hand_angle"]) - number(sessions[-2]["avg_hand_angle"])
                if delta >= 10:
                    alerts.append((f"{name}: significant improvement", f"ROM improved by {delta:.1f} degrees since the previous session.", ""))
                elif delta < -8:
                    alerts.append((f"{name}: slow recovery risk", f"ROM decreased by {abs(delta):.1f} degrees since the previous session.", "warning"))
        return alerts

    def report_pdf(self, patient_name: str) -> bytes:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except Exception as exc:
            return f"PDF export requires reportlab. Import error: {exc}".encode("utf-8")

        patient = self.repo.patient(patient_name)
        sessions = self.repo.sessions_chrono(patient_name)
        notes = self.repo.notes(patient_name)
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
        summary = [
            f"Completed Sessions: {len(sessions)}",
            f"Average Accuracy: {avg_acc:.1f}%",
            f"Average ROM: {avg_rom:.1f} degrees",
            f"Recovery Prediction: {pred:.1f}%" if pred >= 0 else "Recovery Prediction: Need more data",
        ]
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Session Summary")
        y -= 18
        pdf.setFont("Helvetica", 10)
        for line in summary:
            pdf.drawString(60, y, line)
            y -= 15
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
                f"Pain {int(number(row['pain_level']))}/10"
            )
            pdf.drawString(60, y, line[:110])
            y -= 13
        y -= 8
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(50, y, "Therapist Observations")
        y -= 18
        pdf.setFont("Helvetica", 9)
        observation_lines = [n["note"] for n in notes[:6]] or ["No therapist notes recorded."]
        for line in observation_lines:
            for chunk in [line[i:i + 95] for i in range(0, len(line), 95)]:
                if y < 80:
                    pdf.showPage()
                    y = height - 50
                pdf.drawString(60, y, chunk)
                y -= 13
        pdf.save()
        return buf.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    repo = DashboardRepository(DB_PATH)
    renderer = DashboardRenderer(repo)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        path = parsed.path.rstrip("/") or "/"
        if path == "/report.pdf":
            patient = params.get("patient", "")
            data = self.renderer.report_pdf(patient)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="rehab_report_{quote(patient or "patient")}.pdf"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        page_map = {
            "/": self.renderer.home,
            "/patients": lambda: self.renderer.patients(params),
            "/sessions": lambda: self.renderer.sessions_page(params),
            "/analytics": lambda: self.renderer.analytics(params),
            "/reports": lambda: self.renderer.reports(params),
            "/performance": lambda: self.renderer.performance(params),
            "/notes": lambda: self.renderer.notes(params),
            "/notifications": self.renderer.notifications,
        }
        page_factory = page_map.get(path)
        if not page_factory:
            self.send_error(HTTPStatus.NOT_FOUND, "Page not found")
            return
        body = self.renderer.layout(page_factory(), params)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8")
        form = {key: values[-1] for key, values in parse_qs(data).items()}
        path = urlparse(self.path).path
        if path == "/patients/save":
            self.repo.save_patient(form)
            self.redirect(f"/patients?patient={quote(form.get('name', ''))}")
        elif path == "/patients/delete":
            self.repo.delete_patient(form.get("name", ""))
            self.redirect("/patients")
        elif path == "/notes/save":
            self.repo.save_note(form)
            patient = form.get("patient_name", "")
            self.redirect(f"/notes?patient={quote(patient)}")
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Action not found")

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()


def run_server(host: str = HOST, port: int = PORT, open_browser: bool = True) -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    url = f"http://{host}:{port}"
    print("=" * 64)
    print("AI Hand Rehabilitation - Therapist Dashboard")
    print("=" * 64)
    print(f"Dashboard URL: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    chosen_port = PORT
    if len(sys.argv) > 1:
        try:
            chosen_port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port=chosen_port)
