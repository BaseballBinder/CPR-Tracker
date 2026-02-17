"""
Simple per-service password authentication using PBKDF2-SHA256.
No external dependencies beyond stdlib.
"""
import hashlib
import secrets
import json
from pathlib import Path


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-SHA256 with random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000)
    return f"{salt}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, key_hex = stored_hash.split(':', 1)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000)
        return key.hex() == key_hex
    except (ValueError, AttributeError):
        return False


def get_password_hash(service_dir: Path) -> str | None:
    """Read the stored password hash for a service."""
    auth_file = service_dir / "auth.json"
    if not auth_file.exists():
        return None
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        return data.get("password_hash")
    except (json.JSONDecodeError, IOError):
        return None


def check_password(service_dir: Path, password: str) -> bool:
    """Check if a password is correct for a service."""
    stored_hash = get_password_hash(service_dir)
    if stored_hash is None:
        return False
    return verify_password(password, stored_hash)
