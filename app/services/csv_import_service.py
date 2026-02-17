"""CSV provider import service."""
import csv
import io
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict
from pathlib import Path

from app.desktop_config import get_service_dir

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = {"name", "certification"}


def validate_provider_csv(csv_text: str) -> List[str]:
    errors = []
    if not csv_text.strip():
        errors.append("CSV file is empty")
        return errors
    reader = csv.reader(io.StringIO(csv_text.strip()))
    try:
        headers = [h.strip().lower() for h in next(reader)]
    except StopIteration:
        errors.append("CSV file has no header row")
        return errors
    missing = REQUIRED_HEADERS - set(headers)
    if missing:
        errors.append(f"Missing required columns: {', '.join(h.title() for h in sorted(missing))}")
    return errors


def parse_provider_csv(csv_text: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames] if reader.fieldnames else []
    rows = []
    for row in reader:
        name = row.get("name", "").strip()
        cert = row.get("certification", "").strip()
        if name:
            rows.append({"name": name, "certification": cert})
    return rows


def import_providers_to_service(service_slug: str, providers: List[Dict[str, str]]) -> Dict[str, int]:
    providers_file = get_service_dir(service_slug) / "data" / "providers.json"
    existing = []
    if providers_file.exists():
        try:
            raw = json.loads(providers_file.read_text(encoding="utf-8"))
            existing = raw.get("providers", [])
        except (json.JSONDecodeError, IOError):
            pass
    existing_names = {p.get("name", "").lower() for p in existing}
    added = 0
    skipped = 0
    for p in providers:
        if p["name"].lower() in existing_names:
            skipped += 1
            continue
        names = p["name"].split(maxsplit=1)
        first_name = names[0] if names else ""
        last_name = names[1] if len(names) > 1 else ""
        existing.append({
            "id": str(uuid.uuid4())[:8],
            "name": p["name"],
            "first_name": first_name,
            "last_name": last_name,
            "certification": p["certification"],
            "role": "Paramedic",
            "status": "active",
        })
        existing_names.add(p["name"].lower())
        added += 1
    providers_file.parent.mkdir(parents=True, exist_ok=True)
    providers_file.write_text(
        json.dumps({"providers": existing, "last_updated": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )
    return {"added": added, "skipped": skipped, "errors": 0}
