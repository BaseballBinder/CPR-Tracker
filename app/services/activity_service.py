"""
Activity tracking for per-service usage logging.
Each service gets an activity.json file in its data directory.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.desktop_config import get_service_dir as _get_service_dir

logger = logging.getLogger(__name__)

MAX_ACTIVITY_ENTRIES = 5000


def _get_activity_file(service_slug: str) -> Path:
    return _get_service_dir(service_slug) / "activity.json"


def _load_activity(service_slug: str) -> List[Dict]:
    f = _get_activity_file(service_slug)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_activity(service_slug: str, entries: List[Dict]) -> None:
    if len(entries) > MAX_ACTIVITY_ENTRIES:
        entries = entries[-MAX_ACTIVITY_ENTRIES:]
    f = _get_activity_file(service_slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def log_activity(service_slug: str, event_type: str, detail: Optional[Dict[str, Any]] = None) -> None:
    entries = _load_activity(service_slug)
    entries.append({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    })
    _save_activity(service_slug, entries)


def get_activity_log(service_slug: str, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
    entries = _load_activity(service_slug)
    if event_type:
        entries = [e for e in entries if e.get("type") == event_type]
    return list(reversed(entries[-limit:]))


def get_last_active(service_slug: str) -> Optional[str]:
    entries = _load_activity(service_slug)
    if not entries:
        return None
    return entries[-1].get("timestamp")
