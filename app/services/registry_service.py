"""
Service registry — bakes the fire department list into the .exe at build time
and seeds new machines on first launch so departments appear in the dropdown.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from app.desktop_config import (
    get_appdata_dir, get_service_dir, get_bundle_dir,
    load_global_config, save_global_config, slugify,
)

logger = logging.getLogger(__name__)

REGISTRY_FILENAME = "services_registry.json"


# ---------------------------------------------------------------------------
# Build-time: generate the registry from the current machine's state
# ---------------------------------------------------------------------------

def generate_registry(output_path: Optional[Path] = None) -> Path:
    """Scan %APPDATA%/CPR-Tracker and produce a services_registry.json.
    Called by build.bat before PyInstaller runs.
    """
    appdata = get_appdata_dir()
    config = load_global_config()

    registry = {"services": [], "github": None}

    for svc in config.get("services", []):
        slug = svc["slug"]
        name = svc.get("name", slug)
        service_dir = appdata / slug

        entry = {"name": name, "slug": slug}

        # Include password hash so users can log in on new machines
        auth_file = service_dir / "auth.json"
        if auth_file.exists():
            try:
                auth = json.loads(auth_file.read_text(encoding="utf-8"))
                entry["password_hash"] = auth.get("password_hash", "")
            except (json.JSONDecodeError, IOError):
                pass

        # Include backup config so auto-sync works immediately
        backup_file = service_dir / "backup_config.json"
        if backup_file.exists():
            try:
                bc = json.loads(backup_file.read_text(encoding="utf-8"))
                entry["backup"] = {
                    "github_token": bc.get("github_token", ""),
                    "repo_owner": bc.get("repo_owner", ""),
                    "repo_name": bc.get("repo_name", ""),
                }
                # Also store globally for services that don't have backup yet
                if bc.get("github_token") and not registry["github"]:
                    registry["github"] = {
                        "github_token": bc["github_token"],
                        "repo_owner": bc.get("repo_owner", ""),
                        "repo_name": bc.get("repo_name", ""),
                    }
            except (json.JSONDecodeError, IOError):
                pass

        # Copy test data flag if present
        if svc.get("is_test_data"):
            entry["is_test_data"] = True

        registry["services"].append(entry)

    if output_path is None:
        output_path = get_bundle_dir() / "data" / REGISTRY_FILENAME

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    logger.info("Registry generated at %s with %d services", output_path, len(registry["services"]))
    return output_path


# ---------------------------------------------------------------------------
# Runtime: seed local services from the bundled registry
# ---------------------------------------------------------------------------

def _update_backup_config(svc: dict, global_github: dict | None) -> None:
    """Update backup config for an existing service if the registry has newer info."""
    backup_info = svc.get("backup") or global_github
    if not backup_info or not backup_info.get("github_token"):
        return

    service_dir = get_service_dir(svc["slug"])
    if not service_dir.exists():
        return

    # Check if backup is already configured with this token
    backup_file = service_dir / "backup_config.json"
    if backup_file.exists():
        try:
            existing = json.loads(backup_file.read_text(encoding="utf-8"))
            if existing.get("github_token") == backup_info["github_token"]:
                return  # Already up to date
        except (json.JSONDecodeError, IOError):
            pass

    # Write updated backup config
    from app.services.backup_service import configure
    configure(
        service_dir,
        backup_info["github_token"],
        backup_info.get("repo_owner", ""),
        backup_info.get("repo_name", ""),
    )
    logger.info("Updated backup config for existing service: %s", svc["slug"])


def seed_from_registry() -> int:
    """Read the bundled services_registry.json and create any missing services.
    Returns the number of new services created.
    """
    import shutil

    bundle_dir = get_bundle_dir()
    registry_path = bundle_dir / "data" / REGISTRY_FILENAME

    if not registry_path.exists():
        return 0

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        logger.warning("Could not read registry file")
        return 0

    config = load_global_config()
    existing_slugs = {s["slug"] for s in config.get("services", [])}
    created = 0

    for svc in registry.get("services", []):
        slug = svc["slug"]
        name = svc.get("name", slug)

        if slug in existing_slugs:
            # Even for existing services, update backup config if registry has one
            _update_backup_config(svc, registry.get("github"))
            continue

        # Create the service directory structure
        service_dir = get_service_dir(slug)
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
            encoding="utf-8",
        )
        (service_dir / "data" / "providers.json").write_text(
            json.dumps({"providers": [], "last_updated": ""}, indent=2),
            encoding="utf-8",
        )

        # Write password hash so users can log in
        if svc.get("password_hash"):
            (service_dir / "auth.json").write_text(
                json.dumps({"password_hash": svc["password_hash"]}),
                encoding="utf-8",
            )

        # Write backup config so auto-sync works on login
        backup_info = svc.get("backup") or registry.get("github")
        if backup_info and backup_info.get("github_token"):
            from app.services.backup_service import configure
            configure(
                service_dir,
                backup_info["github_token"],
                backup_info.get("repo_owner", ""),
                backup_info.get("repo_name", ""),
            )

        # Add to global config
        entry = {"name": name, "slug": slug}
        if svc.get("is_test_data"):
            entry["is_test_data"] = True
        config.setdefault("services", []).append(entry)
        existing_slugs.add(slug)
        created += 1

        logger.info("Seeded service from registry: %s (%s)", name, slug)

    if created > 0:
        save_global_config(config)

    return created
