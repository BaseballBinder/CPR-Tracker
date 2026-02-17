"""
Test data generation service.
Generates a synthetic 'Test 16 Fire Department' service with
50 providers and 20 sessions for demonstration and testing.
"""
import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.desktop_config import get_appdata_dir, load_global_config, save_global_config
from app.services.auth_service import hash_password

logger = logging.getLogger(__name__)

TEST_SERVICE_NAME = "Test 16 Fire Department"
TEST_SERVICE_SLUG = "test-16-fire-department"
TEST_SERVICE_PASSWORD = "password"

# Realistic Canadian first / last names
FIRST_NAMES_M = [
    "James", "Liam", "Noah", "Ethan", "Owen", "Lucas", "Benjamin",
    "Alexander", "William", "Daniel", "Matthew", "Ryan", "Connor",
    "Nathan", "Tyler", "Kyle", "Derek", "Sean", "Patrick", "Andrew",
    "Michael", "David", "Jason", "Mark", "Kevin",
]
FIRST_NAMES_F = [
    "Olivia", "Emma", "Charlotte", "Amelia", "Sophie", "Mia", "Ava",
    "Isabella", "Abigail", "Emily", "Sarah", "Jessica", "Rachel",
    "Lauren", "Nicole", "Megan", "Kayla", "Samantha", "Chloe", "Hannah",
    "Natasha", "Brianna", "Ashley", "Taylor", "Morgan",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
    "Miller", "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson",
    "Taylor", "Thomas", "Hernandez", "Moore", "Martin", "Jackson",
    "Thompson", "White", "Lopez", "Lee", "Gonzalez", "Harris",
    "Clark", "Lewis", "Robinson", "Walker", "Young", "Allen",
    "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Perez",
    "Roberts", "Turner", "Phillips", "Campbell", "Parker", "Evans",
    "Edwards", "Collins",
]

PLATOONS = ["A", "B", "C", "D"]
OUTCOMES = ["ROSC", "ROSC", "ROSC", "No ROSC", "No ROSC", "No ROSC",
            "No ROSC", "No ROSC", "No ROSC", "Ongoing"]


def _generate_providers(count: int = 50) -> list:
    """Generate realistic providers. 70% PCP, 30% ACP."""
    providers = []
    used_names = set()
    all_first = FIRST_NAMES_M + FIRST_NAMES_F

    for i in range(count):
        # Avoid duplicate names
        while True:
            first = random.choice(all_first)
            last = random.choice(LAST_NAMES)
            full = f"{first} {last}"
            if full not in used_names:
                used_names.add(full)
                break

        cert = "PCP" if random.random() < 0.7 else "ACP"
        provider = {
            "id": uuid.uuid4().hex[:12],
            "name": full,
            "first_name": first,
            "last_name": last,
            "certification": cert,
            "role": "Paramedic",
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }
        providers.append(provider)

    return providers


def _generate_sessions(providers: list, count: int = 20) -> list:
    """Generate 20 sessions: 8 real calls + 12 simulated, spread over 6 months."""
    sessions = []
    now = datetime.now()
    real_count = 8
    sim_count = count - real_count

    for i in range(count):
        session_id = uuid.uuid4().hex[:12]
        # Spread over the last 6 months
        days_ago = random.randint(0, 180)
        session_date = now - timedelta(days=days_ago)
        date_str = session_date.strftime("%Y-%m-%d")
        time_str = f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}"
        platoon = random.choice(PLATOONS)

        # Pick random providers
        primary = random.choice(providers)
        participants_pool = [p for p in providers if p["id"] != primary["id"]]
        participant_count = random.randint(1, min(4, len(participants_pool)))
        participants = random.sample(participants_pool, participant_count)

        # Generate realistic metrics
        compression_rate = round(random.uniform(95, 125), 1)
        compression_depth = round(random.uniform(4.5, 6.5), 1)
        correct_depth_percent = round(random.uniform(50, 98), 1)
        correct_rate_percent = round(random.uniform(50, 98), 1)
        compression_fraction = round(random.uniform(60, 95), 1)
        metrics = {
            "compression_rate": compression_rate,
            "compression_depth": compression_depth,
            "correct_depth_percent": correct_depth_percent,
            "correct_rate_percent": correct_rate_percent,
            "compression_fraction": compression_fraction,
            "duration": round(random.uniform(120, 900), 0),
            "total_compressions": random.randint(200, 2000),
        }

        if i < real_count:
            # Real call
            outcome = random.choice(OUTCOMES)
            shocks = random.randint(0, 4) if random.random() > 0.3 else 0
            session = {
                "id": session_id,
                "session_type": "real_call",
                "status": "complete",
                "date": date_str,
                "time": time_str,
                "event_type": "Cardiac Arrest",
                "outcome": outcome,
                "shocks_delivered": shocks,
                "platoon": platoon,
                "provider_id": primary["id"],
                "provider_name": primary["name"],
                "participants": [
                    {"provider_id": primary["id"], "provider_name": primary["name"], "is_primary": True}
                ] + [
                    {"provider_id": p["id"], "provider_name": p["name"], "is_primary": False}
                    for p in participants
                ],
                "metrics": metrics,
                "zoll_data_available": True,
                "resuscitation_attempted": "Yes",
                "created_at": session_date.isoformat(),
            }
        else:
            # Simulated
            session = {
                "id": session_id,
                "session_type": "simulated",
                "status": "complete",
                "date": date_str,
                "time": time_str,
                "event_type": "Simulated",
                "platoon": platoon,
                "provider_id": primary["id"],
                "provider_name": primary["name"],
                "participants": [
                    {"provider_id": primary["id"], "provider_name": primary["name"], "is_primary": True}
                ] + [
                    {"provider_id": p["id"], "provider_name": p["name"], "is_primary": False}
                    for p in participants
                ],
                "metrics": metrics,
                "created_at": session_date.isoformat(),
            }

        sessions.append(session)

    # Sort by date descending (most recent first)
    sessions.sort(key=lambda s: s["date"], reverse=True)
    return sessions


def generate_test_data() -> dict:
    """Generate the complete test fire department data.

    Returns dict with success/error info.
    """
    appdata_dir = get_appdata_dir()
    svc_dir = appdata_dir / TEST_SERVICE_SLUG

    # Create service directory
    data_dir = svc_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Generate data
    providers = _generate_providers(50)
    sessions = _generate_sessions(providers, 20)

    # Write providers.json
    providers_file = data_dir / "providers.json"
    providers_file.write_text(
        json.dumps({"providers": providers}, indent=2),
        encoding="utf-8",
    )

    # Write sessions.json
    sessions_file = data_dir / "sessions.json"
    sessions_file.write_text(
        json.dumps({"sessions": sessions}, indent=2),
        encoding="utf-8",
    )

    # Write password hash
    pw_hash = hash_password(TEST_SERVICE_PASSWORD)
    auth_file = svc_dir / "auth.json"
    auth_file.write_text(
        json.dumps({"password_hash": pw_hash}, indent=2),
        encoding="utf-8",
    )

    # Register the service in global config
    config = load_global_config()
    services = config.get("services", [])

    # Remove existing test service entry if any
    services = [s for s in services if s.get("slug") != TEST_SERVICE_SLUG]
    services.append({
        "slug": TEST_SERVICE_SLUG,
        "name": TEST_SERVICE_NAME,
        "created_at": datetime.now().isoformat(),
        "is_test_data": True,
    })
    config["services"] = services
    save_global_config(config)

    logger.info(f"Generated test data: {len(providers)} providers, {len(sessions)} sessions")

    return {
        "success": True,
        "message": f"Generated '{TEST_SERVICE_NAME}' with {len(providers)} providers and {len(sessions)} sessions.",
        "service_slug": TEST_SERVICE_SLUG,
        "providers_count": len(providers),
        "sessions_count": len(sessions),
    }


def delete_test_data() -> dict:
    """Delete the test fire department data.

    Returns dict with success/error info.
    """
    import shutil

    appdata_dir = get_appdata_dir()
    svc_dir = appdata_dir / TEST_SERVICE_SLUG

    if not svc_dir.exists():
        return {
            "success": False,
            "error": "Test data not found. Nothing to delete.",
        }

    # Remove service directory
    try:
        shutil.rmtree(svc_dir)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to delete test data: {str(e)}",
        }

    # Remove from global config
    config = load_global_config()
    services = config.get("services", [])
    services = [s for s in services if s.get("slug") != TEST_SERVICE_SLUG]
    config["services"] = services
    save_global_config(config)

    logger.info("Deleted test data")

    return {
        "success": True,
        "message": "Test data deleted successfully.",
    }


def test_data_exists() -> bool:
    """Check if test data service exists."""
    appdata_dir = get_appdata_dir()
    svc_dir = appdata_dir / TEST_SERVICE_SLUG
    return svc_dir.exists()
