"""
Active service context management.
Tracks which fire service is currently selected and manages data reloading.
"""
import json
import shutil
import logging
from pathlib import Path
from typing import Optional

from app.desktop_config import (
    get_service_dir, get_bundle_dir, get_appdata_dir,
    load_global_config, save_global_config, slugify
)

logger = logging.getLogger(__name__)

_active_service_slug: Optional[str] = None
_active_service_name: Optional[str] = None


def get_active_service() -> Optional[str]:
    """Get the active service slug."""
    return _active_service_slug


def get_active_service_name() -> Optional[str]:
    """Get the active service display name."""
    return _active_service_name


def get_active_service_dir() -> Optional[Path]:
    """Get the active service's data directory."""
    if not _active_service_slug:
        return None
    return get_service_dir(_active_service_slug)


def set_active_service(slug: str, name: Optional[str] = None) -> None:
    """Set the active service and reinitialize data paths."""
    global _active_service_slug, _active_service_name
    _active_service_slug = slug
    _active_service_name = name or slug

    # Update last_service in global config
    config = load_global_config()
    config["last_service"] = slug
    save_global_config(config)

    # Clear ALL cached state so paths and data update for the new service
    _clear_all_caches()

    # Reinitialize in-memory data from the new service's directory
    _reinitialize_data()

    logger.info(f"Active service set to: {slug}")

    try:
        from app.services.activity_service import log_activity
        log_activity(slug, "login")
    except Exception:
        logger.debug("Failed to log login activity", exc_info=True)


def clear_active_service() -> None:
    """Clear the active service (logout)."""
    global _active_service_slug, _active_service_name
    _active_service_slug = None
    _active_service_name = None

    # Clear all cached state
    _clear_all_caches()

    logger.info("Active service cleared (logged out)")


def _clear_all_caches() -> None:
    """Clear all cached settings and service singletons.

    When the active service changes, every singleton that cached paths or data
    from the previous service must be reset so it gets recreated with the
    new service's paths on next access.
    """
    # Clear LRU-cached Settings
    from app.config import get_settings
    get_settings.cache_clear()

    # Reset service singletons so they recreate with fresh paths
    import app.services.export_service as _es
    import app.services.schema_service as _ss
    import app.services.ingestion_service as _ig
    import app.services.wizard_service as _ws

    _es._export_service = None
    _ss._schema_service = None
    _ig._ingestion_service = None
    _ws._wizard_service = None


def _reinitialize_data() -> None:
    """Reload all in-memory data from the active service's directory."""
    from app import mock_data
    mock_data.reinitialize()

    # Backfill JcLS scores for any real-call sessions missing them
    from app.services.jcls_service import backfill_jcls_scores
    backfill_jcls_scores()


def create_service(service_name: str, password_hash: str) -> str:
    """Create a new service with its directory structure and initial data.
    Returns the service slug.
    """
    slug = slugify(service_name)
    service_dir = get_service_dir(slug)
    bundle_dir = get_bundle_dir()

    # Create directory structure
    (service_dir / "data" / "schemas").mkdir(parents=True, exist_ok=True)
    (service_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (service_dir / "exports").mkdir(parents=True, exist_ok=True)
    (service_dir / "templates_canroc").mkdir(parents=True, exist_ok=True)

    # Copy schemas from bundle
    bundle_schemas = bundle_dir / "data" / "schemas"
    if bundle_schemas.exists():
        for schema_file in bundle_schemas.glob("*.json"):
            shutil.copy2(schema_file, service_dir / "data" / "schemas" / schema_file.name)

    # Copy CanROC templates from bundle
    bundle_templates = bundle_dir / "templates_canroc"
    if bundle_templates.exists():
        for template_file in bundle_templates.glob("*.xlsx"):
            shutil.copy2(template_file, service_dir / "templates_canroc" / template_file.name)

    # Create empty data files
    (service_dir / "data" / "sessions.json").write_text(
        json.dumps({"sessions": [], "last_updated": ""}, indent=2),
        encoding="utf-8"
    )
    (service_dir / "data" / "providers.json").write_text(
        json.dumps({"providers": [], "last_updated": ""}, indent=2),
        encoding="utf-8"
    )

    # Store password hash
    (service_dir / "auth.json").write_text(
        json.dumps({"password_hash": password_hash}),
        encoding="utf-8"
    )

    # Update global config
    config = load_global_config()
    if not any(s["slug"] == slug for s in config["services"]):
        config["services"].append({
            "name": service_name,
            "slug": slug,
        })
        save_global_config(config)

    logger.info(f"Created service: {service_name} ({slug})")
    return slug


def list_services() -> list:
    """List all configured services."""
    config = load_global_config()
    return config.get("services", [])
