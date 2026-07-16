import os
import sqlite3
import security_utils
from therapist_dashboard import DashboardRepository
from zero_keyboard_physio import DatabaseManager

def test_password_security():
    print("--- Testing Password Security ---")
    password = "MySecurePassword123!"
    
    # 1. Hashing
    hashed = security_utils.hash_password(password)
    print(f"Hashed: {hashed}")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$"), "Password must be bcrypt hashed"
    
    # 2. Verification
    assert security_utils.verify_password(hashed, password), "Password verification failed"
    assert not security_utils.verify_password(hashed, "wrong_password"), "Should fail with wrong password"
    
    # 3. Validation
    valid, msg = security_utils.validate_password_strength(password)
    assert valid, f"Password should be valid: {msg}"
    valid, msg = security_utils.validate_password_strength("weak")
    assert not valid, f"Should fail weak password"
    print("Password Security tests passed!")

def test_encryption():
    print("\n--- Testing Field Encryption ---")
    plain_text = "John Doe"
    
    # 1. Deterministic
    enc_det1 = security_utils.encrypt_deterministic(plain_text)
    enc_det2 = security_utils.encrypt_deterministic(plain_text)
    print(f"Det 1: {enc_det1}")
    print(f"Det 2: {enc_det2}")
    assert enc_det1 == enc_det2, "Deterministic encryption must return same cipher for same text"
    
    dec_det = security_utils.decrypt_deterministic(enc_det1)
    assert dec_det == plain_text, "Deterministic decryption failed"
    
    # 2. Non-deterministic
    enc_ndet1 = security_utils.encrypt_non_deterministic(plain_text)
    enc_ndet2 = security_utils.encrypt_non_deterministic(plain_text)
    print(f"Non-Det 1: {enc_ndet1}")
    print(f"Non-Det 2: {enc_ndet2}")
    assert enc_ndet1 != enc_ndet2, "Non-deterministic encryption must return different ciphers"
    
    dec_ndet = security_utils.decrypt_non_deterministic(enc_ndet1)
    assert dec_ndet == plain_text, "Non-deterministic decryption failed"
    print("Encryption tests passed!")

def test_audit_logs():
    print("\n--- Testing Audit Logging ---")
    db_path = "test_rehab.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    # Log an event
    security_utils.log_audit_event(
        db_path,
        user_id="therapist_1",
        username="alice",
        role="Therapist",
        action="VIEW_REPORT",
        target="Patient_JohnDoe",
        status="Success"
    )
    
    # Check that it exists in db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, action, target FROM audit_logs")
    row = cursor.fetchone()
    assert row is not None, "Audit log not inserted"
    assert row[0] == security_utils.encrypt_deterministic("therapist_1"), "user_id should be encrypted"
    assert row[1] == "VIEW_REPORT", "action should be plaintext"
    assert row[2] == security_utils.encrypt_deterministic("Patient_JohnDoe"), "target should be encrypted"
    conn.close()
    
    # Test file log rotation
    print("Testing file log rotation...")
    log_file = "test_audit.log"
    if os.path.exists(log_file):
        os.remove(log_file)
    for i in range(100):
        security_utils.log_to_file(log_file, f"Event {i}")
    assert os.path.exists(log_file), "File log not created"
    
    # Clean up
    if os.path.exists(db_path):
        os.remove(db_path)
    if os.path.exists(log_file):
        os.remove(log_file)
    print("Audit Logging tests passed!")

def test_database_manager():
    print("\n--- Testing Database Manager Integration ---")
    db_path = "test_rehab.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = DatabaseManager(db_path)
    db.save_patient("Jane Doe", 45, "Adult", id_number="ID12345")
    
    # Query database directly to see if fields are encrypted
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, id_number FROM patients")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] != "Jane Doe", "Name must be encrypted in db"
    assert row[1] != "ID12345", "ID must be encrypted in db"
    print("Verified database storage is encrypted!")
    
    # Retrieve using database manager and verify decryption
    pat = db.get_patient("Jane Doe")
    assert pat is not None
    assert pat['age'] == 45
    
    pat_by_id = db.get_patient_by_id("ID12345")
    assert pat_by_id is not None
    assert pat_by_id['name'] == "Jane Doe"
    
    all_pat = db.get_all_patients()
    assert len(all_pat) == 1
    assert all_pat[0]['name'] == "Jane Doe"
    assert all_pat[0]['id_number'] == "ID12345"
    
    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)
    print("Database Manager Integration tests passed!")

if __name__ == "__main__":
    test_password_security()
    test_encryption()
    test_audit_logs()
    test_database_manager()
    print("\nALL SECURITY TESTS PASSED SUCCESSFULLY!")
