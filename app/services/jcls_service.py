"""
JcLS Scoring Service — Jordan's Clinical Scoring for CPR Quality.

100-point evidence-based rubric. Weights derived from published adjusted
odds ratios for neurologically intact survival (CPC 1-2) from OHCA research.

Two public functions:
  calculate_jcls_score()  — pure calculation, no side effects
  backfill_jcls_scores()  — one-time migration for existing sessions
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ── Scoring Band Definitions ──

def _score_depth_compliance(value: Optional[float]) -> tuple[int, int]:
    """Tier 1A: Depth Compliance (20 pts). Source: correct_depth_percent."""
    if value is None:
        return 0, 0  # earned, max (excluded)
    if value >= 80:
        return 20, 20
    if value >= 65:
        return 16, 20
    if value >= 50:
        return 12, 20
    if value >= 35:
        return 7, 20
    return 3, 20


def _score_rate_compliance(value: Optional[float]) -> tuple[int, int]:
    """Tier 1B: Rate Compliance (15 pts). Source: correct_rate_percent."""
    if value is None:
        return 0, 0
    if value >= 85:
        return 15, 15
    if value >= 70:
        return 12, 15
    if value >= 55:
        return 8, 15
    if value >= 40:
        return 4, 15
    return 1, 15


def _score_combined_compliance(value: Optional[float]) -> tuple[int, int]:
    """Tier 1C: Combined Compliance / CiT (20 pts). Source: compressions_in_target_percent."""
    if value is None:
        return 0, 0
    if value >= 60:
        return 20, 20
    if value >= 45:
        return 16, 20
    if value >= 35:
        return 12, 20
    if value >= 25:
        return 7, 20
    return 3, 20


def _score_ccf(value: Optional[float]) -> tuple[int, int]:
    """Tier 2A: CCF (15 pts). Source: compression_fraction."""
    if value is None:
        return 0, 0
    if value >= 85:
        return 15, 15
    if value >= 80:
        return 12, 15
    if value >= 70:
        return 8, 15
    if value >= 60:
        return 4, 15
    return 1, 15


def _score_pause_mean(value: Optional[float]) -> tuple[int, int]:
    """Tier 2B sub-score A: Mean pause duration (6 pts)."""
    if value is None:
        return 0, 0
    if value <= 4.0:
        return 6, 6
    if value <= 6.0:
        return 4, 6
    if value <= 8.0:
        return 2, 6
    return 0, 6


def _score_pause_long(pauses_over_10s: Optional[int]) -> tuple[int, int]:
    """Tier 2B sub-score B: No pauses >10s (4 pts)."""
    if pauses_over_10s is None:
        return 0, 0
    if pauses_over_10s == 0:
        return 4, 4
    if pauses_over_10s == 1:
        return 2, 4
    return 0, 4


def _score_release_velocity(
    mean_vel: Optional[float], std_dev: Optional[float]
) -> tuple[int, int]:
    """Tier 3A: Release Velocity (10 pts)."""
    if mean_vel is None:
        return 0, 0
    if mean_vel >= 400 and std_dev is not None and std_dev < 100:
        return 10, 10
    if mean_vel >= 400:
        return 8, 10
    if mean_vel >= 350:
        return 6, 10
    if mean_vel >= 300:
        return 3, 10
    return 1, 10


def _score_time_to_first_compression(value: Optional[float]) -> tuple[int, int]:
    """Tier 4A: Time to First Compression (5 pts)."""
    if value is None:
        return 0, 0
    if value <= 30:
        return 5, 5
    if value <= 60:
        return 4, 5
    if value <= 90:
        return 2, 5
    return 0, 5


def _score_time_to_first_shock(
    value: Optional[float], shocks_delivered: Optional[int]
) -> tuple[int, int]:
    """Tier 4B: Time to First Shock (5 pts). Non-shockable = 3 pts neutral."""
    if value is None:
        # No shock data — check if non-shockable (neutral 3 pts)
        if shocks_delivered is not None and shocks_delivered == 0:
            return 3, 5
        # Truly missing data — exclude
        return 0, 0
    if value <= 120:
        return 5, 5
    if value <= 180:
        return 3, 5
    return 1, 5


# ── Color Band ──

def _color_band(score: int) -> str:
    """Return color band: 'green', 'yellow', or 'red'."""
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"


# ── Main Calculation ──

def calculate_jcls_score(
    metrics: Dict[str, Any],
    shocks_delivered: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calculate JcLS Score from session metrics.

    Args:
        metrics: Flat dict of session metric values (same keys as SessionMetrics).
        shocks_delivered: From session object (not in metrics dict).

    Returns:
        Full breakdown dict with jcls_score, color_band, tier breakdowns,
        available_points, and raw_score.
    """
    # ── Tier 1: Compression Quality (55 pts) ──
    depth_earned, depth_max = _score_depth_compliance(
        metrics.get("correct_depth_percent")
    )
    rate_earned, rate_max = _score_rate_compliance(
        metrics.get("correct_rate_percent")
    )
    combined_earned, combined_max = _score_combined_compliance(
        metrics.get("compressions_in_target_percent")
    )

    tier1_earned = depth_earned + rate_earned + combined_earned
    tier1_max = depth_max + rate_max + combined_max

    # ── Tier 2: Perfusion Continuity (25 pts) ──
    ccf_earned, ccf_max = _score_ccf(
        metrics.get("compression_fraction")
    )
    pause_mean_earned, pause_mean_max = _score_pause_mean(
        metrics.get("mean_pause_duration")
    )
    pause_long_earned, pause_long_max = _score_pause_long(
        metrics.get("pauses_over_10s")
    )

    pause_earned = pause_mean_earned + pause_long_earned
    pause_max = pause_mean_max + pause_long_max
    tier2_earned = ccf_earned + pause_earned
    tier2_max = ccf_max + pause_max

    # ── Tier 3: Recoil Quality (10 pts) ──
    rv_earned, rv_max = _score_release_velocity(
        metrics.get("mean_release_velocity"),
        metrics.get("release_velocity_std_dev"),
    )

    tier3_earned = rv_earned
    tier3_max = rv_max

    # ── Tier 4: System Performance (10 pts) ──
    ttfc_earned, ttfc_max = _score_time_to_first_compression(
        metrics.get("seconds_to_first_compression")
    )
    ttfs_earned, ttfs_max = _score_time_to_first_shock(
        metrics.get("seconds_to_first_shock"),
        shocks_delivered,
    )

    tier4_earned = ttfc_earned + ttfs_earned
    tier4_max = ttfc_max + ttfs_max

    # ── Totals ──
    raw_score = tier1_earned + tier2_earned + tier3_earned + tier4_earned
    available_points = tier1_max + tier2_max + tier3_max + tier4_max

    if available_points > 0:
        scaled_score = round(raw_score / available_points * 100)
    else:
        scaled_score = 0

    return {
        "jcls_score": scaled_score,
        "color_band": _color_band(scaled_score),
        "raw_score": raw_score,
        "available_points": available_points,
        "tier1": {
            "name": "Compression Quality",
            "earned": tier1_earned,
            "max": tier1_max,
            "depth_compliance": {
                "value": metrics.get("correct_depth_percent"),
                "earned": depth_earned,
                "max": depth_max,
            },
            "rate_compliance": {
                "value": metrics.get("correct_rate_percent"),
                "earned": rate_earned,
                "max": rate_max,
            },
            "combined_compliance": {
                "value": metrics.get("compressions_in_target_percent"),
                "earned": combined_earned,
                "max": combined_max,
            },
        },
        "tier2": {
            "name": "Perfusion Continuity",
            "earned": tier2_earned,
            "max": tier2_max,
            "ccf": {
                "value": metrics.get("compression_fraction"),
                "earned": ccf_earned,
                "max": ccf_max,
            },
            "pause_quality": {
                "earned": pause_earned,
                "max": pause_max,
                "mean_pause": {
                    "value": metrics.get("mean_pause_duration"),
                    "earned": pause_mean_earned,
                    "max": pause_mean_max,
                },
                "no_long_pauses": {
                    "value": metrics.get("pauses_over_10s"),
                    "earned": pause_long_earned,
                    "max": pause_long_max,
                },
            },
        },
        "tier3": {
            "name": "Recoil Quality",
            "earned": tier3_earned,
            "max": tier3_max,
            "release_velocity": {
                "value": metrics.get("mean_release_velocity"),
                "sd": metrics.get("release_velocity_std_dev"),
                "earned": rv_earned,
                "max": rv_max,
            },
        },
        "tier4": {
            "name": "System Performance",
            "earned": tier4_earned,
            "max": tier4_max,
            "time_to_first_compression": {
                "value": metrics.get("seconds_to_first_compression"),
                "earned": ttfc_earned,
                "max": ttfc_max,
            },
            "time_to_first_shock": {
                "value": metrics.get("seconds_to_first_shock"),
                "shocks_delivered": shocks_delivered,
                "earned": ttfs_earned,
                "max": ttfs_max,
            },
        },
    }


# ── Backfill ──

def backfill_jcls_scores() -> int:
    """
    Scan all real-call sessions. If jcls_score is missing from metrics,
    calculate and persist. Returns count of sessions updated.

    Called once on service activation (login). No-op on subsequent calls
    since all sessions will already have scores.
    """
    from app.mock_data import SESSIONS, _save_user_sessions

    updated = 0
    for session in SESSIONS:
        if session.get("session_type") != "real_call":
            continue
        if session.get("status") != "complete":
            continue

        metrics = session.get("metrics")
        if not metrics or not isinstance(metrics, dict):
            continue

        # Skip if already scored
        if metrics.get("jcls_score") is not None:
            continue

        result = calculate_jcls_score(
            metrics,
            shocks_delivered=session.get("shocks_delivered"),
        )
        metrics["jcls_score"] = result["jcls_score"]
        metrics["jcls_breakdown"] = result
        updated += 1

    if updated > 0:
        _save_user_sessions()
        logger.info(f"JcLS backfill: scored {updated} session(s)")

    return updated
