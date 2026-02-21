"""
Per-service settings management.
Settings stored in {service_dir}/settings.json.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from app.service_context import get_active_service_dir

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "general": {
        "department_name": "",
        "timezone": "America/Edmonton",
        "platoon_labels": ["A", "B", "C", "D"],
    },
    "metrics": {
        "target_compression_rate_min": 100,
        "target_compression_rate_max": 120,
        "target_compression_depth_min": 5.0,
        "target_compression_depth_max": 6.0,
        "target_ccf": 80.0,
        "target_depth_compliance": 80.0,
        "target_rate_compliance": 80.0,
    },
    "export": {
        "default_format": "xlsx",
        "include_headers": True,
        "date_format": "YYYY-MM-DD",
    },
}


def _get_settings_path() -> Optional[Path]:
    """Get path to settings.json for the active service."""
    service_dir = get_active_service_dir()
    if not service_dir:
        return None
    return service_dir / "settings.json"


def load_settings() -> dict:
    """Load settings for the active service. Returns defaults if none saved."""
    path = _get_settings_path()
    if not path or not path.exists():
        return dict(DEFAULT_SETTINGS)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Merge with defaults so new keys are always present
        merged = dict(DEFAULT_SETTINGS)
        for section_key, section_defaults in DEFAULT_SETTINGS.items():
            if section_key in data:
                if isinstance(section_defaults, dict):
                    merged[section_key] = {**section_defaults, **data[section_key]}
                else:
                    merged[section_key] = data[section_key]
        return merged
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load settings: {e}")
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> bool:
    """Save settings for the active service."""
    path = _get_settings_path()
    if not path:
        return False

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return True
    except IOError as e:
        logger.error(f"Failed to save settings: {e}")
        return False


def update_section(section: str, values: dict) -> bool:
    """Update a specific section of settings. Only allows known sections and keys."""
    # Whitelist: only accept known sections
    if section not in DEFAULT_SETTINGS:
        logger.warning(f"Rejected unknown settings section: {section}")
        return False

    # Only accept keys that exist in the defaults for this section
    allowed_keys = set(DEFAULT_SETTINGS[section].keys()) if isinstance(DEFAULT_SETTINGS[section], dict) else set()
    filtered = {k: v for k, v in values.items() if k in allowed_keys}

    settings = load_settings()
    if section not in settings:
        settings[section] = {}
    settings[section].update(filtered)
    return save_settings(settings)
