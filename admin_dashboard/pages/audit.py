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



class AuditPagesMixin:
    def audit_logs_page(self, params: dict[str, str] | None = None) -> Page:
        params = params or {}
        search = params.get("search", "").strip()
        status_filter = params.get("status", "").strip()
        
        # Build query
        query_str = "SELECT * FROM audit_logs"
        conditions = []
        args = []
        if search:
            conditions.append("(username LIKE ? OR action LIKE ? OR target LIKE ?)")
            search_param = f"%{search}%"
            args.extend([search_param, search_param, search_param])
        if status_filter:
            conditions.append("status = ?")
            args.append(status_filter)
            
        if conditions:
            query_str += " WHERE " + " AND ".join(conditions)
        query_str += " ORDER BY timestamp DESC LIMIT 100"
        
        rows = self.repo.query(query_str, args)
        
        # Render rows
        rows_html = ""
        for r in rows:
            status_badge = "success" if r['status'] == "Success" else "danger"
            rows_html += f"""
            <tr style="border-bottom: 1px solid var(--line);">
              <td style="padding: 12px;">{esc(r['timestamp'])}</td>
              <td style="padding: 12px; font-weight: 600;">{esc(r['username'] or 'System')}</td>
              <td style="padding: 12px;">{esc(r['role'])}</td>
              <td style="padding: 12px; font-weight: 600;">{esc(r['action'])}</td>
              <td style="padding: 12px;">{esc(r['target'])}</td>
              <td style="padding: 12px;">{esc(r['ip_address'])}</td>
              <td style="padding: 12px;"><span class="badge {status_badge}">{esc(r['status'])}</span></td>
            </tr>
            """
        if not rows:
            rows_html = '<tr><td colspan="7" class="muted" style="padding: 24px; text-align: center;">No audit logs matched your query.</td></tr>'
            
        body = f"""
        <div class="card glass-panel">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 16px;">
            <form method="get" action="/audit-logs" style="display: flex; gap: 12px; align-items: center; flex-grow: 1; max-width: 600px;">
              <input type="text" name="search" value="{esc(search)}" placeholder="Search logs by user, action, target..." class="search-input" style="flex-grow: 1; padding: 10px; border: 1px solid var(--line); border-radius: 6px;">
              <select name="status" style="padding: 10px; border: 1px solid var(--line); border-radius: 6px; background: white; color: var(--text); height: 38px;">
                <option value="">All Statuses</option>
                <option value="Success" {"selected" if status_filter == "Success" else ""}>Success</option>
                <option value="Failed" {"selected" if status_filter == "Failed" else ""}>Failed</option>
              </select>
              <button type="submit" class="btn" style="padding: 10px 16px; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; height: 38px;">Filter</button>
            </form>
            <a href="/audit-logs/export" class="btn" style="padding: 10px 16px; background: var(--success); color: white; border-radius: 6px; text-decoration: none; font-weight: 600; line-height: 1.4;">📥 Export Audit Logs (CSV)</a>
          </div>
          
          <div style="overflow-x: auto;">
            <div class="table-container" style="margin-top:24px;">
<table style="width: 100%; border-collapse: collapse;">
              <thead>
                <tr style="border-bottom: 2px solid var(--line); text-align: left; background: var(--panel-2);">
                  <th style="padding: 12px;">Timestamp</th>
                  <th style="padding: 12px;">User</th>
                  <th style="padding: 12px;">Role</th>
                  <th style="padding: 12px;">Action</th>
                  <th style="padding: 12px;">Target</th>
                  <th style="padding: 12px;">IP Address</th>
                  <th style="padding: 12px;">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
</div>
          </div>
        </div>
        """
        return Page("Security Audit Trail", body, "audit")

