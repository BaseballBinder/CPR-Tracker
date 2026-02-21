"""
Simple JSON file-based persistence for sessions and providers.
Saves data to JSON files on disk so they survive server restarts.
Supports per-service data isolation via service_context.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from app.desktop_config import get_bundle_dir


def _get_data_dir() -> Path:
    """Get the data directory for the active service, or project root fallback."""
    from app.service_context import get_active_service_dir
    service_dir = get_active_service_dir()
    if service_dir:
        return service_dir / "data"
    # Fallback to project-root data dir (dev mode, no service selected)
    return get_bundle_dir() / "data"


def _get_sessions_file() -> Path:
    return _get_data_dir() / "sessions.json"


def _get_providers_file() -> Path:
    return _get_data_dir() / "providers.json"


def _ensure_data_dir():
    """Ensure data directory exists."""
    _get_data_dir().mkdir(parents=True, exist_ok=True)


def load_sessions() -> List[Dict[str, Any]]:
    """Load sessions from JSON file."""
    _ensure_data_dir()
    sessions_file = _get_sessions_file()

    if not sessions_file.exists():
        return []

    try:
        with open(sessions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("sessions", [])
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load sessions file: {e}")
        return []


def save_sessions(sessions: List[Dict[str, Any]]) -> bool:
    """Save sessions to JSON file."""
    _ensure_data_dir()

    try:
        data = {
            "sessions": sessions,
            "last_updated": datetime.now().isoformat()
        }
        with open(_get_sessions_file(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except IOError as e:
        logger.error(f"Error saving sessions: {e}")
        return False


def add_session(session: Dict[str, Any], sessions_list: List[Dict[str, Any]]) -> bool:
    """Add a session and persist to disk."""
    sessions_list.append(session)
    return save_sessions(sessions_list)


def update_session_in_list(session_id: str, updates: Dict[str, Any], sessions_list: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Update a session in the list and persist to disk."""
    for session in sessions_list:
        if session.get("id") == session_id:
            session.update(updates)
            session["updated_at"] = datetime.now().isoformat()
            save_sessions(sessions_list)
            return session
    return None


def delete_session(session_id: str, sessions_list: List[Dict[str, Any]]) -> bool:
    """Delete a session and persist to disk."""
    original_len = len(sessions_list)
    sessions_list[:] = [s for s in sessions_list if s.get("id") != session_id]
    if len(sessions_list) < original_len:
        return save_sessions(sessions_list)
    return False


# ============================================================================
# Provider Persistence
# ============================================================================

def load_providers() -> List[Dict[str, Any]]:
    """Load user-added providers from JSON file."""
    _ensure_data_dir()
    providers_file = _get_providers_file()

    if not providers_file.exists():
        return []

    try:
        with open(providers_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("providers", [])
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load providers file: {e}")
        return []


def save_providers(providers: List[Dict[str, Any]]) -> bool:
    """Save user-added providers to JSON file."""
    _ensure_data_dir()

    try:
        data = {
            "providers": providers,
            "last_updated": datetime.now().isoformat()
        }
        with open(_get_providers_file(), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except IOError as e:
        logger.error(f"Error saving providers: {e}")
        return False


def add_provider_to_file(provider: Dict[str, Any]) -> bool:
    """Add a provider and persist to disk."""
    providers = load_providers()
    providers.append(provider)
    return save_providers(providers)


def delete_provider_from_file(provider_id: str) -> bool:
    """Delete a provider from the persisted file."""
    providers = load_providers()
    original_len = len(providers)
    providers = [p for p in providers if p.get("id") != provider_id]
    if len(providers) < original_len:
        return save_providers(providers)
    return False
