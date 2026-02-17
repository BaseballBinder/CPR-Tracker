"""
Data structures for CPR Tracking System.
Data imported from CSV files.
Sessions are persisted to disk via persistence.py so they survive restarts.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from app.models import SessionType, SessionStatus, SessionParticipant, SessionArtifact
from app.persistence import load_sessions, save_sessions as persist_sessions, load_providers, delete_provider_from_file

# Teams - empty until configured in Settings
TEAMS = []

# Certifications reference
CERTIFICATIONS = ["ACP", "PCP", "Mechanic"]

# Providers - base roster (imported from roster)
_BASE_PROVIDERS = []

# Load providers from disk for the active service
PROVIDERS = load_providers()

# Create lookup for provider by name
PROVIDER_BY_NAME = {p["name"]: p["id"] for p in PROVIDERS}

# Event types - reference list for dropdowns
EVENT_TYPES = ["Cardiac Arrest", "Respiratory Arrest", "Trauma", "Medical Emergency", "Simulated"]

# Outcomes - reference list for dropdowns
OUTCOMES = ["ROSC", "No ROSC", "Ongoing", "Transported"]

# Joules comparison data for fun statistics
# Each defibrillator shock delivers approximately 200 Joules
JOULES_PER_SHOCK = 200

# Fun comparisons for Joules delivered (cumulative ranges)
JOULES_COMPARISONS = [
    {"min_joules": 0, "max_joules": 199, "comparison": "Not enough to power an LED for 1 second", "icon": "lightbulb"},
    {"min_joules": 200, "max_joules": 399, "comparison": "Enough to light an LED for about 3 minutes", "icon": "lightbulb"},
    {"min_joules": 400, "max_joules": 999, "comparison": "Equivalent to powering a phone flashlight for 5 minutes", "icon": "flashlight"},
    {"min_joules": 1000, "max_joules": 1999, "comparison": "Similar to the energy in a AA battery", "icon": "battery"},
    {"min_joules": 2000, "max_joules": 2999, "comparison": "Could toast a slice of bread", "icon": "toast"},
    {"min_joules": 3000, "max_joules": 4999, "comparison": "Enough to brew a single cup of coffee", "icon": "coffee"},
    {"min_joules": 5000, "max_joules": 7499, "comparison": "Could power a laptop for about 30 seconds", "icon": "laptop"},
    {"min_joules": 7500, "max_joules": 9999, "comparison": "Similar to the kinetic energy of a bowling ball at 60 mph", "icon": "bowling"},
    {"min_joules": 10000, "max_joules": 14999, "comparison": "Enough to run a microwave for 10 seconds", "icon": "microwave"},
    {"min_joules": 15000, "max_joules": 19999, "comparison": "Could charge a smartphone 3 times", "icon": "phone"},
    {"min_joules": 20000, "max_joules": 29999, "comparison": "Equivalent to the energy in a small firecracker", "icon": "spark"},
    {"min_joules": 30000, "max_joules": 49999, "comparison": "Could power a 100W light bulb for 5 minutes", "icon": "bulb"},
    {"min_joules": 50000, "max_joules": 99999, "comparison": "Similar to the energy released eating a single M&M", "icon": "candy"},
    {"min_joules": 100000, "max_joules": float('inf'), "comparison": "Enough energy to lift a car 1 inch off the ground", "icon": "car"},
]


def get_joules_comparison(total_joules: int) -> dict:
    """Get a fun comparison for the given Joules amount."""
    for comp in JOULES_COMPARISONS:
        if comp["min_joules"] <= total_joules <= comp["max_joules"]:
            return {
                "comparison": comp["comparison"],
                "icon": comp["icon"],
            }
    # Fallback
    return {
        "comparison": "An impressive amount of life-saving energy!",
        "icon": "lightning",
    }


# Compression distance calculation (based on ~5.5cm avg depth per compression)
# Distance in meters = compressions × 0.055m


def get_compressions_comparison(total_compressions: int, avg_depth_cm: float = 5.5) -> dict:
    """
    Calculate total compression distance.
    Uses average depth to calculate total distance pushed.
    Returns distance in km (no commentary).
    """
    # Calculate total distance in meters
    depth_m = avg_depth_cm / 100  # Convert cm to meters
    total_distance_m = total_compressions * depth_m
    total_distance_km = total_distance_m / 1000

    # Format the distance display
    if total_distance_km >= 1:
        distance_text = f"{total_distance_km:,.2f} km"
    else:
        distance_text = f"{total_distance_m:,.0f} m"

    return {
        "comparison": distance_text,
        "icon": "heart",
        "distance_m": round(total_distance_m, 1),
        "distance_km": round(total_distance_km, 2),
    }

# Location types - reference list
LOCATION_TYPES = ["Residential", "Commercial", "Public", "Healthcare Facility", "Outdoor"]

# Initial/baseline sessions - imported from CSV training data
# These are the pre-loaded training sessions that come with the system
_INITIAL_SESSIONS = []


def _initialize_sessions() -> List[Dict[str, Any]]:
    """Load sessions from disk for the active service."""
    return load_sessions()


# Active sessions list - combines baseline + persisted user sessions
SESSIONS: List[Dict[str, Any]] = _initialize_sessions()


def _save_user_sessions():
    """Save all sessions to disk."""
    persist_sessions(SESSIONS)


def get_team_by_id(team_id: str):
    """Get team by ID."""
    return next((t for t in TEAMS if t["id"] == team_id), None)


def get_provider_by_id(provider_id: str):
    """Get provider by ID."""
    return next((p for p in PROVIDERS if p["id"] == provider_id), None)


def get_provider_by_name(name: str):
    """Get provider by name."""
    return next((p for p in PROVIDERS if p["name"] == name), None)


def get_providers_by_team(team_id: str):
    """Get all providers in a team."""
    return [p for p in PROVIDERS if p["team_id"] == team_id]


def get_sessions_by_provider(provider_id: str, include_as_participant: bool = True):
    """
    Get all sessions for a provider.

    Args:
        provider_id: The provider ID to search for
        include_as_participant: If True, includes sessions where provider is a participant
                               (not just primary). Defaults to True.

    Returns:
        List of sessions, each with an added 'provider_role' field:
        - 'lead' if they were primary/team lead
        - 'provider' if they were a participant
        - 'individual' for simulated sessions (no team)
    """
    results = []
    for s in SESSIONS:
        session_copy = None

        # Check if they're the primary provider
        if s.get("provider_id") == provider_id:
            session_copy = dict(s)
            # Determine role based on session type and participants
            if s.get("session_type") == "simulated":
                session_copy["provider_role"] = "individual"
            elif s.get("participants"):
                # Check if they're marked as primary in participants
                for p in s.get("participants", []):
                    if p.get("provider_id") == provider_id and p.get("is_primary"):
                        session_copy["provider_role"] = "lead"
                        break
                else:
                    session_copy["provider_role"] = "lead"  # Primary provider = lead
            else:
                session_copy["provider_role"] = "lead"

        # Check if they're a participant (non-primary)
        elif include_as_participant and s.get("participants"):
            for p in s.get("participants", []):
                if p.get("provider_id") == provider_id:
                    session_copy = dict(s)
                    session_copy["provider_role"] = "lead" if p.get("is_primary") else "provider"
                    break

        if session_copy:
            results.append(session_copy)

    return results


def get_sessions_by_provider_name(provider_name: str):
    """Get all sessions for a provider by name."""
    return [s for s in SESSIONS if s.get("provider_name") == provider_name]


def get_sessions_by_team(team_id: str):
    """Get all sessions for a team."""
    return [s for s in SESSIONS if s["team_id"] == team_id]


def add_provider(name: str, first_name: str, last_name: str, certification: str, role: str = "Paramedic"):
    """Add a new provider and persist to disk. Returns existing provider if duplicate found."""
    from app.persistence import add_provider_to_file

    # Check for existing provider with same name (case-insensitive)
    name_lower = name.lower().strip()
    for existing in PROVIDERS:
        if existing.get("name", "").lower().strip() == name_lower:
            # Return existing provider instead of creating duplicate
            return existing

    # Generate unique ID - find max existing ID number
    max_id = 0
    for p in PROVIDERS:
        pid = p.get("id", "")
        if pid.startswith("EMP"):
            try:
                num = int(pid[3:])
                max_id = max(max_id, num)
            except ValueError:
                pass
    new_id = f"EMP{max_id + 1:03d}"

    provider = {
        "id": new_id,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "certification": certification,
        "status": "active",
        "role": role,
        "team_id": None
    }
    PROVIDERS.append(provider)
    PROVIDER_BY_NAME[name] = new_id

    # Persist to disk
    add_provider_to_file(provider)

    return provider


def delete_provider(provider_id: str) -> bool:
    """
    Delete a provider by ID.
    Returns True if deleted, False if not found.
    Note: Base roster providers (from _BASE_PROVIDERS) cannot be deleted from file,
    but will be removed from the in-memory list.
    """
    global PROVIDERS, PROVIDER_BY_NAME

    # Find the provider
    provider = next((p for p in PROVIDERS if p["id"] == provider_id), None)
    if not provider:
        return False

    # Remove from in-memory lists
    provider_name = provider.get("name")
    PROVIDERS[:] = [p for p in PROVIDERS if p["id"] != provider_id]
    if provider_name and provider_name in PROVIDER_BY_NAME:
        del PROVIDER_BY_NAME[provider_name]

    # Try to delete from persisted file (only works for user-added providers)
    delete_provider_from_file(provider_id)

    return True


def add_session(date: str, provider_name: str, event_type: str, metrics: dict):
    """Add a new session (legacy function for backwards compatibility)."""
    provider = get_provider_by_name(provider_name)
    provider_id = provider["id"] if provider else None

    new_id = f"S{len(SESSIONS) + 1:03d}"
    session = {
        "id": new_id,
        "date": date,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "event_type": event_type,
        "team_id": None,
        "outcome": None,
        "metrics": metrics,
        # New fields with defaults for backwards compatibility
        "session_type": SessionType.SIMULATED.value,
        "status": SessionStatus.COMPLETE.value,
        "time": None,
        "participants": [],
        "artifact": None,
        "error_message": None,
        "canroc_master_payload": None,
        "canroc_pco_payload": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    SESSIONS.append(session)
    return session


def generate_session_id() -> str:
    """Generate a unique session ID that won't collide with existing IDs."""
    import uuid
    # Use a short UUID suffix to ensure uniqueness
    return f"S{uuid.uuid4().hex[:8].upper()}"


def create_session(
    session_type: SessionType,
    date: str,
    time: Optional[str] = None,
    event_type: Optional[str] = None,
    outcome: Optional[str] = None,
    shocks_delivered: Optional[int] = None,
    primary_provider_id: Optional[str] = None,
    participant_ids: Optional[List[str]] = None,
    artifact: Optional[Dict[str, Any]] = None,
    zoll_data_available: bool = True,
    resuscitation_attempted: Optional[str] = None,
    zoll_missing_reason: Optional[str] = None,
    platoon: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new session with status='importing'.
    This is used by the new Add Session wizard.
    """
    session_id = generate_session_id()

    # Build participants list
    participants = []
    if primary_provider_id:
        primary_provider = get_provider_by_id(primary_provider_id)
        if primary_provider:
            participants.append({
                "provider_id": primary_provider_id,
                "provider_name": primary_provider["name"],
                "is_primary": True
            })

    if participant_ids:
        for pid in participant_ids:
            if pid != primary_provider_id:  # Don't duplicate primary
                provider = get_provider_by_id(pid)
                if provider:
                    participants.append({
                        "provider_id": pid,
                        "provider_name": provider["name"],
                        "is_primary": False
                    })

    # Get primary provider info for backwards-compatible fields
    primary_provider = get_provider_by_id(primary_provider_id) if primary_provider_id else None

    # Determine initial status based on Zoll data availability and provider assignment
    # If no primary provider, session is 'pending' (awaiting provider assignment)
    # If no Zoll data, session is 'complete' immediately (no metrics to parse)
    # If Zoll data available, session is 'importing' until parsed
    if not primary_provider_id:
        initial_status = "pending"  # New status for sessions without assigned provider
    elif session_type == SessionType.REAL_CALL and not zoll_data_available:
        initial_status = SessionStatus.COMPLETE.value
    else:
        initial_status = SessionStatus.IMPORTING.value

    session = {
        "id": session_id,
        "session_type": session_type.value if isinstance(session_type, SessionType) else session_type,
        "status": initial_status,
        "date": date,
        "time": time,
        "event_type": event_type or ("Cardiac Arrest" if session_type == SessionType.REAL_CALL else "Simulated"),
        "outcome": outcome,
        "shocks_delivered": shocks_delivered,
        # Backwards-compatible provider fields (primary provider)
        "provider_id": primary_provider_id,
        "provider_name": primary_provider["name"] if primary_provider else None,
        # New multi-participant support
        "participants": participants,
        "team_id": None,
        "platoon": platoon,
        # Zoll data availability fields (Real Call only)
        "zoll_data_available": zoll_data_available,
        "resuscitation_attempted": resuscitation_attempted,
        "zoll_missing_reason": zoll_missing_reason,
        # Metrics (empty until import completes, or always empty if no Zoll data)
        "metrics": {},
        # Import artifact reference
        "artifact": artifact,
        # Error tracking
        "error_message": None,
        # CanROC payloads
        "canroc_master_payload": None,
        "canroc_pco_payload": None,
        # Timestamps
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    SESSIONS.append(session)
    _save_user_sessions()  # Persist to disk
    return session


def get_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID."""
    return next((s for s in SESSIONS if s["id"] == session_id), None)


def update_session(session_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a session by ID."""
    session = get_session_by_id(session_id)
    if not session:
        return None

    # Update fields
    for key, value in updates.items():
        session[key] = value

    session["updated_at"] = datetime.now().isoformat()
    _save_user_sessions()  # Persist to disk
    return session


_UNSET = object()  # Sentinel for distinguishing None from unset


def update_session_status(
    session_id: str,
    status: SessionStatus,
    error_message: Optional[str] = _UNSET,
    metrics: Optional[Dict[str, Any]] = None,
    canroc_master_payload: Optional[Dict[str, Any]] = None,
    canroc_pco_payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Update session status after import attempt."""
    session = get_session_by_id(session_id)
    if not session:
        return None

    session["status"] = status.value if isinstance(status, SessionStatus) else status
    session["updated_at"] = datetime.now().isoformat()

    # Use sentinel to distinguish between "not provided" and "explicitly set to None"
    if error_message is not _UNSET:
        session["error_message"] = error_message

    if metrics is not None:
        session["metrics"] = metrics

    if canroc_master_payload is not None:
        session["canroc_master_payload"] = canroc_master_payload

    if canroc_pco_payload is not None:
        session["canroc_pco_payload"] = canroc_pco_payload

    _save_user_sessions()  # Persist to disk
    return session


def get_sessions_by_status(status: SessionStatus) -> List[Dict[str, Any]]:
    """Get all sessions with a specific status."""
    status_value = status.value if isinstance(status, SessionStatus) else status
    return [s for s in SESSIONS if s.get("status") == status_value]


def get_failed_sessions() -> List[Dict[str, Any]]:
    """Get all failed sessions (for retry functionality)."""
    return get_sessions_by_status(SessionStatus.FAILED)


def delete_session(session_id: str) -> bool:
    """
    Delete a session by ID.
    Returns True if deleted, False if not found.
    """
    global SESSIONS
    original_len = len(SESSIONS)
    SESSIONS[:] = [s for s in SESSIONS if s.get("id") != session_id]

    if len(SESSIONS) < original_len:
        _save_user_sessions()  # Persist to disk
        return True
    return False


def should_include_in_cpr_stats(session: Dict) -> bool:
    """
    Determine if a session should be included in CPR performance statistics.

    Exclusion rules:
    - If zoll_data_available=False AND resuscitation_attempted='no': Exclude from CPR stats
    - If zoll_data_available=False AND resuscitation_attempted='yes': Include in session count,
      but metrics will be empty/null (attendance tracking only)
    - If zoll_data_available=True (normal case): Include fully

    This function returns True if the session should be counted for metrics calculations.
    Sessions without metrics (no Zoll data) will naturally have no metric values to average.
    """
    # Only applies to real call sessions
    if session.get("session_type") != "real_call":
        return True  # Simulated sessions are always included

    zoll_available = session.get("zoll_data_available", True)  # Default True for backwards compat
    resus_attempted = session.get("resuscitation_attempted", "")

    # If no resuscitation was attempted, exclude from CPR metrics entirely
    if not zoll_available and resus_attempted == "no":
        return False

    return True


def get_all_arrests_count() -> int:
    """
    Get count of ALL cardiac arrest sessions (including non-resuscitated).
    Used for 'arrests attended' metric on dashboard.
    """
    return len([s for s in SESSIONS if s.get("session_type") == "real_call"])


# Dashboard KPIs - computed from actual data
def get_dashboard_kpis():
    """Calculate dashboard KPIs from actual data."""
    active_providers = [p for p in PROVIDERS if p.get("status") == "active"]
    rosc_sessions = [s for s in SESSIONS if s.get("outcome") == "ROSC"]

    # Separate sessions by type
    real_call_sessions = [s for s in SESSIONS if s.get("session_type") == "real_call"]
    simulated_sessions = [s for s in SESSIONS if s.get("session_type") != "real_call"]

    # Helper function to calculate metrics for a list of sessions
    def calc_metrics(session_list):
        if not session_list:
            return {"depth": 0, "rate": 0, "ccf": 0}
        depth_values = [s.get("metrics", {}).get("correct_depth_percent", 0) or 0 for s in session_list]
        rate_values = [s.get("metrics", {}).get("correct_rate_percent", 0) or 0 for s in session_list]
        ccf_values = [s.get("metrics", {}).get("compression_fraction", 0) or 0 for s in session_list]
        avg_depth = round(sum(depth_values) / len(depth_values), 1) if depth_values else 0
        avg_rate = round(sum(rate_values) / len(rate_values), 1) if rate_values else 0
        avg_ccf = round(sum(ccf_values) / len(ccf_values), 1) if ccf_values else 0
        return {"depth": avg_depth, "rate": avg_rate, "ccf": avg_ccf}

    # Calculate metrics for real life calls
    real_metrics = calc_metrics(real_call_sessions)

    # Calculate metrics for simulated sessions
    sim_metrics = calc_metrics(simulated_sessions)

    # Overall metrics (all sessions combined)
    all_metrics = calc_metrics(SESSIONS)

    rosc_rate = 0
    if SESSIONS:
        rosc_count = len(rosc_sessions)
        total_with_outcome = len([s for s in SESSIONS if s.get("outcome")])
        rosc_rate = round((rosc_count / total_with_outcome) * 100) if total_with_outcome else 0

    # Calculate total shocks across all real-life sessions
    total_shocks = sum(s.get("shocks_delivered", 0) or 0 for s in real_call_sessions)
    total_joules = total_shocks * JOULES_PER_SHOCK
    joules_info = get_joules_comparison(total_joules)

    # Calculate total compressions and average depth across all sessions
    total_compressions = 0
    total_depth_weighted = 0
    total_compression_count = 0
    for s in SESSIONS:
        metrics = s.get("metrics", {})
        duration = metrics.get("duration", 0) or 0
        rate = metrics.get("compression_rate", 0) or 0
        ccf = metrics.get("compression_fraction", 0) or 0
        depth = metrics.get("compression_depth", 0) or 0
        if duration > 0 and rate > 0 and ccf > 0:
            compressions = int(duration * (rate / 60) * (ccf / 100))
            total_compressions += compressions
            if depth > 0:
                total_depth_weighted += depth * compressions
                total_compression_count += compressions

    # Calculate weighted average depth (weighted by number of compressions per session)
    avg_depth_cm = round(total_depth_weighted / total_compression_count, 2) if total_compression_count > 0 else 5.5

    # Get fun compression comparison
    compressions_info = get_compressions_comparison(total_compressions, avg_depth_cm)

    # JcLS averages (real calls only)
    jcls_scores = []
    combined_compliance_values = []
    release_velocity_values = []
    release_velocity_sd_values = []

    for s in real_call_sessions:
        m = s.get("metrics", {})
        if m.get("jcls_score") is not None:
            jcls_scores.append(m["jcls_score"])
        if m.get("compressions_in_target_percent") is not None:
            combined_compliance_values.append(m["compressions_in_target_percent"])
        if m.get("mean_release_velocity") is not None:
            release_velocity_values.append(m["mean_release_velocity"])
        if m.get("release_velocity_std_dev") is not None:
            release_velocity_sd_values.append(m["release_velocity_std_dev"])

    avg_jcls = round(sum(jcls_scores) / len(jcls_scores), 1) if jcls_scores else None
    avg_combined = round(sum(combined_compliance_values) / len(combined_compliance_values), 1) if combined_compliance_values else None
    avg_rv = round(sum(release_velocity_values) / len(release_velocity_values), 1) if release_velocity_values else None
    avg_rv_sd = round(sum(release_velocity_sd_values) / len(release_velocity_sd_values), 1) if release_velocity_sd_values else None

    # Build trend data arrays (real-call sessions only, sorted by date)
    real_sorted = sorted(real_call_sessions, key=lambda s: s.get("date", ""))
    jcls_trend = []
    ccf_trend = []
    cit_trend = []
    rv_trend = []

    for s in real_sorted:
        m = s.get("metrics", {})
        d = s.get("date", "")
        if m.get("jcls_score") is not None:
            jcls_trend.append({"date": d, "value": m["jcls_score"]})
        if m.get("compression_fraction") is not None:
            ccf_trend.append({"date": d, "value": m["compression_fraction"]})
        if m.get("compressions_in_target_percent") is not None:
            cit_trend.append({"date": d, "value": m["compressions_in_target_percent"]})
        if m.get("mean_release_velocity") is not None:
            rv_trend.append({"date": d, "value": m["mean_release_velocity"]})

    return {
        "total_sessions": len(SESSIONS),
        "total_providers": len(active_providers),
        # Overall metrics (for backwards compatibility)
        "avg_depth_compliance": all_metrics["depth"],
        "avg_rate_compliance": all_metrics["rate"],
        "avg_ccf": all_metrics["ccf"],
        # Real Life Call metrics
        "real_call_count": len(real_call_sessions),
        "real_depth_compliance": real_metrics["depth"],
        "real_rate_compliance": real_metrics["rate"],
        "real_ccf": real_metrics["ccf"],
        # Simulated session metrics (CCF not applicable - only for real calls)
        "simulated_count": len(simulated_sessions),
        "sim_depth_compliance": sim_metrics["depth"],
        "sim_rate_compliance": sim_metrics["rate"],
        # Other stats
        "rosc_rate": rosc_rate,
        "avg_time_to_compression": 0,
        "total_shocks": total_shocks,
        "total_joules": total_joules,
        "joules_comparison": joules_info["comparison"],
        "total_compressions": total_compressions,
        "avg_compression_depth": avg_depth_cm,
        "compressions_comparison": compressions_info["comparison"],
        "compressions_distance_m": compressions_info["distance_m"],
        "compressions_distance_km": compressions_info["distance_km"],
        # JcLS metrics (real calls only)
        "avg_jcls_score": avg_jcls,
        "avg_jcls_color": ("green" if avg_jcls >= 80 else ("yellow" if avg_jcls >= 60 else "red")) if avg_jcls else None,
        "avg_combined_compliance": avg_combined,
        "avg_release_velocity": avg_rv,
        "avg_release_velocity_sd": avg_rv_sd,
        # Trend data (for expandable graphs)
        "jcls_trend": jcls_trend,
        "ccf_trend": ccf_trend,
        "cit_trend": cit_trend,
        "rv_trend": rv_trend,
    }


def get_provider_stats(provider_id: str):
    """Get aggregated stats for a provider across all their sessions."""
    all_sessions = get_sessions_by_provider(provider_id)
    if not all_sessions:
        return {
            "session_count": 0,
            "real_call_count": 0,
            "simulated_count": 0,
            "arrests_attended": 0,  # Total cardiac arrests (including non-resuscitated)
            "avg_depth_compliance": 0,
            "avg_rate_compliance": 0,
            "avg_compression_rate": 0,
            "avg_compression_depth": 0,
            "avg_ccf": 0,
            "avg_seconds_to_first_compression": 0,
            "avg_seconds_to_first_shock": 0,
            "avg_post_shock_pause": 0,
            "total_compressions": 0,
            "avg_mean_etco2": 0,
            "avg_max_etco2": 0,
            "avg_jcls_score": None,
        }

    # Filter sessions for CPR stats (excludes non-resuscitated calls)
    sessions = [s for s in all_sessions if should_include_in_cpr_stats(s)]

    # Count session types (for CPR stats)
    real_calls = [s for s in sessions if s.get("session_type") == "real_call"]
    simulated = [s for s in sessions if s.get("session_type") == "simulated"]

    # Total arrests attended (includes non-resuscitated - for attendance tracking)
    all_real_calls = [s for s in all_sessions if s.get("session_type") == "real_call"]

    # Helper to safely get numeric values, filtering None/0
    def get_valid_values(key, from_sessions=None):
        source = from_sessions if from_sessions is not None else sessions
        values = []
        for s in source:
            val = s.get("metrics", {}).get(key)
            if val is not None and val != 0:
                values.append(val)
        return values

    # Get metric values from sessions (basic metrics from all sessions)
    depth_compliance = get_valid_values("correct_depth_percent")
    rate_compliance = get_valid_values("correct_rate_percent")
    compression_rates = get_valid_values("compression_rate")
    compression_depths = get_valid_values("compression_depth")

    # CCF and advanced metrics ONLY from real calls (not available in simulations)
    ccf_values = get_valid_values("compression_fraction", real_calls)
    first_compression_times = get_valid_values("seconds_to_first_compression", real_calls)
    first_shock_times = get_valid_values("seconds_to_first_shock", real_calls)
    post_shock_pauses = get_valid_values("avg_post_shock_pause", real_calls)
    total_compressions_list = get_valid_values("total_compressions", real_calls)
    mean_etco2_values = get_valid_values("mean_etco2", real_calls)
    max_etco2_values = get_valid_values("max_etco2", real_calls)

    # Calculate averages
    avg_depth_compliance = round(sum(depth_compliance) / len(depth_compliance), 1) if depth_compliance else 0
    avg_rate_compliance = round(sum(rate_compliance) / len(rate_compliance), 1) if rate_compliance else 0

    # Avg JcLS score from real-call sessions
    jcls_values_list = [s.get("metrics", {}).get("jcls_score") for s in real_calls
                        if s.get("metrics", {}).get("jcls_score") is not None]
    avg_jcls_score = round(sum(jcls_values_list) / len(jcls_values_list), 1) if jcls_values_list else None

    return {
        "session_count": len(sessions),
        "real_call_count": len(real_calls),
        "simulated_count": len(simulated),
        "arrests_attended": len(all_real_calls),  # Total cardiac arrests (including non-resuscitated)
        "avg_depth_compliance": avg_depth_compliance,
        "avg_rate_compliance": avg_rate_compliance,
        "avg_compression_rate": round(sum(compression_rates) / len(compression_rates), 1) if compression_rates else 0,
        "avg_compression_depth": round(sum(compression_depths) / len(compression_depths), 2) if compression_depths else 0,
        # Key metrics user requested
        "avg_ccf": round(sum(ccf_values) / len(ccf_values), 1) if ccf_values else 0,
        "avg_seconds_to_first_compression": round(sum(first_compression_times) / len(first_compression_times), 1) if first_compression_times else 0,
        "avg_seconds_to_first_shock": round(sum(first_shock_times) / len(first_shock_times), 1) if first_shock_times else 0,
        "avg_post_shock_pause": round(sum(post_shock_pauses) / len(post_shock_pauses), 1) if post_shock_pauses else 0,
        "total_compressions": sum(total_compressions_list) if total_compressions_list else 0,
        "avg_mean_etco2": round(sum(mean_etco2_values) / len(mean_etco2_values), 1) if mean_etco2_values else 0,
        "avg_max_etco2": round(sum(max_etco2_values) / len(max_etco2_values), 1) if max_etco2_values else 0,
        "avg_jcls_score": avg_jcls_score,
    }


def _calculate_stats_for_sessions(sessions: List[Dict], real_calls_only_for_advanced: bool = True):
    """
    Helper function to calculate stats for a given list of sessions.
    Used by get_provider_stats_detailed to avoid code duplication.
    """
    if not sessions:
        return {
            "session_count": 0,
            "real_call_count": 0,
            "simulated_count": 0,
            "avg_depth_compliance": 0,
            "avg_rate_compliance": 0,
            "avg_compression_rate": 0,
            "avg_compression_depth": 0,
            "avg_ccf": 0,
            "avg_seconds_to_first_compression": 0,
            "avg_seconds_to_first_shock": 0,
            "avg_post_shock_pause": 0,
            "total_compressions": 0,
            "avg_mean_etco2": 0,
            "avg_max_etco2": 0,
            "avg_jcls_score": None,
        }

    real_calls = [s for s in sessions if s.get("session_type") == "real_call"]
    simulated = [s for s in sessions if s.get("session_type") == "simulated"]

    def get_valid_values(key, from_sessions=None):
        source = from_sessions if from_sessions is not None else sessions
        values = []
        for s in source:
            val = s.get("metrics", {}).get(key)
            if val is not None and val != 0:
                values.append(val)
        return values

    # Basic metrics from all sessions
    depth_compliance = get_valid_values("correct_depth_percent")
    rate_compliance = get_valid_values("correct_rate_percent")
    compression_rates = get_valid_values("compression_rate")
    compression_depths = get_valid_values("compression_depth")

    # Advanced metrics only from real calls
    advanced_source = real_calls if real_calls_only_for_advanced else sessions
    ccf_values = get_valid_values("compression_fraction", advanced_source)
    first_compression_times = get_valid_values("seconds_to_first_compression", advanced_source)
    first_shock_times = get_valid_values("seconds_to_first_shock", advanced_source)
    post_shock_pauses = get_valid_values("avg_post_shock_pause", advanced_source)
    total_compressions_list = get_valid_values("total_compressions", advanced_source)
    mean_etco2_values = get_valid_values("mean_etco2", advanced_source)
    max_etco2_values = get_valid_values("max_etco2", advanced_source)

    avg_depth = round(sum(depth_compliance) / len(depth_compliance), 1) if depth_compliance else 0
    avg_rate = round(sum(rate_compliance) / len(rate_compliance), 1) if rate_compliance else 0

    jcls_vals = [s.get("metrics", {}).get("jcls_score") for s in sessions
                 if s.get("session_type") == "real_call" and s.get("metrics", {}).get("jcls_score") is not None]
    avg_jcls_score = round(sum(jcls_vals) / len(jcls_vals), 1) if jcls_vals else None

    return {
        "session_count": len(sessions),
        "real_call_count": len(real_calls),
        "simulated_count": len(simulated),
        "avg_depth_compliance": avg_depth,
        "avg_rate_compliance": avg_rate,
        "avg_compression_rate": round(sum(compression_rates) / len(compression_rates), 1) if compression_rates else 0,
        "avg_compression_depth": round(sum(compression_depths) / len(compression_depths), 2) if compression_depths else 0,
        "avg_ccf": round(sum(ccf_values) / len(ccf_values), 1) if ccf_values else 0,
        "avg_seconds_to_first_compression": round(sum(first_compression_times) / len(first_compression_times), 1) if first_compression_times else 0,
        "avg_seconds_to_first_shock": round(sum(first_shock_times) / len(first_shock_times), 1) if first_shock_times else 0,
        "avg_post_shock_pause": round(sum(post_shock_pauses) / len(post_shock_pauses), 1) if post_shock_pauses else 0,
        "total_compressions": sum(total_compressions_list) if total_compressions_list else 0,
        "avg_mean_etco2": round(sum(mean_etco2_values) / len(mean_etco2_values), 1) if mean_etco2_values else 0,
        "avg_max_etco2": round(sum(max_etco2_values) / len(max_etco2_values), 1) if max_etco2_values else 0,
        "avg_jcls_score": avg_jcls_score,
    }


def get_provider_stats_detailed(provider_id: str):
    """
    Get detailed stats for a provider with breakdowns:
    - as_lead: Stats from sessions where they were Team Lead
    - as_provider: Stats from sessions where they were a participant (not lead)
    - combined: Stats from all sessions they participated in
    - simulated: Stats from simulated sessions only

    Returns dict with these four stat breakdowns plus summary counts.
    Also includes cumulative shock/Joules statistics from real calls.
    """
    all_sessions = get_sessions_by_provider(provider_id, include_as_participant=True)

    # Separate by role
    lead_sessions = [s for s in all_sessions if s.get("provider_role") == "lead"]
    provider_sessions = [s for s in all_sessions if s.get("provider_role") == "provider"]
    simulated_sessions = [s for s in all_sessions if s.get("provider_role") == "individual"]
    real_sessions = [s for s in all_sessions if s.get("session_type") == "real_call"]

    # Calculate cumulative shocks from real calls
    total_shocks = 0
    for session in real_sessions:
        shocks = session.get("shocks_delivered")
        if shocks is not None and isinstance(shocks, (int, float)):
            total_shocks += int(shocks)

    # Calculate Joules and get fun comparison
    total_joules = total_shocks * JOULES_PER_SHOCK
    joules_comparison = get_joules_comparison(total_joules)

    return {
        "as_lead": _calculate_stats_for_sessions(lead_sessions),
        "as_provider": _calculate_stats_for_sessions(provider_sessions),
        "combined": _calculate_stats_for_sessions(all_sessions),
        "simulated": _calculate_stats_for_sessions(simulated_sessions),
        "real_calls_only": _calculate_stats_for_sessions(real_sessions),
        # Summary counts for quick reference
        "total_sessions": len(all_sessions),
        "lead_count": len(lead_sessions),
        "provider_count": len(provider_sessions),
        "simulated_count": len(simulated_sessions),
        "real_call_count": len(real_sessions),
        # Shock/Joules statistics
        "total_shocks": total_shocks,
        "total_joules": total_joules,
        "joules_comparison": joules_comparison["comparison"],
        "joules_icon": joules_comparison["icon"],
    }


def get_top_performers(limit: int = 3):
    """Get top performers by JcLS Score."""
    ranked = get_ranked_providers()
    return ranked[:limit]


def get_ranked_providers():
    """Get all active providers ranked by JcLS Score with their stats."""
    provider_stats = []
    for provider in PROVIDERS:
        if provider.get("status") != "active":
            continue
        stats = get_provider_stats(provider["id"])

        # Compute avg JcLS from real-call sessions
        real_sessions = [s for s in get_sessions_by_provider(provider["id"], include_as_participant=True)
                         if s.get("session_type") == "real_call"]
        jcls_values = [s.get("metrics", {}).get("jcls_score") for s in real_sessions
                       if s.get("metrics", {}).get("jcls_score") is not None]
        avg_jcls = round(sum(jcls_values) / len(jcls_values), 1) if jcls_values else None

        provider_stats.append({
            "id": provider["id"],
            "name": provider["name"],
            "team_id": provider.get("team_id"),
            "certification": provider.get("certification"),
            "avg_jcls_score": avg_jcls,
            "avg_depth_compliance": stats["avg_depth_compliance"],
            "avg_rate_compliance": stats["avg_rate_compliance"],
            "avg_compression_rate": stats["avg_compression_rate"],
            "avg_compression_depth": stats["avg_compression_depth"],
            "session_count": stats["session_count"]
        })

    # Sort by JcLS score descending (providers with sessions first, then by jcls, then depth)
    provider_stats.sort(key=lambda x: (x["session_count"] > 0, x.get("avg_jcls_score") or 0, x["avg_depth_compliance"]), reverse=True)
    return provider_stats


def get_ranked_providers_by_type(session_type: str = "all"):
    """
    Get active providers ranked by JcLS Score, filtered by session type.

    Args:
        session_type: "real_call", "simulated", or "all"

    Returns list of providers with stats calculated only from matching sessions.
    """
    provider_stats = []

    for provider in PROVIDERS:
        if provider.get("status") != "active":
            continue

        # Get all sessions for this provider
        all_sessions = get_sessions_by_provider(provider["id"], include_as_participant=True)

        # Filter by session type
        if session_type == "real_call":
            sessions = [s for s in all_sessions if s.get("session_type") == "real_call"]
        elif session_type == "simulated":
            sessions = [s for s in all_sessions if s.get("session_type") == "simulated" or s.get("event_type") == "Simulated"]
        else:
            sessions = all_sessions

        if not sessions:
            continue  # Skip providers with no sessions of this type

        # Calculate stats from filtered sessions
        depth_values = [s.get("metrics", {}).get("correct_depth_percent", 0) for s in sessions if s.get("metrics")]
        rate_values = [s.get("metrics", {}).get("correct_rate_percent", 0) for s in sessions if s.get("metrics")]
        ccf_values = [s.get("metrics", {}).get("compression_fraction", 0) for s in sessions if s.get("metrics") and s.get("metrics", {}).get("compression_fraction")]

        avg_depth = round(sum(depth_values) / len(depth_values), 1) if depth_values else 0
        avg_rate = round(sum(rate_values) / len(rate_values), 1) if rate_values else 0
        avg_ccf = round(sum(ccf_values) / len(ccf_values), 1) if ccf_values else 0

        # Compute avg JcLS for real-call sessions
        jcls_values = [s.get("metrics", {}).get("jcls_score") for s in sessions
                       if s.get("metrics", {}).get("jcls_score") is not None]
        avg_jcls = round(sum(jcls_values) / len(jcls_values), 1) if jcls_values else None

        provider_stats.append({
            "id": provider["id"],
            "name": provider["name"],
            "certification": provider.get("certification"),
            "avg_jcls_score": avg_jcls,
            "avg_depth_compliance": avg_depth,
            "avg_rate_compliance": avg_rate,
            "avg_ccf": avg_ccf,
            "session_count": len(sessions),
        })

    # Sort by JcLS score descending (with fallback to depth compliance)
    provider_stats.sort(key=lambda x: (x.get("avg_jcls_score") or 0, x["avg_depth_compliance"]), reverse=True)

    # Add rank numbers
    for i, provider in enumerate(provider_stats, 1):
        provider["rank"] = i

    return provider_stats


def get_real_call_teams(sort_by: str = "jcls_score"):
    """
    Get teams from real-life calls.
    Each real call with participants forms a "team instance" - one event = one team entry.
    Returns ranked list of teams based on JcLS score.

    Args:
        sort_by: Field to sort by. Options:
            - "jcls_score" (default): JcLS Score
            - "ccf": Compression Fraction
            - "depth_compliance": Depth %
            - "rate_compliance": Rate %
            - "total_compressions": Total compressions
            - "date": Most recent first

    Returns list of team instances with full metrics and ranking.
    """
    from app.models import SessionType

    # Find all real-life call sessions with metrics
    real_calls = [
        s for s in SESSIONS
        if (s.get("session_type") == SessionType.REAL_CALL.value or
            s.get("session_type") == "real_call" or
            (s.get("event_type") and s.get("event_type") != "Simulated"))
        and s.get("metrics")
        and (s.get("status") == "complete" or s.get("metrics", {}).get("correct_depth_percent") is not None)
    ]

    teams = []
    for session in real_calls:
        # Get team lead (primary provider)
        team_lead_name = session.get("provider_name") or "Unknown Team"
        team_lead_id = session.get("provider_id")

        # Get team members from participants
        participants = session.get("participants", [])
        providers = []  # Non-lead participants
        for p in participants:
            if not p.get("is_primary"):
                providers.append({
                    "id": p.get("provider_id"),
                    "name": p.get("provider_name", "Unknown")
                })

        # Build member list string for display
        if participants:
            all_members = [p.get("provider_name", "Unknown") for p in participants]
            members_str = ", ".join(all_members)
        else:
            members_str = team_lead_name

        # Get metrics
        metrics = session.get("metrics", {})
        depth_compliance = metrics.get("correct_depth_percent", 0) or 0
        rate_compliance = metrics.get("correct_rate_percent", 0) or 0
        ccf = metrics.get("compression_fraction", 0) or 0
        total_compressions = metrics.get("total_compressions", 0) or 0
        jcls_score = metrics.get("jcls_score")

        # Determine CCF status for visual indication
        if ccf >= 85:
            ccf_status = "excellent"
        elif ccf >= 60:
            ccf_status = "warning"
        elif ccf > 0:
            ccf_status = "critical"
        else:
            ccf_status = "unknown"

        teams.append({
            "id": session.get("id"),
            "session_id": session.get("id"),
            "team_lead": team_lead_name,
            "team_lead_id": team_lead_id,
            "providers": providers,  # List of non-lead providers
            "members": members_str,  # Full string of all participants
            "member_count": len(participants) if participants else 1,
            "provider_count": len(providers),
            "date": session.get("date"),
            "event_type": session.get("event_type"),
            # Scores
            "jcls_score": jcls_score,
            "ccf": ccf,
            "ccf_status": ccf_status,
            "depth_compliance": depth_compliance,
            "rate_compliance": rate_compliance,
            # Additional metrics
            "compression_rate": metrics.get("compression_rate"),
            "total_compressions": total_compressions,
            "duration": metrics.get("duration"),
            "seconds_to_first_compression": metrics.get("seconds_to_first_compression"),
            "mean_etco2": metrics.get("mean_etco2"),
        })

    # Sort based on requested field
    sort_key_map = {
        "jcls_score": lambda x: x.get("jcls_score") or 0,
        "ccf": lambda x: x["ccf"],
        "depth_compliance": lambda x: x["depth_compliance"],
        "rate_compliance": lambda x: x["rate_compliance"],
        "total_compressions": lambda x: x["total_compressions"],
        "date": lambda x: x["date"] or "",
    }

    sort_key = sort_key_map.get(sort_by, sort_key_map["jcls_score"])
    teams.sort(key=sort_key, reverse=True)

    # Add rank numbers
    for i, team in enumerate(teams, 1):
        team["rank"] = i

    return teams


# For backwards compatibility
DASHBOARD_KPIS = get_dashboard_kpis()


def reinitialize():
    """Reload all in-memory data from disk. Called when switching services.

    Uses in-place mutation (clear + extend) instead of rebinding so that
    all modules holding references via 'from mock_data import SESSIONS'
    see the updated data.
    """
    global PROVIDER_BY_NAME, DASHBOARD_KPIS

    PROVIDERS.clear()
    PROVIDERS.extend(load_providers())
    PROVIDER_BY_NAME = {p["name"]: p["id"] for p in PROVIDERS}

    SESSIONS.clear()
    SESSIONS.extend(_initialize_sessions())

    DASHBOARD_KPIS = get_dashboard_kpis()


# Date range presets - reference list for dropdowns
DATE_RANGE_PRESETS = [
    {"value": "7d", "label": "Last 7 days"},
    {"value": "30d", "label": "Last 30 days"},
    {"value": "90d", "label": "Last 90 days"},
    {"value": "month", "label": "This month"},
    {"value": "year", "label": "This year"},
    {"value": "all", "label": "All time"},
]
