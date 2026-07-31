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
from admin_dashboard.renderer import *

class DashboardHandler(BaseHTTPRequestHandler):
    repo = DashboardRepository(DB_PATH)
    renderer = DashboardRenderer(repo)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def get_cookie(self, name: str) -> str:
        cookies = self.headers.get("Cookie", "")
        for cookie in cookies.split(";"):
            cookie = cookie.strip()
            if cookie.startswith(name + "="):
                return cookie[len(name) + 1 :]
        return ""

    def get_current_user(self) -> str | None:
        token = self.get_cookie("session_token")
        return get_session(token)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        params = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        path = parsed.path.rstrip("/") or "/"
        
        username = self.get_current_user()

        # Handle Auth Paths
        if path == "/login":
            if username:
                self.redirect("/")
            else:
                body = self.renderer.login_page()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
            return

        if path == "/register":
            if username:
                self.redirect("/")
            else:
                body = self.renderer.register_page()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
            return

        if path == "/reset-password":
            body = self.renderer.reset_password_page()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        # Access Control Verification
        if not username:
            # Log unauthorized access attempt
            security_utils.log_audit_event(
                DB_PATH,
                user_id="",
                username="Anonymous",
                role="Unknown",
                action="Unauthorized Access Attempt",
                target=f"Path: {path}",
                ip_address=self.client_address[0],
                status="Failed"
            )
            self.redirect("/login")
            return

        # Add username to params for display in layout
        params["_username"] = username

        if path == "/logout":
            token = self.get_cookie("session_token")
            clear_session(token)
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="Logout",
                target="Therapist Portal",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Set-Cookie", "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            self.send_header("Location", "/login")
            self.send_status(HTTPStatus.SEE_OTHER)
            self.end_headers()
            return

        if path == "/report.pdf":
            patient = params.get("patient", "")
            data = self.renderer.report_pdf(patient)
            # Log PDF Download
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="PDF Downloaded",
                target=f"Patient Report: {patient}",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="rehab_report_{quote(patient or "patient")}.pdf"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/audit-logs/export":
            # Generate CSV file of audit logs
            csv_data = "Timestamp,User,Role,Action,Target,IP Address,Status\n"
            rows = self.repo.query("SELECT * FROM audit_logs ORDER BY timestamp DESC")
            for r in rows:
                csv_data += f'"{r["timestamp"]}","{r["username"]}","{r["role"]}","{r["action"]}","{r["target"]}","{r["ip_address"]}","{r["status"]}"\n'
            # Log CSV Export Event
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="Audit Logs Exported",
                target="Audit Logs CSV File",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="security_audit_logs.csv"')
            self.send_header("Content-Length", str(len(csv_data)))
            self.end_headers()
            self.wfile.write(csv_data.encode("utf-8"))
            return

        # Static files serving
        if path.startswith("/static/"):
            filepath = os.path.join(os.path.dirname(__file__), path.lstrip("/"))
            if os.path.exists(filepath):
                with open(filepath, "rb") as f:
                    content = f.read()
                self.send_response(HTTPStatus.OK)
                if path.endswith(".css"):
                    self.send_header("Content-Type", "text/css")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                return

        # Audit logs patient views
        if path == "/patients" and params.get("patient"):
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="Patient Viewed",
                target=f"Patient: {params.get('patient')}",
                ip_address=self.client_address[0],
                status="Success"
            )

        page_map = {
            "/": self.renderer.home,
            "/patients": lambda: self.renderer.patients(params),
            "/sessions": lambda: self.renderer.sessions_page(params),
            "/analytics": lambda: self.renderer.analytics(params),
            "/adaptive": lambda: self.renderer.adaptive_ai(params),
            "/sensei": lambda: self.renderer.sensei_review(params),
            "/risks": lambda: self.renderer.risks_page(params),
            "/digital-twin": lambda: self.renderer.digital_twin_page(params),
            "/reports": lambda: self.renderer.reports(params),
            "/performance": lambda: self.renderer.performance(params),
            "/research": lambda: self.renderer.research_dashboard(params),
            "/notes": lambda: self.renderer.notes(params),
            "/notifications": self.renderer.notifications,
            "/security": lambda: self.renderer.security_overview(params),
            "/audit-logs": lambda: self.renderer.audit_logs_page(params),
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
        
        username = self.get_current_user()

        # Unauthenticated Handlers
        if path == "/login":
            user = form.get("username", "").strip()
            pwd = form.get("password", "")
            if self.repo.verify_therapist(user, pwd):
                token = create_session(user)
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Set-Cookie", f"session_token={token}; Path=/; HttpOnly")
                self.send_header("Location", "/")
                self.end_headers()
            else:
                body = self.renderer.login_page(error="Invalid username or password.")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
            return

        if path == "/register":
            user = form.get("username", "").strip()
            pwd = form.get("password", "")
            confirm = form.get("confirm_password", "")
            
            if not user or not pwd:
                err = "Username and password are required."
            elif pwd != confirm:
                err = "Passwords do not match."
            else:
                valid, strength_err = security_utils.validate_password_strength(pwd)
                if not valid:
                    err = strength_err
                else:
                    # Check if user exists
                    existing = self.repo.query("SELECT username FROM therapists WHERE username = ?", (user,))
                    if existing:
                        err = f"Username '{user}' is already taken."
                    else:
                        hashed = security_utils.hash_password(pwd)
                        self.repo.execute("INSERT INTO therapists (username, password_hash) VALUES (?, ?)", (user, hashed))
                        # Log registration
                        security_utils.log_audit_event(
                            DB_PATH,
                            user_id=user,
                            username=user,
                            role="Therapist",
                            action="Therapist Registered",
                            target="Therapist Credentials",
                            ip_address=self.client_address[0],
                            status="Success"
                        )
                        body = self.renderer.register_page(success="Registration successful! You can now log in.")
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body.encode("utf-8"))
                        return
            
            body = self.renderer.register_page(error=err)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        if path == "/reset-password":
            user = form.get("username", "").strip()
            instruction = security_utils.request_password_reset_placeholder(user)
            # Log Reset request
            security_utils.log_audit_event(
                DB_PATH,
                user_id="",
                username=user,
                role="Therapist",
                action="Password Reset Request",
                target="Password Reset Gateway",
                ip_address=self.client_address[0],
                status="Success"
            )
            body = self.renderer.reset_password_page(status=instruction)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))
            return

        # Authenticated Write Handlers
        if not username:
            self.redirect("/login")
            return

        if path == "/patients/save":
            self.repo.save_patient(form)
            # Log Patient Save
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="Patient Created/Updated",
                target=f"Patient: {form.get('name')}",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.redirect(f"/patients?patient={quote(form.get('name', ''))}")
        elif path == "/patients/delete":
            name = form.get("name", "")
            self.repo.delete_patient(name)
            # Log Patient Delete
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="Patient Deleted",
                target=f"Patient: {name}",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.redirect("/patients")
        elif path == "/notes/save":
            self.repo.save_note(form)
            patient = form.get("patient_name", "")
            note_id = form.get("note_id", "")
            action = "Note Edited" if note_id.isdigit() else "Note Added"
            # Log Note Save
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action=action,
                target=f"Patient: {patient}",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.redirect(f"/notes?patient={quote(patient)}")
        elif path == "/adaptive/override":
            self.repo.save_override(form)
            # Log Prescription Override
            security_utils.log_audit_event(
                DB_PATH,
                user_id=username,
                username=username,
                role="Therapist",
                action="Prescription Reviewed",
                target=f"Prescription ID: {form.get('prescription_id')}",
                ip_address=self.client_address[0],
                status="Success"
            )
            self.redirect("/adaptive")
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Action not found")

    def send_status(self, status: HTTPStatus) -> None:
        self.wfile.write(b"") # Placeholder for override to allow SEE_OTHER redirect

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


