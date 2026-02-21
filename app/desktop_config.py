"""
Desktop configuration for PyInstaller and per-service data isolation.
Handles path resolution for both development and frozen (packaged) modes.
"""
import os
import re
import sys
import json
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False)


def get_bundle_dir() -> Path:
    """Get the directory containing bundled assets (templates, static, schemas).
    In frozen mode: sys._MEIPASS (temp extraction dir)
    In dev mode: project root
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_appdata_dir() -> Path:
    """Get the base application data directory: %APPDATA%/CPR-Tracker/"""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        # Fallback for non-Windows or missing APPDATA
        appdata = str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "CPR-Tracker"


def get_service_dir(service_slug: str) -> Path:
    """Get the data directory for a specific service."""
    return get_appdata_dir() / service_slug


def get_global_config_path() -> Path:
    """Get path to the global config.json."""
    return get_appdata_dir() / "config.json"


def load_global_config() -> dict:
    """Load global config (services list, last used service, etc.)."""
    config_path = get_global_config_path()
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {"services": [], "last_service": None, "window_state": {}}


def save_global_config(config: dict) -> None:
    """Save global config."""
    config_path = get_global_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def slugify(service_name: str) -> str:
    """Convert service name to filesystem-safe slug.
    Only permits lowercase alphanumeric characters and hyphens.
    """
    slug = service_name.lower().strip().replace(" ", "-")
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or "default"


def ensure_appdata_dir() -> None:
    """Ensure the base AppData directory exists."""
    get_appdata_dir().mkdir(parents=True, exist_ok=True)
