"""
Auto-sync service — pulls on login, pushes after data changes.
Uses GitHub encrypted backups as the sync transport layer.
"""
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 5

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

@dataclass
class SyncState:
    enabled: bool = False
    last_push_time: Optional[str] = None
    last_pull_time: Optional[str] = None
    push_in_progress: bool = False
    pull_in_progress: bool = False
    last_error: Optional[str] = None


_state = SyncState()
_service_dir: Optional[Path] = None
_push_timer: Optional[threading.Timer] = None
_push_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_sync_state() -> dict:
    """Return current sync state for the status API."""
    return {
        "enabled": _state.enabled,
        "last_push_time": _state.last_push_time,
        "last_pull_time": _state.last_pull_time,
        "push_in_progress": _state.push_in_progress,
        "pull_in_progress": _state.pull_in_progress,
        "last_error": _state.last_error,
    }


def initialize_for_service(service_dir: Path) -> None:
    """Check if backup is configured and enable sync if so."""
    global _service_dir, _state
    _service_dir = service_dir
    _state = SyncState()

    from app.services.backup_service import get_stored_token, load_backup_config
    token = get_stored_token(service_dir)
    config = load_backup_config(service_dir)

    if token and config.get("repo_owner") and config.get("repo_name"):
        _state.enabled = True
        logger.info("Sync enabled for %s", service_dir.name)
    else:
        logger.info("Sync not configured for %s", service_dir.name)


def auto_pull(service_dir: Path) -> dict:
    """Pull the newest backup from GitHub, overwriting local JSON.
    Runs synchronously during login (before data loads).
    Returns {"pulled": True/False, ...}.
    """
    if not _state.enabled:
        return {"pulled": False, "reason": "sync not enabled"}

    from app.services.backup_service import get_stored_token, list_backups, restore

    token = get_stored_token(service_dir)
    if not token:
        return {"pulled": False, "reason": "no token"}

    _state.pull_in_progress = True
    _state.last_error = None

    try:
        result = list_backups(service_dir, token)
        if not result.get("success") or not result.get("backups"):
            _state.pull_in_progress = False
            return {"pulled": False, "reason": "no backups found"}

        newest = result["backups"][0]  # already sorted newest-first
        restore_result = restore(service_dir, token, newest["path"])

        if restore_result.get("success"):
            _state.last_pull_time = datetime.now(timezone.utc).isoformat()
            logger.info("Auto-pull restored %s", newest["path"])
            return {"pulled": True, "backup": newest["name"]}
        else:
            _state.last_error = restore_result.get("error", "restore failed")
            logger.warning("Auto-pull restore failed: %s", _state.last_error)
            return {"pulled": False, "reason": _state.last_error}
    except Exception as e:
        _state.last_error = str(e)
        logger.exception("Auto-pull error")
        return {"pulled": False, "reason": str(e)}
    finally:
        _state.pull_in_progress = False


def schedule_push() -> None:
    """Schedule a debounced push. Resets the timer on each call."""
    global _push_timer

    if not _state.enabled:
        return

    with _push_lock:
        if _push_timer is not None:
            _push_timer.cancel()
        _push_timer = threading.Timer(DEBOUNCE_SECONDS, _execute_push)
        _push_timer.daemon = True
        _push_timer.start()


def reset() -> None:
    """Cancel pending timers and clear state (called on logout)."""
    global _push_timer, _service_dir, _state

    with _push_lock:
        if _push_timer is not None:
            _push_timer.cancel()
            _push_timer = None

    _service_dir = None
    _state = SyncState()
    logger.info("Sync state reset")


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _execute_push() -> None:
    """Run backup_now in the timer's background thread."""
    global _push_timer

    if not _state.enabled or _service_dir is None:
        return

    from app.services.backup_service import get_stored_token, backup_now

    token = get_stored_token(_service_dir)
    if not token:
        _state.last_error = "no token for push"
        return

    _state.push_in_progress = True
    _state.last_error = None

    try:
        result = backup_now(_service_dir, token)
        if result.get("success"):
            _state.last_push_time = datetime.now(timezone.utc).isoformat()
            logger.info("Auto-push succeeded: %s", result.get("path"))
        else:
            _state.last_error = result.get("error", "push failed")
            logger.warning("Auto-push failed: %s", _state.last_error)
    except Exception as e:
        _state.last_error = str(e)
        logger.exception("Auto-push error")
    finally:
        _state.push_in_progress = False
        with _push_lock:
            _push_timer = None
