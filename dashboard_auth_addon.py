"""
Authentication addon for therapist_dashboard.py
Add this at the beginning of the file after imports
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

# Session storage (in production, use Redis or database)
SESSIONS: dict[str, tuple[str, datetime]] = {}
SESSION_DURATION = timedelta(hours=8)


def hash_password_sha256(password: str) -> str:
    """SHA-256 hash for compatibility with zero_keyboard_physio.py"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify password against SHA-256 hash"""
    return stored_hash == hash_password_sha256(password)


def create_session(username: str) -> str:
    """Create a new session token"""
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (username, datetime.now() + SESSION_DURATION)
    return token


def get_session(token: str) -> Optional[str]:
    """Get username from session token"""
    if token not in SESSIONS:
        return None
    username, expires = SESSIONS[token]
    if datetime.now() > expires:
        del SESSIONS[token]
        return None
    # Extend session on activity
    SESSIONS[token] = (username, datetime.now() + SESSION_DURATION)
    return username


def clear_session(token: str) -> None:
    """Clear session token"""
    if token in SESSIONS:
        del SESSIONS[token]


def render_login_page(error: str = "") -> str:
    """Render therapist login page"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Therapist Login - Hand Rehab Dashboard</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: linear-gradient(135deg, #0077b6 0%, #00a0a8 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      color: #1c2735;
    }}
    .login-card {{
      background: white;
      border-radius: 16px;
      padding: 48px 40px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
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
      background: linear-gradient(135deg, #0077b6, #00a0a8);
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
    }}
    .subtitle {{
      color: #66778a;
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
    }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border: 2px solid #d2e0ec;
      border-radius: 8px;
      font: inherit;
      font-size: 15px;
    }}
    input:focus {{
      outline: none;
      border-color: #0077b6;
    }}
    button {{
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #0077b6, #00a0a8);
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
    .error {{
      background: #fef3f2;
      border: 1px solid #fecdca;
      color: #cc404a;
      padding: 12px;
      border-radius: 8px;
      margin-bottom: 20px;
      font-size: 14px;
    }}
    .footer {{
      text-align: center;
      margin-top: 24px;
      color: #66778a;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="login-card">
    <div class="brand">
      <div class="brand-mark">HR</div>
      <h1>Therapist Dashboard</h1>
      <p class="subtitle">AI Hand Rehabilitation System</p>
    </div>
    {"<div class='error'>" + error + "</div>" if error else ""}
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
    <div class="footer">
      <p>Secure access for authorized therapists only</p>
    </div>
  </div>
</body>
</html>"""


# Add to DashboardRepository class:
def verify_therapist(self, username: str, password: str) -> bool:
    """Verify therapist credentials"""
    rows = self.query(
        "SELECT password_hash FROM therapists WHERE username = ?", 
        (username,)
    )
    if not rows:
        return False
    stored_hash = rows[0]["password_hash"]
    return verify_password(stored_hash, password)


# Modify DashboardHandler class to add authentication:
def get_cookie(self, name: str) -> str:
    """Extract cookie value"""
    cookies = self.headers.get("Cookie", "")
    for cookie in cookies.split(";"):
        cookie = cookie.strip()
        if cookie.startswith(name + "="):
            return cookie[len(name)+1:]
    return ""


def require_auth(self) -> Optional[str]:
    """Check if request is authenticated, return username or None"""
    token = self.get_cookie("session_token")
    return get_session(token)


def send_redirect(self, location: str, set_cookie: str = "") -> None:
    """Send redirect response with optional cookie"""
    self.send_response(302)
    self.send_header("Location", location)
    if set_cookie:
        self.send_header("Set-Cookie", set_cookie)
    self.end_headers()
