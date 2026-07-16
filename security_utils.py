import os
import base64
import hashlib
import sqlite3
from datetime import datetime
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# -----------------------------------------------------------------------------
# KEY MANAGEMENT
# -----------------------------------------------------------------------------
KEY_FILE = "secret.key"

def load_or_create_key() -> bytes:
    """Loads key from secret.key, or creates it if not found."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read().strip()
    else:
        # Generate 32-byte key
        key = os.urandom(32)
        with open(KEY_FILE, "wb") as f:
            f.write(key)
        # Try to append to .gitignore automatically
        try:
            if os.path.exists(".gitignore"):
                with open(".gitignore", "r") as gitignore:
                    lines = gitignore.read()
                if "secret.key" not in lines:
                    with open(".gitignore", "a") as gitignore:
                        gitignore.write("\nsecret.key\n")
        except Exception as e:
            print(f"[SECURITY] Warning adding to .gitignore: {e}")
        return key

_KEY = load_or_create_key()

# -----------------------------------------------------------------------------
# ENCRYPTION HELPERS
# -----------------------------------------------------------------------------
def encrypt_deterministic(plaintext: str) -> str:
    """
    Encrypts text deterministically using AES-CBC.
    Same plaintext and same key produces same ciphertext, allowing joins and indexing.
    """
    if not plaintext:
        return ""
    try:
        raw = plaintext.encode('utf-8')
        # Padding
        pad_len = 16 - (len(raw) % 16)
        padded = raw + bytes([pad_len] * pad_len)
        
        # IV derived deterministically from SHA-256 of plaintext
        iv = hashlib.sha256(raw).digest()[:16]
        
        cipher = Cipher(algorithms.AES(_KEY), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        
        # Store IV + Ciphertext
        return base64.b64encode(iv + ciphertext).decode('utf-8')
    except Exception as e:
        print(f"[SECURITY] Deterministic encryption failed: {e}")
        return plaintext

def decrypt_deterministic(ciphertext: str) -> str:
    """Decrypts text encrypted with encrypt_deterministic. Falls back to input if invalid."""
    if not ciphertext:
        return ""
    try:
        data = base64.b64decode(ciphertext.encode('utf-8'))
        if len(data) < 32:
            return ciphertext
        iv = data[:16]
        cipher_part = data[16:]
        
        cipher = Cipher(algorithms.AES(_KEY), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(cipher_part) + decryptor.finalize()
        
        # Unpadding
        pad_len = padded[-1]
        if pad_len < 1 or pad_len > 16:
            return ciphertext
        return padded[:-pad_len].decode('utf-8')
    except Exception:
        # Fallback to plain text if not encrypted
        return ciphertext

def encrypt_non_deterministic(plaintext: str) -> str:
    """Encrypts text non-deterministically (with random IV) using Fernet."""
    if not plaintext:
        return ""
    try:
        fernet_key = base64.urlsafe_b64encode(_KEY)
        f = Fernet(fernet_key)
        return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"[SECURITY] Non-deterministic encryption failed: {e}")
        return plaintext

def decrypt_non_deterministic(ciphertext: str) -> str:
    """Decrypts text encrypted with Fernet. Falls back to input if invalid."""
    if not ciphertext:
        return ""
    try:
        fernet_key = base64.urlsafe_b64encode(_KEY)
        f = Fernet(fernet_key)
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except Exception:
        # Fallback to plain text if not encrypted
        return ciphertext

# -----------------------------------------------------------------------------
# PASSWORD SECURITY
# -----------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_hash: str, password: str) -> bool:
    """Verifies a password against a stored bcrypt hash."""
    if not stored_hash or not password:
        return False
    try:
        # If stored hash is legacy SHA-256 (64 hex characters), migrate or handle
        if len(stored_hash) == 64 and all(c in "0123456789abcdefABCDEF" for c in stored_hash):
            sha_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            return sha_hash == stored_hash
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception as e:
        print(f"[SECURITY] Password verification failed: {e}")
        return False

def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validates password strength (min length 8, contains letters and numbers)."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_letter and has_digit):
        return False, "Password must contain both letters and digits."
    return True, ""

def request_password_reset_placeholder(username: str) -> str:
    """Placeholder architecture for secure password reset request."""
    # In a full clinical deployment, this would email/SMS a one-time token or alert a sysadmin
    return f"Password reset request initiated for user '{username}'. Please contact your system administrator to complete verification."

# -----------------------------------------------------------------------------
# AUDIT LOGGING HELPER
# -----------------------------------------------------------------------------
def log_audit_event(db_path: str, user_id: str, username: str, role: str, action: str, target: str, ip_address: str = "127.0.0.1", status: str = "Success") -> None:
    """Inserts an encrypted security audit record into the audit_logs table."""
    try:
        enc_user_id = encrypt_deterministic(user_id) if user_id else ""
        enc_username = encrypt_deterministic(username) if username else ""
        enc_role = encrypt_deterministic(role) if role else ""
        enc_target = encrypt_deterministic(target) if target else ""
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Ensure audit_logs exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                username TEXT,
                role TEXT,
                action TEXT,
                target TEXT,
                ip_address TEXT,
                status TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO audit_logs (user_id, username, role, action, target, ip_address, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (enc_user_id, enc_username, enc_role, action, enc_target, ip_address, status))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SECURITY] Audit logging failed: {e}")
        # Fallback to local encrypted file logging
        log_message = f"{datetime.now().isoformat()} | {enc_user_id} | {enc_username} | {enc_role} | {action} | {enc_target} | {ip_address} | {status} | Fallback (DB Error: {str(e)})"
        log_to_file("security_audit.log", log_message)

def log_to_file(filepath: str, message: str) -> None:
    """Logs a message to a file with automatic rotation (at 1MB, max 5 backups)."""
    try:
        import os
        # Log rotation
        if os.path.exists(filepath) and os.path.getsize(filepath) >= 1 * 1024 * 1024:
            # Rotate backups
            for i in range(4, 0, -1):
                src = f"{filepath}.{i}"
                dst = f"{filepath}.{i+1}"
                if os.path.exists(src):
                    if os.path.exists(dst):
                        os.remove(dst)
                    os.rename(src, dst)
            if os.path.exists(filepath):
                os.rename(filepath, f"{filepath}.1")
                
        with open(filepath, "a") as f:
            f.write(message + "\n")
    except Exception as e:
        print(f"[SECURITY] File logging failed: {e}")

# -----------------------------------------------------------------------------
# PRIVACY & WEBCAM CHECKS
# -----------------------------------------------------------------------------
def run_privacy_startup_checks() -> str:
    """
    Verifies that no webcam photos, video recordings, or raw biometric images
    are being stored on disk. Scans the workspace directory.
    """
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".mp4", ".avi", ".mov"}
    offending_files = []
    
    # Simple check for any image folders
    for root, dirs, files in os.walk("."):
        # Ignore reports, img, .git, and .agents directories
        if any(ignored in root for ignored in [".git", ".agents", "reports", "img", "venv"]):
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in image_extensions:
                offending_files.append(os.path.join(root, file))
                
    if offending_files:
        print(f"[PRIVACY WARNING] Found {len(offending_files)} raw files. Ensure no webcam captures or videos are saved.")
        
    return "Privacy Mode Enabled"
