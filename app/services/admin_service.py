"""
Admin authentication and cross-service data aggregation.
Admin credentials stored in %APPDATA%/CPR-Tracker/admin.json.
Annotations stored in %APPDATA%/CPR-Tracker/annotations.json.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import Optional, List, Dict

from app.desktop_config import get_appdata_dir
from app.services.auth_service import hash_password, verify_password
from app.services.activity_service import get_last_active

logger = logging.getLogger(__name__)

# Default admin username (password must be set on first run)
DEFAULT_ADMIN_USERNAME = "Admin"

# Module-level state
_admin_authenticated = False


def get_admin_file() -> Path:
    """Get path to admin.json in the base AppData directory."""
    return get_appdata_dir() / "admin.json"


def admin_needs_setup() -> bool:
    """Check if admin credentials need to be created on first run."""
    return not get_admin_file().exists()


def setup_admin_credentials(password: str) -> bool:
    """Create admin credentials on first run. Returns True on success."""
    admin_file = get_admin_file()
    if admin_file.exists():
        return False  # Already exists

    if len(password) < 8:
        return False

    admin_file.parent.mkdir(parents=True, exist_ok=True)
    pw_hash = hash_password(password)
    data = {
        "username": DEFAULT_ADMIN_USERNAME,
        "password_hash": pw_hash,
    }
    admin_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info("Admin credentials created via first-run setup")
    return True


def ensure_admin_credentials() -> None:
    """Ensure admin directory exists (no longer creates default password)."""
    admin_file = get_admin_file()
    admin_file.parent.mkdir(parents=True, exist_ok=True)


def check_admin_password(username: str, password: str) -> bool:
    """Verify admin credentials."""
    admin_file = get_admin_file()
    if not admin_file.exists():
        ensure_admin_credentials()

    try:
        data = json.loads(admin_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return False

    stored_username = data.get("username", "")
    stored_hash = data.get("password_hash", "")

    if username != stored_username:
        return False

    return verify_password(password, stored_hash)


def set_admin_authenticated(value: bool) -> None:
    """Set admin authentication state."""
    global _admin_authenticated
    _admin_authenticated = value


def is_admin_authenticated() -> bool:
    """Check if admin is currently authenticated."""
    return _admin_authenticated


def get_all_services_data() -> list:
    """Read sessions and providers from every service directory.
    Returns a list of dicts, one per service.
    """
    appdata_dir = get_appdata_dir()
    if not appdata_dir.exists():
        return []

    from app.desktop_config import load_global_config
    config = load_global_config()
    services = config.get("services", [])

    results = []
    for svc in services:
        slug = svc.get("slug", "")
        name = svc.get("name", slug)
        svc_dir = appdata_dir / slug

        if not svc_dir.exists():
            continue

        # Load sessions
        sessions_file = svc_dir / "data" / "sessions.json"
        sessions = []
        if sessions_file.exists():
            try:
                raw = json.loads(sessions_file.read_text(encoding="utf-8"))
                sessions = raw.get("sessions", [])
            except (json.JSONDecodeError, IOError):
                pass

        # Load providers
        providers_file = svc_dir / "data" / "providers.json"
        providers = []
        if providers_file.exists():
            try:
                raw = json.loads(providers_file.read_text(encoding="utf-8"))
                providers = raw.get("providers", [])
            except (json.JSONDecodeError, IOError):
                pass

        # Compute summary stats
        total_sessions = len(sessions)
        real_calls = [s for s in sessions if s.get("session_type") == "real_call"]
        simulated = [s for s in sessions if s.get("session_type") == "simulated"]
        complete_sessions = [s for s in sessions if s.get("status") == "complete"]

        # Average metrics across completed sessions
        avg_rate = 0
        avg_depth = 0
        avg_ccf = 0
        avg_depth_compliance = 0
        avg_rate_compliance = 0
        avg_jcls = 0
        rates = []
        depths = []
        ccfs = []
        depth_comps = []
        rate_comps = []
        jcls_scores = []

        metrics_sessions = [s for s in complete_sessions if s.get("metrics")]
        if metrics_sessions:
            rates = [s["metrics"].get("compression_rate", 0) for s in metrics_sessions if s["metrics"].get("compression_rate")]
            depths = [s["metrics"].get("compression_depth", 0) for s in metrics_sessions if s["metrics"].get("compression_depth")]
            ccfs = [s["metrics"].get("compression_fraction", 0) for s in metrics_sessions if s["metrics"].get("compression_fraction")]
            depth_comps = [s["metrics"].get("correct_depth_percent", 0) for s in metrics_sessions if s["metrics"].get("correct_depth_percent")]
            rate_comps = [s["metrics"].get("correct_rate_percent", 0) for s in metrics_sessions if s["metrics"].get("correct_rate_percent")]
            jcls_scores = [s["metrics"].get("jcls_score", 0) for s in metrics_sessions if s["metrics"].get("jcls_score") is not None]

            avg_rate = round(sum(rates) / len(rates), 1) if rates else 0
            avg_depth = round(sum(depths) / len(depths), 1) if depths else 0
            avg_ccf = round(sum(ccfs) / len(ccfs), 1) if ccfs else 0
            avg_depth_compliance = round(sum(depth_comps) / len(depth_comps), 1) if depth_comps else 0
            avg_rate_compliance = round(sum(rate_comps) / len(rate_comps), 1) if rate_comps else 0
            avg_jcls = round(sum(jcls_scores) / len(jcls_scores), 1) if jcls_scores else 0

        active_providers = [p for p in providers if p.get("status") == "active"]

        # ROSC stats (real calls only)
        rosc_sessions = [s for s in real_calls if s.get("outcome") == "ROSC"]
        no_rosc_sessions = [s for s in real_calls if s.get("outcome") == "No ROSC"]
        ongoing_sessions = [s for s in real_calls if s.get("outcome") == "Ongoing"]
        rosc_rate = round(len(rosc_sessions) / len(real_calls) * 100, 1) if real_calls else 0

        # Platoon breakdown
        platoon_counts = {}
        for s in sessions:
            p = s.get("platoon", "Unassigned") or "Unassigned"
            platoon_counts[p] = platoon_counts.get(p, 0) + 1

        # Certification breakdown
        cert_counts = {}
        for p in active_providers:
            cert = p.get("certification", "Unknown") or "Unknown"
            cert_counts[cert] = cert_counts.get(cert, 0) + 1

        # Monthly session counts (last 6 months)
        from datetime import datetime, timedelta
        now = datetime.now()
        monthly_counts = {}
        for i in range(5, -1, -1):
            dt = now - timedelta(days=i * 30)
            key = dt.strftime("%Y-%m")
            monthly_counts[key] = 0
        for s in sessions:
            d = s.get("date", "")
            if d and len(d) >= 7:
                month_key = d[:7]
                if month_key in monthly_counts:
                    monthly_counts[month_key] += 1

        # Best/worst metrics
        best_ccf = max(ccfs) if ccfs else 0
        worst_ccf = min(ccfs) if ccfs else 0
        best_depth_comp = max(depth_comps) if depth_comps else 0
        worst_depth_comp = min(depth_comps) if depth_comps else 0

        # Monthly metric averages (for trending charts)
        monthly_metrics = {}
        for s in complete_sessions:
            d = s.get("date", "")
            m = s.get("metrics")
            if d and len(d) >= 7 and m:
                mk = d[:7]
                if mk not in monthly_metrics:
                    monthly_metrics[mk] = {"rates": [], "depths": [], "ccfs": [], "depth_comps": [], "rate_comps": [], "jcls": []}
                if m.get("compression_rate"):
                    monthly_metrics[mk]["rates"].append(m["compression_rate"])
                if m.get("compression_depth"):
                    monthly_metrics[mk]["depths"].append(m["compression_depth"])
                if m.get("compression_fraction"):
                    monthly_metrics[mk]["ccfs"].append(m["compression_fraction"])
                if m.get("correct_depth_percent"):
                    monthly_metrics[mk]["depth_comps"].append(m["correct_depth_percent"])
                if m.get("correct_rate_percent"):
                    monthly_metrics[mk]["rate_comps"].append(m["correct_rate_percent"])
                if m.get("jcls_score") is not None:
                    monthly_metrics[mk]["jcls"].append(m["jcls_score"])

        monthly_avg = {}
        for mk, vals in monthly_metrics.items():
            monthly_avg[mk] = {
                "avg_rate": round(sum(vals["rates"]) / len(vals["rates"]), 1) if vals["rates"] else None,
                "avg_depth": round(sum(vals["depths"]) / len(vals["depths"]), 1) if vals["depths"] else None,
                "avg_ccf": round(sum(vals["ccfs"]) / len(vals["ccfs"]), 1) if vals["ccfs"] else None,
                "avg_depth_compliance": round(sum(vals["depth_comps"]) / len(vals["depth_comps"]), 1) if vals["depth_comps"] else None,
                "avg_rate_compliance": round(sum(vals["rate_comps"]) / len(vals["rate_comps"]), 1) if vals["rate_comps"] else None,
                "avg_jcls": round(sum(vals["jcls"]) / len(vals["jcls"]), 1) if vals["jcls"] else None,
                "session_count": len(vals["rates"]) or len(vals["depths"]) or 0,
            }

        results.append({
            "slug": slug,
            "name": name,
            "last_active": get_last_active(slug),
            "total_sessions": total_sessions,
            "real_calls": len(real_calls),
            "simulated": len(simulated),
            "complete_sessions": len(complete_sessions),
            "total_providers": len(providers),
            "active_providers": len(active_providers),
            "avg_compression_rate": avg_rate,
            "avg_compression_depth": avg_depth,
            "avg_ccf": avg_ccf,
            "avg_depth_compliance": avg_depth_compliance,
            "avg_rate_compliance": avg_rate_compliance,
            "avg_jcls": avg_jcls,
            # ROSC stats
            "rosc_count": len(rosc_sessions),
            "no_rosc_count": len(no_rosc_sessions),
            "ongoing_count": len(ongoing_sessions),
            "rosc_rate": rosc_rate,
            # Breakdowns
            "platoon_counts": platoon_counts,
            "cert_counts": cert_counts,
            "monthly_counts": monthly_counts,
            "monthly_avg": monthly_avg,
            # Best/worst
            "best_ccf": best_ccf,
            "worst_ccf": worst_ccf,
            "best_depth_compliance": best_depth_comp,
            "worst_depth_compliance": worst_depth_comp,
            # Raw data
            "sessions": sessions,
            "providers": providers,
        })

    return results


# ============================================================================
# Annotations — Event markers for trend charts
# Stored globally in %APPDATA%/CPR-Tracker/annotations.json
# ============================================================================

def _get_annotations_file() -> Path:
    return get_appdata_dir() / "annotations.json"


def load_annotations() -> List[Dict]:
    """Load all annotations."""
    f = _get_annotations_file()
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data.get("annotations", [])
    except (json.JSONDecodeError, IOError):
        return []


def save_annotations(annotations: List[Dict]) -> None:
    """Persist annotations list."""
    f = _get_annotations_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"annotations": annotations}, indent=2), encoding="utf-8")


def add_annotation(month: str, label: str, description: str = "", color: str = "#dc2626") -> Dict:
    """Add an event annotation. month format: 'YYYY-MM'."""
    annotations = load_annotations()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "month": month,
        "label": label,
        "description": description,
        "color": color,
    }
    annotations.append(entry)
    save_annotations(annotations)
    return entry


def delete_annotation(annotation_id: str) -> bool:
    """Delete an annotation by ID."""
    annotations = load_annotations()
    original_len = len(annotations)
    annotations = [a for a in annotations if a.get("id") != annotation_id]
    if len(annotations) < original_len:
        save_annotations(annotations)
        return True
    return False
