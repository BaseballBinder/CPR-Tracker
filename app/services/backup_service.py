"""
GitHub encrypted backup service.
Encrypts service data and pushes to a private GitHub repository.
"""
import json
import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _derive_key(passphrase: str) -> bytes:
    """Derive a Fernet key from a passphrase (deterministic)."""
    import hashlib
    digest = hashlib.sha256(passphrase.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _get_machine_key() -> str:
    """Get a machine-specific key for encrypting tokens at rest.
    Uses OS username + hostname + a fixed salt so the key is tied to
    this machine/user but doesn't require the secret being protected.
    """
    import getpass
    import platform
    material = f"cpr-tracker:{getpass.getuser()}@{platform.node()}:token-encryption"
    return material


def _encrypt(data: bytes, token: str) -> bytes:
    """Encrypt data using Fernet with key derived from token."""
    f = Fernet(_derive_key(token))
    return f.encrypt(data)


def _decrypt(data: bytes, token: str) -> bytes:
    """Decrypt data using Fernet with key derived from token."""
    f = Fernet(_derive_key(token))
    return f.decrypt(data)


def load_backup_config(service_dir: Path) -> dict:
    """Load backup configuration for a service."""
    config_file = service_dir / "backup_config.json"
    if not config_file.exists():
        return {}
    try:
        return json.loads(config_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def save_backup_config(service_dir: Path, config: dict) -> None:
    """Save backup configuration for a service."""
    config_file = service_dir / "backup_config.json"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _encrypt_token(token: str) -> str:
    """Encrypt a GitHub token using a machine-specific key."""
    return _encrypt(token.encode("utf-8"), _get_machine_key()).decode("utf-8")


def _decrypt_token(encrypted_token: str) -> str:
    """Decrypt a GitHub token using a machine-specific key."""
    return _decrypt(encrypted_token.encode("utf-8"), _get_machine_key()).decode("utf-8")


def configure(service_dir: Path, github_token: str, repo_owner: str, repo_name: str) -> dict:
    """Configure GitHub backup for a service.
    Encrypts and stores the GitHub token using a machine-specific key.
    """
    encrypted_token = _encrypt_token(github_token)

    config = {
        "encrypted_token": encrypted_token,
        "repo_owner": repo_owner,
        "repo_name": repo_name,
        "configured_at": datetime.now(timezone.utc).isoformat(),
    }
    save_backup_config(service_dir, config)

    # Verify the token works
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    try:
        resp = requests.get(f"{GITHUB_API}/repos/{repo_owner}/{repo_name}", headers=headers, timeout=10)
        if resp.status_code == 200:
            config["verified"] = True
        else:
            config["verified"] = False
            config["error"] = f"GitHub API returned {resp.status_code}"
    except requests.RequestException as e:
        config["verified"] = False
        config["error"] = str(e)

    save_backup_config(service_dir, config)
    return config


def _get_github_headers(token: str) -> dict:
    """Get GitHub API headers."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def backup_now(service_dir: Path, github_token: str) -> dict:
    """Create an encrypted backup and push to GitHub.
    Returns dict with status information.
    """
    config = load_backup_config(service_dir)
    if not config.get("repo_owner") or not config.get("repo_name"):
        return {"success": False, "error": "Backup not configured"}

    repo_owner = config["repo_owner"]
    repo_name = config["repo_name"]
    headers = _get_github_headers(github_token)

    # Collect data to backup
    data_dir = service_dir / "data"
    backup_data = {}

    for filename in ["sessions.json", "providers.json"]:
        filepath = data_dir / filename
        if filepath.exists():
            try:
                backup_data[filename] = json.loads(filepath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                backup_data[filename] = {}

    # Add metadata
    backup_data["_metadata"] = {
        "backed_up_at": datetime.now(timezone.utc).isoformat(),
        "service_dir": service_dir.name,
    }

    # Encrypt
    raw = json.dumps(backup_data, indent=2).encode("utf-8")
    encrypted = _encrypt(raw, github_token)
    content_b64 = base64.b64encode(encrypted).decode("utf-8")

    # Build path in repo
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = f"backups/{service_dir.name}/{timestamp}.enc"

    # Check if file exists (for update vs create)
    url = f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/contents/{path}"

    try:
        put_data = {
            "message": f"Backup {service_dir.name} - {timestamp}",
            "content": content_b64,
        }
        resp = requests.put(url, headers=headers, json=put_data, timeout=30)

        if resp.status_code in (200, 201):
            return {
                "success": True,
                "path": path,
                "timestamp": timestamp,
                "size": len(raw),
            }
        else:
            return {
                "success": False,
                "error": f"GitHub API returned {resp.status_code}: {resp.text[:200]}",
            }
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}


def list_backups(service_dir: Path, github_token: str) -> dict:
    """List available backups from GitHub."""
    config = load_backup_config(service_dir)
    if not config.get("repo_owner") or not config.get("repo_name"):
        return {"success": False, "error": "Backup not configured", "backups": []}

    repo_owner = config["repo_owner"]
    repo_name = config["repo_name"]
    headers = _get_github_headers(github_token)
    path = f"backups/{service_dir.name}"

    url = f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/contents/{path}"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            files = resp.json()
            backups = []
            for f in files:
                if f["name"].endswith(".enc"):
                    backups.append({
                        "name": f["name"],
                        "path": f["path"],
                        "size": f["size"],
                        "sha": f["sha"],
                    })
            backups.sort(key=lambda x: x["name"], reverse=True)
            return {"success": True, "backups": backups}
        elif resp.status_code == 404:
            return {"success": True, "backups": []}
        else:
            return {"success": False, "error": f"GitHub API returned {resp.status_code}", "backups": []}
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "backups": []}


def restore(service_dir: Path, github_token: str, backup_path: str) -> dict:
    """Download and decrypt a backup, replacing local data."""
    import re as _re
    # Validate backup_path format to prevent path traversal
    if not _re.match(r'^backups/[a-z0-9-]+/[0-9T-]+\.enc$', backup_path):
        return {"success": False, "error": "Invalid backup path format"}

    config = load_backup_config(service_dir)
    if not config.get("repo_owner") or not config.get("repo_name"):
        return {"success": False, "error": "Backup not configured"}

    repo_owner = config["repo_owner"]
    repo_name = config["repo_name"]
    headers = _get_github_headers(github_token)

    url = f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/contents/{backup_path}"

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return {"success": False, "error": f"GitHub API returned {resp.status_code}"}

        file_data = resp.json()
        encrypted = base64.b64decode(file_data["content"])
        decrypted = _decrypt(encrypted, github_token)
        backup_data = json.loads(decrypted)

        # Restore data files
        data_dir = service_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        for filename in ["sessions.json", "providers.json"]:
            if filename in backup_data:
                (data_dir / filename).write_text(
                    json.dumps(backup_data[filename], indent=2),
                    encoding="utf-8"
                )

        return {
            "success": True,
            "restored_files": [f for f in ["sessions.json", "providers.json"] if f in backup_data],
            "metadata": backup_data.get("_metadata", {}),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_config_display(service_dir: Path) -> dict:
    """Get backup config for display (with masked token)."""
    config = load_backup_config(service_dir)
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "repo_owner": config.get("repo_owner", ""),
        "repo_name": config.get("repo_name", ""),
        "configured_at": config.get("configured_at", ""),
        "verified": config.get("verified", False),
    }
