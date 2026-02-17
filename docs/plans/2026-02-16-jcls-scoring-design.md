# JcLS Scoring System — Design Document

**Date:** 2026-02-16
**Status:** Approved

## Overview

The JcLS Score (Jordan's Clinical Scoring) is a 100-point evidence-based CPR quality rubric that replaces the simple depth/rate average as the primary quality metric. Every weight is derived from published adjusted odds ratios for neurologically intact survival (CPC 1-2) from OHCA research.

**Scope:** Real-call sessions only. Simulated sessions keep using the existing simple quality percentage.

## Two Quality Scores

These must never be confused:

- **jcls_score** — Our 100-point rubric. Primary metric. Hero display, color-coded. Real-call only.
- **zoll_quality_score** — ZOLL's proprietary quality percentage from Case Statistics. Displayed as a secondary reference labeled "ZOLL Quality Score". The existing `quality_score` calculation stays but gets relabeled.

## Scoring Rubric (100 Points)

### Tier 1 — Compression Quality (55 pts)

**1A. Depth Compliance (20 pts)**
Source: `correct_depth_percent` (already parsed)
Bands: >=80% = 20 | 65-79% = 16 | 50-64% = 12 | 35-49% = 7 | <35% = 3

**1B. Rate Compliance (15 pts)**
Source: `correct_rate_percent` (already parsed)
Bands: >=85% = 15 | 70-84% = 12 | 55-69% = 8 | 40-54% = 4 | <40% = 1

**1C. Combined Compliance / CiT (20 pts)**
Source: `compressions_in_target_percent` (already parsed)
Bands: >=60% = 20 | 45-59% = 16 | 35-44% = 12 | 25-34% = 7 | <25% = 3

### Tier 2 — Perfusion Continuity (25 pts)

**2A. CCF (15 pts)**
Source: `compression_fraction` (already parsed, "CCF All % in CPR time")
Bands: >=85% = 15 | 80-84% = 12 | 70-79% = 8 | 60-69% = 4 | <60% = 1

**2B. Pause Quality (10 pts)**
Source: IndividualPauses.csv → `Total pause duration (sec)` column

Sub-score A — Mean pause duration (6 pts):
<=4s = 6 | 4.1-6s = 4 | 6.1-8s = 2 | >8s = 0

Sub-score B — No pauses >10s (4 pts):
True (0 pauses >10s) = 4 | 1 pause >10s = 2 | 2+ pauses >10s = 0

If IndividualPauses.csv is missing: set pause metrics to null, exclude 10 pts from denominator (score on 90-point basis).

### Tier 3 — Recoil Quality (10 pts)

**3A. Release Velocity (10 pts)**
Source: `mean_release_velocity` + `release_velocity_std_dev` (already parsed)
Bands: >=400mm/s AND SD<100 = 10 | >=400mm/s AND SD>=100 = 8 | 350-399mm/s = 6 | 300-349mm/s = 3 | <300mm/s = 1

If field is missing/null: exclude from denominator, scale proportionally.

### Tier 4 — System Performance (10 pts)

**4A. Time to First Compression (5 pts)**
Source: `seconds_to_first_compression` (already parsed)
Bands: <=30s = 5 | 31-60s = 4 | 61-90s = 2 | >90s = 0

**4B. Time to First Shock (5 pts)**
Source: `seconds_to_first_shock` (already parsed)
Bands: <=120s = 5 | 121-180s = 3 | >180s = 1
Non-shockable/no shock (value is None AND shocks_delivered == 0): 3 pts (neutral)

## Color Bands (No Letter Grades)

- Green (>=80): target met
- Yellow (60-79): needs improvement
- Red (<60): below standard

Score displayed as number + color. No letter grades.

## Architecture — Approach A: Standalone Scoring Service

### Data Model Changes (app/models.py)

New fields on `SessionMetrics`:

```
pause_count: Optional[int]
mean_pause_duration: Optional[float]
max_pause_duration: Optional[float]
pauses_over_10s: Optional[int]
jcls_score: Optional[int]
jcls_breakdown: Optional[Dict]
```

No fields renamed or removed. Existing `quality_score` calculation stays.

### IndividualPauses.csv Parser (app/services/ingestion_service.py)

New function `_parse_individual_pauses(zip_path)` added to existing ingestion service. Reads `Total pause duration (sec)` column. Returns dict with pause_count, mean_pause_duration, max_pause_duration, pauses_over_10s. Returns all-None dict if file missing/empty.

Called from `ingest_zip()` after Case Statistics and MinuteByMinute parsing.

### JcLS Scoring Service (app/services/jcls_service.py)

New file. Two public functions:

1. `calculate_jcls_score(metrics: dict, shocks_delivered: int|None) -> dict` — pure function, takes metrics dict, returns full breakdown with jcls_score, tier breakdowns, available_points, raw_score.

2. `backfill_jcls_scores(session_service) -> int` — scans real-call sessions missing jcls_score, calculates and persists. Called on app startup.

### Integration

**Ingestion flow:**
1. Parse Case Statistics.csv (existing)
2. Parse MinuteByMinuteReport.csv (existing)
3. Parse IndividualPauses.csv (NEW)
4. If real_call: calculate_jcls_score() → store jcls_score + jcls_breakdown
5. Save session (existing)

**Startup backfill:**
On app boot, after service context loaded, call backfill_jcls_scores(). No-op on subsequent boots.

## Dashboard UI Changes

### KPI Row (4 cards, reordered)
1. JcLS Score — hero card, large number, color-coded
2. CCF — percentage, "Target: >=80%" subtext
3. Total Sessions — unchanged
4. Active Providers — unchanged

### New Secondary KPI Row (3 smaller cards)
1. Combined Compliance (CiT) — percentage, "Industry avg: ~35%" subtext
2. Release Velocity — mm/s, color threshold, SD below
3. ZOLL Quality Score — gray/neutral, clearly labeled

### Other Dashboard Changes
- ROSC Rate moves to highlight banners section
- Quality Metrics circular progress indicators stay as-is
- Top Performers sort by jcls_score, show score + colored dot
- Rankings show JcLS as primary column, ZOLL quality as secondary

## Session Detail — JcLS Tab

New first tab "JcLS Score" on real-call session detail modal. Default active tab.

**Hero section:** Large score number + color indicator. "out of {available_points}" when <100. ZOLL Quality Score in small gray text.

**Breakdown:** 4 tier cards, each with sub-metrics showing value, earned/max points, star for full marks, progress bar per tier. Missing metrics show "N/A (excluded from scoring)".

Simulated sessions: tab doesn't appear.

## Session List — Score Badge

Real Life sessions table and dashboard Recent Sessions table get a JcLS column: colored dot + numeric score. Simulated sessions show gray dash.

## Decisions Made

- **Rankings:** JcLS primary, ZOLL quality secondary (both visible)
- **Simulated sessions:** Skip JcLS, keep simple quality percentage
- **Backfill:** Auto on startup for existing sessions
- **CCF source:** Use existing `compression_fraction` ("CCF All % in CPR time")
- **Pause CSV column:** `Total pause duration (sec)` (exact header confirmed)
- **No letter grades:** Number + color band only
