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



class AuthPagesMixin:
    def login_page(self, error: str = "") -> str:
        error_html = f'<div class="error" style="background: #fef3f2; border: 1px solid #fecdca; color: #cc404a; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px;">{esc(error)}</div>' if error else ""
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Therapist Login - AI Hand Rehab</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      color: #1e293b;
    }}
    .login-card {{
      background: white;
      border-radius: 16px;
      padding: 48px 40px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      width: 100%;
      max-width: 420px;
    }}
    .brand {{
      text-align: center;
      margin-bottom: 32px;
    }}
    .brand-mark {{
      width: 64px;
      height: 64px;
      border-radius: 12px;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      display: grid;
      place-items: center;
      font-size: 28px;
      font-weight: 800;
      margin: 0 auto 16px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      color: #0f172a;
    }}
    .subtitle {{
      color: #64748b;
      font-size: 14px;
      margin: 0;
    }}
    .form-group {{
      margin-bottom: 20px;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      font-size: 14px;
      color: #334155;
    }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border: 2px solid #e2e8f0;
      border-radius: 8px;
      font: inherit;
      font-size: 15px;
      color: #0f172a;
    }}
    input:focus {{
      outline: none;
      border-color: #2563eb;
    }}
    button {{
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      border: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
      transition: transform 0.2s;
    }}
    button:hover {{
      transform: translateY(-2px);
    }}
    .footer {{
      text-align: center;
      margin-top: 24px;
      color: #64748b;
      font-size: 13px;
    }}
    .links {{
      display: flex;
      justify-content: space-between;
      margin-top: 16px;
      font-size: 13px;
    }}
    .links a {{
      color: #2563eb;
      text-decoration: none;
    }}
    .links a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div class="login-card">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <h1>Therapist Login</h1>
      <p class="subtitle">AI Hand Rehabilitation System</p>
    </div>
    {error_html}
    <form method="post" action="/login">
      <div class="form-group">
        <label>Username</label>
        <input type="text" name="username" required autofocus>
      </div>
      <div class="form-group">
        <label>Password</label>
        <input type="password" name="password" required>
      </div>
      <button type="submit">Sign In</button>
    </form>
    <div class="links">
      <a href="/register">Register Account</a>
      <a href="/reset-password">Forgot Password?</a>
    </div>
    <div class="footer">
      <p>Secure access for authorized therapists only</p>
    </div>
  </div>
</body>
</html>"""

    def register_page(self, error: str = "", success: str = "") -> str:
        error_html = f'<div class="error" style="background: #fef3f2; border: 1px solid #fecdca; color: #cc404a; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px;">{esc(error)}</div>' if error else ""
        success_html = f'<div class="success" style="background: #ecfdf5; border: 1px solid #a7f3d0; color: #047857; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px;">{esc(success)}</div>' if success else ""
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Therapist Registration - AI Hand Rehab</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      color: #1e293b;
    }}
    .login-card {{
      background: white;
      border-radius: 16px;
      padding: 48px 40px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      width: 100%;
      max-width: 420px;
    }}
    .brand {{
      text-align: center;
      margin-bottom: 32px;
    }}
    .brand-mark {{
      width: 64px;
      height: 64px;
      border-radius: 12px;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      display: grid;
      place-items: center;
      font-size: 28px;
      font-weight: 800;
      margin: 0 auto 16px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      color: #0f172a;
    }}
    .subtitle {{
      color: #64748b;
      font-size: 14px;
      margin: 0;
    }}
    .form-group {{
      margin-bottom: 20px;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      font-size: 14px;
      color: #334155;
    }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border: 2px solid #e2e8f0;
      border-radius: 8px;
      font: inherit;
      font-size: 15px;
      color: #0f172a;
    }}
    input:focus {{
      outline: none;
      border-color: #2563eb;
    }}
    button {{
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      border: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
      transition: transform 0.2s;
    }}
    button:hover {{
      transform: translateY(-2px);
    }}
    .footer {{
      text-align: center;
      margin-top: 24px;
      color: #64748b;
      font-size: 13px;
    }}
    .links {{
      display: flex;
      justify-content: center;
      margin-top: 16px;
      font-size: 13px;
    }}
    .links a {{
      color: #2563eb;
      text-decoration: none;
    }}
    .links a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div class="login-card">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <h1>Register Account</h1>
      <p class="subtitle">AI Hand Rehabilitation System</p>
    </div>
    {error_html}
    {success_html}
    <form method="post" action="/register">
      <div class="form-group">
        <label>Username</label>
        <input type="text" name="username" required autofocus>
      </div>
      <div class="form-group">
        <label>Password</label>
        <input type="password" name="password" required placeholder="Min 8 chars, letters & digits">
      </div>
      <div class="form-group">
        <label>Confirm Password</label>
        <input type="password" name="confirm_password" required>
      </div>
      <button type="submit">Sign Up</button>
    </form>
    <div class="links">
      <a href="/login">Back to Login</a>
    </div>
    <div class="footer">
      <p>Secure therapist registration portal</p>
    </div>
  </div>
</body>
</html>"""

    def reset_password_page(self, status: str = "") -> str:
        status_html = f'<div class="info" style="background: #eff6ff; border: 1px solid #bfdbfe; color: #1e3a8a; padding: 16px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; line-height: 1.5;">{esc(status)}</div>' if status else ""
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reset Password - AI Hand Rehab</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      color: #1e293b;
    }}
    .login-card {{
      background: white;
      border-radius: 16px;
      padding: 48px 40px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      width: 100%;
      max-width: 420px;
    }}
    .brand {{
      text-align: center;
      margin-bottom: 32px;
    }}
    .brand-mark {{
      width: 64px;
      height: 64px;
      border-radius: 12px;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      display: grid;
      place-items: center;
      font-size: 28px;
      font-weight: 800;
      margin: 0 auto 16px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      color: #0f172a;
    }}
    .subtitle {{
      color: #64748b;
      font-size: 14px;
      margin: 0;
    }}
    .form-group {{
      margin-bottom: 20px;
    }}
    label {{
      display: block;
      margin-bottom: 8px;
      font-weight: 600;
      font-size: 14px;
      color: #334155;
    }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border: 2px solid #e2e8f0;
      border-radius: 8px;
      font: inherit;
      font-size: 15px;
      color: #0f172a;
    }}
    input:focus {{
      outline: none;
      border-color: #2563eb;
    }}
    button {{
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #2563eb, #06b6d4);
      color: white;
      border: none;
      border-radius: 8px;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
      transition: transform 0.2s;
    }}
    button:hover {{
      transform: translateY(-2px);
    }}
    .footer {{
      text-align: center;
      margin-top: 24px;
      color: #64748b;
      font-size: 13px;
    }}
    .links {{
      display: flex;
      justify-content: center;
      margin-top: 16px;
      font-size: 13px;
    }}
    .links a {{
      color: #2563eb;
      text-decoration: none;
    }}
    .links a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div class="login-card">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <h1>Reset Password</h1>
      <p class="subtitle">AI Hand Rehabilitation System</p>
    </div>
    {status_html}
    <form method="post" action="/reset-password">
      <div class="form-group">
        <label>Username</label>
        <input type="text" name="username" required autofocus>
      </div>
      <button type="submit">Send Reset Request</button>
    </form>
    <div class="links">
      <a href="/login">Back to Login</a>
    </div>
    <div class="footer">
      <p>Secure password reset gateway</p>
    </div>
  </div>
</body>
</html>"""

    def security_overview(self, params: dict[str, str] | None = None) -> Page:
        # Fetch stats from db
        total_patients = self.repo.scalar("SELECT COUNT(*) FROM patients")
        total_therapists = self.repo.scalar("SELECT COUNT(*) FROM therapists")
        total_users = total_patients + total_therapists
        
        active_sessions = len(SESSIONS)
        
        failed_logins = self.repo.scalar("SELECT COUNT(*) FROM audit_logs WHERE action = 'Login Failure'")
        total_audit_logs = self.repo.scalar("SELECT COUNT(*) FROM audit_logs")
        
        body = f"""
        <div class="grid col-3">
          {self.stat_card('Total Users', str(total_users), 'Registered patient profiles & therapist credentials')}
          {self.stat_card('Active Sessions', str(active_sessions), 'Currently authenticated therapist browser contexts')}
          {self.stat_card('Failed Login Attempts', str(failed_logins), 'Unsuccessful therapist sign-in operations')}
          {self.stat_card('Audit Trail Size', str(total_audit_logs), 'Total recorded clinical and security events')}
          {self.stat_card('Encryption Status', 'Active', 'AES-256 deterministic & non-deterministic field-level')}
          {self.stat_card('Privacy Mode', 'Active', 'Landmark-only webcam feed, no image storage')}
        </div>
        
        <div class="card glass-panel" style="margin-top: 24px;">
          <h2>Security Architecture Status</h2>
          <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
            <thead>
              <tr style="border-bottom: 2px solid var(--line); text-align: left;">
                <th style="padding: 12px;">Security Control</th>
                <th style="padding: 12px;">Standard / Algorithm</th>
                <th style="padding: 12px;">Status</th>
                <th style="padding: 12px;">Details</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom: 1px solid var(--line);">
                <td style="padding: 12px; font-weight: 600;">Credential Hashing</td>
                <td style="padding: 12px;">bcrypt (Salted, Work Factor = 12)</td>
                <td style="padding: 12px;"><span class="badge success">Enforced</span></td>
                <td style="padding: 12px;">Protects patient IDs & therapist passwords from rainbow table attacks.</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--line);">
                <td style="padding: 12px; font-weight: 600;">Data Encryption at Rest</td>
                <td style="padding: 12px;">AES-256 CBC & Fernet</td>
                <td style="padding: 12px;"><span class="badge success">Active</span></td>
                <td style="padding: 12px;">Encryption key stored separately in <code>secret.key</code>. Names and notes are fully encrypted.</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--line);">
                <td style="padding: 12px; font-weight: 600;">Biometric Privacy</td>
                <td style="padding: 12px;">Google MediaPipe Landmarks</td>
                <td style="padding: 12px;"><span class="badge success">Active</span></td>
                <td style="padding: 12px;">Webcam frames processed entirely in-memory. Zero photo/video files written to disk.</td>
              </tr>
              <tr style="border-bottom: 1px solid var(--line);">
                <td style="padding: 12px; font-weight: 600;">Audit Trails</td>
                <td style="padding: 12px;">Internal SQL Audit Logging</td>
                <td style="padding: 12px;"><span class="badge success">Active</span></td>
                <td style="padding: 12px;">Tracks all authentication, patient record editing, reports, and security events.</td>
              </tr>
            </tbody>
          </table>
        </div>
        """
        return Page("Security Overview", body, "security")

