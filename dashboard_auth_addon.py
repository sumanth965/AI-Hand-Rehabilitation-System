"""
Authentication addon for therapist_dashboard.py using bcrypt and security_utils.
"""

import bcrypt
import security_utils
from datetime import datetime, timedelta
from typing import Optional

# Session storage (in-memory for local dashboard)
SESSIONS: dict[str, tuple[str, datetime]] = {}
SESSION_DURATION = timedelta(hours=8)

def hash_password(password: str) -> str:
    """BCrypt hash with strength checks."""
    valid, err = security_utils.validate_password_strength(password)
    if not valid:
        raise ValueError(err)
    return security_utils.hash_password(password)

def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a password against the stored bcrypt hash."""
    return security_utils.verify_password(stored_hash, password)

def create_session(username: str) -> str:
    """Create a new session token."""
    import secrets
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (username, datetime.now() + SESSION_DURATION)
    return token

def get_session(token: str) -> Optional[str]:
    """Get username from session token."""
    if token not in SESSIONS:
        return None
    username, expires = SESSIONS[token]
    if datetime.now() > expires:
        del SESSIONS[token]
        return None
    # Extend session
    SESSIONS[token] = (username, datetime.now() + SESSION_DURATION)
    return username

def clear_session(token: str) -> None:
    """Clear session token."""
    if token in SESSIONS:
        del SESSIONS[token]
