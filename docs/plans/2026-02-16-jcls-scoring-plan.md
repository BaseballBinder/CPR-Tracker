# JcLS Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the JcLS Score — a 100-point evidence-based CPR quality rubric — as the primary quality metric for real-call sessions, with full UI integration.

**Architecture:** Standalone scoring service (`jcls_service.py`) called from the ingestion pipeline and a one-time backfill. IndividualPauses.csv parser added to existing ingestion service. Dashboard, session detail, and session list templates updated.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Jinja2 + HTMX + Alpine.js, Tailwind CSS, JSON file persistence.

**Design Doc:** `docs/plans/2026-02-16-jcls-scoring-design.md`

---

### Task 1: Extend SessionMetrics Model

**Files:**
- Modify: `app/models.py:172` (after `cr_secun10` field)

**Step 1: Add new fields to SessionMetrics**

After line 172 (`cr_secun10: Optional[float] = None`), add:

```python
    # ── Pause metrics (from IndividualPauses.csv) ──
    pause_count: Optional[int] = None
    mean_pause_duration: Optional[float] = None  # seconds
    max_pause_duration: Optional[float] = None   # seconds
    pauses_over_10s: Optional[int] = None

    # ── JcLS Score (real-call only) ──
    jcls_score: Optional[int] = None             # 0-100, scaled
    jcls_breakdown: Optional[Dict[str, Any]] = None  # full tier breakdown
```

Add `Dict, Any` to the typing imports at the top of the file if not already present.

**Step 2: Verify model loads without error**

Run: `cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python -c "from app.models import SessionMetrics; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/models.py
git commit -m "feat: add pause metrics and jcls_score fields to SessionMetrics"
```

---

### Task 2: Create JcLS Scoring Service

**Files:**
- Create: `app/services/jcls_service.py`

**Step 1: Create the scoring module**

```python
"""
JcLS Scoring Service — Jordan's Clinical Scoring for CPR Quality.

100-point evidence-based rubric. Weights derived from published adjusted
odds ratios for neurologically intact survival (CPC 1-2) from OHCA research.

Two public functions:
  calculate_jcls_score()  — pure calculation, no side effects
  backfill_jcls_scores()  — one-time migration for existing sessions
"""
from typing import Any, Dict, List, Optional
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
```

**Step 2: Verify module imports**

Run: `cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python -c "from app.services.jcls_service import calculate_jcls_score; print('OK')"`
Expected: `OK`

**Step 3: Verify scoring with sample data**

Run:
```bash
cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python -c "
from app.services.jcls_service import calculate_jcls_score
result = calculate_jcls_score({
    'correct_depth_percent': 53.5,
    'correct_rate_percent': 87.4,
    'compressions_in_target_percent': 47.7,
    'compression_fraction': 93.6,
    'mean_pause_duration': 6.4,
    'pauses_over_10s': 0,
    'mean_release_velocity': 394.6,
    'release_velocity_std_dev': 87.2,
    'seconds_to_first_compression': 93.4,
    'seconds_to_first_shock': None,
}, shocks_delivered=0)
print(f\"Score: {result['jcls_score']}, Raw: {result['raw_score']}/{result['available_points']}\")
print(f\"T1: {result['tier1']['earned']}/{result['tier1']['max']}\")
print(f\"T2: {result['tier2']['earned']}/{result['tier2']['max']}\")
print(f\"T3: {result['tier3']['earned']}/{result['tier3']['max']}\")
print(f\"T4: {result['tier4']['earned']}/{result['tier4']['max']}\")
"
```

Expected output (verify manually):
- Depth 53.5% → 12/20
- Rate 87.4% → 15/15
- CiT 47.7% → 16/20
- CCF 93.6% → 15/15
- Pause mean 6.4s → 2/6, no pauses >10s → 4/4 = 6/10
- Release 394.6mm/s SD 87.2 → 6/10 (350-399 band, SD irrelevant for this band)
- TTFC 93.4s → 0/5
- TTFS None, 0 shocks → 3/5 (neutral)
- Raw: 12+15+16+15+6+6+0+3 = 73, Available: 100, Scaled: 73

**Step 4: Commit**

```bash
git add app/services/jcls_service.py
git commit -m "feat: create JcLS scoring service with calculate and backfill functions"
```

---

### Task 3: Parse IndividualPauses.csv

**Files:**
- Modify: `app/services/ingestion_service.py:197-200` (insert pause parsing into ingest_zip flow)

**Step 1: Add the pause parser method to IngestionService**

Add this method to the `IngestionService` class (after `_parse_case_statistics` or `_parse_minute_by_minute`):

```python
    def _parse_individual_pauses(self, content: str) -> Dict[str, Any]:
        """
        Parse IndividualPauses.csv for pause quality metrics.

        Reads 'Total pause duration (sec)' column.
        Returns dict with pause_count, mean_pause_duration, max_pause_duration,
        pauses_over_10s. All values None if file is empty or column missing.
        """
        empty = {
            "pause_count": None,
            "mean_pause_duration": None,
            "max_pause_duration": None,
            "pauses_over_10s": None,
        }

        try:
            reader = csv.DictReader(io.StringIO(content))
            durations = []

            for row in reader:
                raw = row.get("Total pause duration (sec)")
                if raw is None:
                    # Column not found — return empty
                    return empty
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    durations.append(float(raw))
                except ValueError:
                    logger.warning(f"IndividualPauses: skipping non-numeric duration: {raw}")

            if not durations:
                return empty

            return {
                "pause_count": len(durations),
                "mean_pause_duration": round(sum(durations) / len(durations), 2),
                "max_pause_duration": round(max(durations), 2),
                "pauses_over_10s": sum(1 for d in durations if d > 10.0),
            }
        except Exception as e:
            logger.warning(f"IndividualPauses parsing failed: {e}")
            return empty
```

Ensure `csv` and `io` are imported at the top of the file (they likely already are for the existing CSV parsers).

**Step 2: Wire pause parsing into ingest_zip**

In `ingest_zip()`, after line 197 (`pco_metrics = self._compute_pco_metrics_weighted(minute_data)`) and before line 199 (`metrics_dict = {**summary_metrics, **pco_metrics}`), insert:

```python
                # ===== Parse IndividualPauses.csv for pause quality metrics =====
                pause_metrics = {"pause_count": None, "mean_pause_duration": None,
                                 "max_pause_duration": None, "pauses_over_10s": None}
                pauses_csv_name = self._find_authoritative_csv(file_list, "IndividualPauses.csv")
                if pauses_csv_name:
                    with zf.open(pauses_csv_name) as f:
                        pauses_content = f.read().decode('utf-8-sig')
                    pause_metrics = self._parse_individual_pauses(pauses_content)
```

Then update the metrics_dict merge on line 199 to include pause data:

```python
                metrics_dict = {**summary_metrics, **pco_metrics, **pause_metrics}
```

**Step 3: Verify import still works**

Run: `cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python -c "from app.services.ingestion_service import IngestionService; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add app/services/ingestion_service.py
git commit -m "feat: parse IndividualPauses.csv for pause quality metrics"
```

---

### Task 4: Integrate JcLS Scoring into Ingestion Pipeline

**Files:**
- Modify: `app/services/ingestion_service.py` (after pause parsing, before return)
- Modify: `app/services/session_service.py` (pass shocks_delivered through)

**Step 1: Add JcLS calculation to ingest_zip**

In `ingest_zip()`, after the pause parsing block added in Task 3 and after `metrics_dict = {**summary_metrics, **pco_metrics, **pause_metrics}`, add:

```python
                # ===== Calculate JcLS Score (will be stored with metrics) =====
                # Note: shocks_delivered is not available here (comes from session).
                # We store partial score; backfill adds shock context on first login.
                # For new imports, the API route passes shocks_delivered after creation.
```

Actually, looking at the flow more carefully: `ingest_zip()` returns `(metrics_dict, pco_payload)`, and the caller (`session_service.mark_session_complete`) stores the metrics. The session already has `shocks_delivered` set from the wizard. So we need to calculate JcLS in the **API route** that calls both, not inside `ingest_zip()`.

Find the API route that orchestrates ingestion. In `app/routers/api.py`, find where `ingest_zip` is called and `mark_session_complete` follows. Add JcLS calculation between them:

```python
# After: metrics_dict, pco_payload = ingestion.ingest_zip(zip_path)
# Before: session_service.mark_session_complete(session_id, metrics_dict, ...)

# Calculate JcLS score for real-call sessions
session = session_service.get_session(session_id)
if session and session.get("session_type") == "real_call":
    from app.services.jcls_service import calculate_jcls_score
    jcls_result = calculate_jcls_score(
        metrics_dict,
        shocks_delivered=session.get("shocks_delivered"),
    )
    metrics_dict["jcls_score"] = jcls_result["jcls_score"]
    metrics_dict["jcls_breakdown"] = jcls_result
```

Read `app/routers/api.py` to find the exact location. Search for `ingest_zip` calls and `mark_session_complete` calls.

**Step 2: Verify the app starts without errors**

Run: `cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python -c "from app.main import app; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/routers/api.py
git commit -m "feat: calculate JcLS score during session import"
```

---

### Task 5: Wire Backfill into Service Activation

**Files:**
- Modify: `app/service_context.py:94-97` (in `_reinitialize_data`)

**Step 1: Add backfill call after data reload**

In `_reinitialize_data()` (line 94), after `mock_data.reinitialize()`:

```python
def _reinitialize_data() -> None:
    """Reload all in-memory data from the active service's directory."""
    from app import mock_data
    mock_data.reinitialize()

    # Backfill JcLS scores for any real-call sessions missing them
    from app.services.jcls_service import backfill_jcls_scores
    backfill_jcls_scores()
```

**Step 2: Verify service activation still works**

Run: `cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python -c "from app.service_context import _reinitialize_data; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add app/service_context.py
git commit -m "feat: backfill JcLS scores on service activation"
```

---

### Task 6: Update Dashboard KPIs

**Files:**
- Modify: `app/mock_data.py` (in `get_dashboard_kpis()` around lines 522-617)

**Step 1: Add JcLS-related KPI calculations**

In `get_dashboard_kpis()`, after computing real-call metrics, add:

```python
    # JcLS averages (real calls only)
    jcls_scores = []
    combined_compliance_values = []
    release_velocity_values = []
    release_velocity_sd_values = []

    for s in real_sessions:
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
```

Add these to the return dict:

```python
    "avg_jcls_score": avg_jcls,
    "avg_jcls_color": "green" if avg_jcls and avg_jcls >= 80 else ("yellow" if avg_jcls and avg_jcls >= 60 else "red") if avg_jcls else None,
    "avg_combined_compliance": avg_combined,
    "avg_release_velocity": avg_rv,
    "avg_release_velocity_sd": avg_rv_sd,
```

**Step 2: Update Top Performers to use JcLS**

In `get_ranked_providers_by_type()` (around line 896), for real-call rankings, add `jcls_score` to the returned provider stats. For the sorting, change the sort key from `quality_score` to `jcls_score` (with fallback to 0 for providers without JcLS data):

```python
# For real-call rankings:
provider_stats.sort(key=lambda x: (x["session_count"] > 0, x.get("avg_jcls_score") or 0), reverse=True)
```

This requires computing `avg_jcls_score` per provider. In the provider stats loop, add:

```python
jcls_values = [s.get("metrics", {}).get("jcls_score") for s in provider_sessions if s.get("metrics", {}).get("jcls_score") is not None]
avg_jcls = round(sum(jcls_values) / len(jcls_values), 1) if jcls_values else None
```

And include `"avg_jcls_score": avg_jcls` in the provider stats dict.

**Step 3: Commit**

```bash
git add app/mock_data.py
git commit -m "feat: add JcLS KPIs and update provider rankings"
```

---

### Task 7: Update Dashboard Template — KPI Cards

**Files:**
- Modify: `templates/pages/dashboard.html:10-54` (KPI card grid)

**Step 1: Reorder primary KPI cards**

Replace the existing 4-card KPI grid (lines 10-54) with:

Card 1: **JcLS Score** (hero)
```html
{% set stat_label = "JcLS Score" %}
{% set stat_value = kpis.avg_jcls_score if kpis.avg_jcls_score else "--" %}
{% set stat_icon = "heart" %}
{% set stat_icon_bg = "bg-red-900/20" %}
{% set stat_icon_color = "text-[#dc2626]" %}
```

Card 2: **CCF**
```html
{% set stat_label = "Avg CCF" %}
{% set stat_value = (kpis.real_ccf ~ "%") if kpis.real_ccf else "--" %}
{% set stat_icon = "chart" %}
{% set stat_icon_bg = "bg-green-900/20" %}
{% set stat_icon_color = "text-[#16a34a]" %}
{% set stat_trend_label = "Target: ≥80%" %}
```

Card 3: **Total Sessions** — keep as-is.

Card 4: **Active Providers** — keep as-is.

**Step 2: Add secondary KPI row**

After the primary KPI grid, add a new 3-column grid:

```html
{# Secondary KPI Row #}
<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
    {# Combined Compliance (CiT) #}
    <div class="bg-[#2c2729] rounded-[6px] p-4 border border-[rgba(255,255,255,0.10)] shadow-sm">
        <p class="text-sm font-medium text-slate-400">Combined Compliance (CiT)</p>
        <p class="text-2xl font-semibold text-slate-100 mt-1">
            {{ (kpis.avg_combined_compliance ~ "%") if kpis.avg_combined_compliance else "--" }}
        </p>
        <p class="text-xs text-slate-500 mt-1">Industry avg: ~35%</p>
    </div>

    {# Release Velocity #}
    <div class="bg-[#2c2729] rounded-[6px] p-4 border border-[rgba(255,255,255,0.10)] shadow-sm">
        <p class="text-sm font-medium text-slate-400">Release Velocity</p>
        <p class="text-2xl font-semibold mt-1
            {% if kpis.avg_release_velocity and kpis.avg_release_velocity >= 400 %}text-green-400
            {% elif kpis.avg_release_velocity and kpis.avg_release_velocity >= 350 %}text-yellow-400
            {% elif kpis.avg_release_velocity %}text-red-400
            {% else %}text-slate-100{% endif %}">
            {{ (kpis.avg_release_velocity ~ " mm/s") if kpis.avg_release_velocity else "--" }}
        </p>
        {% if kpis.avg_release_velocity_sd %}
        <p class="text-xs text-slate-500 mt-1">SD: {{ kpis.avg_release_velocity_sd }} mm/s</p>
        {% endif %}
    </div>

    {# ZOLL Quality Score #}
    <div class="bg-[#2c2729] rounded-[6px] p-4 border border-[rgba(255,255,255,0.10)] shadow-sm">
        <p class="text-sm font-medium text-slate-500">ZOLL Quality Score</p>
        <p class="text-2xl font-semibold text-slate-400 mt-1">
            {{ (kpis.avg_quality_score ~ "%") if kpis.avg_quality_score else "--" }}
        </p>
        <p class="text-xs text-slate-500 mt-1">ZOLL proprietary metric</p>
    </div>
</div>
```

**Step 3: Update Top Performers to show JcLS**

In the Top Performers section (lines 332-416), change the score display from `{{ performer.quality_score }}%` to show JcLS with a colored dot:

```html
<div class="flex items-center gap-2">
    {% if performer.avg_jcls_score %}
    <span class="w-2 h-2 rounded-full
        {% if performer.avg_jcls_score >= 80 %}bg-green-500
        {% elif performer.avg_jcls_score >= 60 %}bg-yellow-500
        {% else %}bg-red-500{% endif %}"></span>
    <span class="text-sm text-slate-300">{{ performer.avg_jcls_score }}</span>
    {% else %}
    <span class="text-sm text-slate-500">--</span>
    {% endif %}
</div>
```

**Step 4: Commit**

```bash
git add templates/pages/dashboard.html
git commit -m "feat: update dashboard KPIs with JcLS score and secondary metrics"
```

---

### Task 8: Add JcLS Tab to Session Detail Modal

**Files:**
- Modify: `templates/partials/sessions/detail_modal.html`

**Step 1: Add JcLS tab button**

In the tab navigation section (around line 108), add a new tab button as the FIRST tab, before "Overview". Only show for real-call sessions:

```html
{% if session.session_type == 'real_call' and session.metrics.jcls_breakdown %}
<button @click="activeTab = 'jcls'"
        :class="activeTab === 'jcls' ? 'border-[#dc2626] text-[#dc2626]' : 'border-transparent text-slate-400 hover:text-slate-200'"
        class="py-3 text-sm font-medium border-b-2 transition-colors">
    JcLS Score
</button>
{% endif %}
```

Change the default `activeTab` value in the Alpine x-data from `'overview'` to:
```
activeTab: '{{ "jcls" if session.session_type == "real_call" and session.metrics.jcls_breakdown else "overview" }}'
```

**Step 2: Add JcLS tab content**

Before the Overview tab content div, add the JcLS Score breakdown panel. This is a substantial template — render the hero score, then 4 tier cards with sub-metric rows. Use the `session.metrics.jcls_breakdown` dict for all values.

Key elements:
- Hero: large score number with colored background
- Per-tier: card with progress bar, earned/max, sub-metric rows
- Star indicator for full marks (earned == max and max > 0)
- "N/A" with gray text for missing metrics (max == 0)
- ZOLL Quality Score reference at bottom

Use the existing Ember Dark theme colors (`bg-[#2c2729]`, `border-[rgba(255,255,255,0.10)]`, etc.) and match the existing tab content styling patterns.

**Step 3: Commit**

```bash
git add templates/partials/sessions/detail_modal.html
git commit -m "feat: add JcLS Score breakdown tab to session detail modal"
```

---

### Task 9: Add JcLS Badge to Session Tables

**Files:**
- Modify: `templates/partials/sessions/table.html` (main sessions table)
- Modify: `templates/partials/dashboard/recent_sessions.html` (dashboard recent table)

**Step 1: Add JcLS column to sessions table**

In `templates/partials/sessions/table.html`, add a `<th>` for "JcLS" after the existing columns (before "Actions"):

```html
<th class="px-4 py-3 font-medium">JcLS</th>
```

In the data rows, add the corresponding `<td>`:

```html
<td class="px-4 py-3">
    {% if session.metrics.jcls_score is not none %}
    <div class="flex items-center gap-1.5">
        <span class="w-2 h-2 rounded-full flex-shrink-0
            {% if session.metrics.jcls_score >= 80 %}bg-green-500
            {% elif session.metrics.jcls_score >= 60 %}bg-yellow-500
            {% else %}bg-red-500{% endif %}"></span>
        <span class="text-sm text-slate-200">{{ session.metrics.jcls_score }}</span>
    </div>
    {% else %}
    <span class="text-slate-500">—</span>
    {% endif %}
</td>
```

**Step 2: Add JcLS column to dashboard recent sessions**

Same pattern in `templates/partials/dashboard/recent_sessions.html` — add `<th>JcLS</th>` and the colored dot + number `<td>`.

**Step 3: Add JcLS to the inline recent sessions table in dashboard.html**

The dashboard page at lines 489-514 has an inline recent sessions table. Add the JcLS column there too with the same pattern.

**Step 4: Commit**

```bash
git add templates/partials/sessions/table.html templates/partials/dashboard/recent_sessions.html templates/pages/dashboard.html
git commit -m "feat: add JcLS badge column to session tables"
```

---

### Task 10: End-to-End Verification

**Step 1: Start the app and verify it loads**

Run: `cd "C:\Users\secre\Desktop\High Efficiency CPR\CPR Program" && venv/Scripts/python desktop.py`

Navigate through:
- Landing page loads
- Login to a service
- Dashboard loads without errors
- Sessions page loads
- Click a real-call session detail — verify JcLS tab appears

**Step 2: Import a ZOLL ZIP**

Import a real ZOLL ZIP file and verify:
- Import completes successfully
- New session has `jcls_score` and `jcls_breakdown` in metrics
- Dashboard KPI cards show JcLS data
- Session detail shows JcLS breakdown tab

**Step 3: Verify backfill worked**

If there were existing real-call sessions before this update:
- They should now have JcLS scores (backfill ran on login)
- Check sessions.json to confirm `jcls_score` is populated

**Step 4: Verify simulated sessions are unaffected**

- Simulated sessions should NOT have jcls_score
- Simulated session detail should NOT show JcLS tab
- Simulated session table rows should show "—" in JcLS column

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: JcLS scoring system - complete implementation"
```
