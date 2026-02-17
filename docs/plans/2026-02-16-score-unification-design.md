# Score Unification & Info System — Design Document

**Date:** 2026-02-16
**Status:** Approved

## Problem

The app has 4 different composite "scores" (Quality Score, JcLS Score, Team Score, ZOLL Quality Score) scattered across pages with no explanation. Users cannot tell which score is which, where they come from, or which one matters. The "ZOLL Quality Score" label is misleading — it's our formula `(Depth% + Rate%) / 2`, not a ZOLL metric. The "Quality Score" is the same made-up formula. The "Team Score" is yet another weighted formula. Only JcLS is evidence-based.

## Solution

**One score: JcLS.** Remove all other composite scores. Add info tooltips so users understand every metric.

## Score Strategy

### What Gets Removed
- **Quality Score** `(Depth% + Rate%) / 2` — removed from all pages. Not evidence-based, not from ZOLL.
- **ZOLL Quality Score** — same formula as Quality Score with a misleading label. Removed entirely.
- **Team Score** `40% CCF + 30% QS + 15% Depth + 15% Rate` — replaced with session JcLS on Team Analysis page.

### What Stays
- **JcLS Score** — the only composite score. Real-call sessions only. 100-point evidence-based rubric.
- **CiT (Compressions in Target %)** — real ZOLL metric. Percentage of compressions where both depth AND rate were simultaneously in target. Already feeds into JcLS Tier 1C.
- **CCF** — real ZOLL metric. Chest compression fraction.
- **Release Velocity** — real ZOLL metric. Chest recoil speed.
- **Individual metrics** (depth%, rate%, CPM, duration, etc.) — raw data, always shown.

### Simulated Sessions
- No composite score. Show raw depth% and rate% individually.
- Rankings: no score column, sort by depth% then rate%.
- Top Performers (simulated tab): name + session count, no score number.

### Team Events
- Each team event is one session. Show that session's JcLS score directly (no averaging, no separate formula).

## Page-by-Page Changes

### Dashboard
- Primary KPI row: JcLS Score (hero), CCF, Total Sessions, Active Providers — unchanged from current
- Secondary KPI row: CiT, Release Velocity — **remove "ZOLL Quality Score" card**
- All 4 metric cards (JcLS, CCF, CiT, Release Velocity) get expandable trend graph
- Top Performers real tab: JcLS with colored dot (already done). Sim tab: name + session count, **remove score number**
- Quality Metrics section: **remove "Real Life Quality Score" and "Simulated Quality Score" summary bars** that show `quality_score`

### Rankings Page
- **Remove** info bar explaining "Quality Score = (Depth + Rate) / 2"
- Real-call provider tab: rename "Quality Score" column to "JcLS", sort by avg JcLS
- Simulated provider tab: **remove** composite score column, sort by depth% then rate%
- Team rankings tab: rename "Quality Score" column to "JcLS", show session JcLS score

### Provider Detail Page
- **Remove** all "Quality Score" displays from 3 stat sections (As Team Lead, As Provider, Combined)
- Real-call sections: replace with avg JcLS with colored indicator
- Simulated sections: show depth% and rate% only, no composite
- Summary cards at top: replace Quality Score card with JcLS
- Chart metric options: replace "Quality Score" with "JcLS Score"
- Recent sessions inline table: replace quality_score display with JcLS

### Team Analysis Page
- Replace "Team Score" with session JcLS score everywhere
- Remove `calculate_team_score()` function (no longer needed)
- "Avg Quality Score" stat card → "Avg JcLS Score"
- Chart datasets: replace "Quality Score" and "Team Score" with "JcLS Score"
- Sort options: replace "Team Score" and "Quality Score" with "JcLS Score"

### Session Detail Modal
- **Remove** "ZOLL Quality Score" reference text below JcLS hero score
- JcLS tab otherwise unchanged

### Sessions Table
- JcLS column already present, no changes needed

## Info Tooltip System

### Implementation
A reusable Jinja2 component `metric_info.html` — renders a small `?` button that opens an Alpine.js modal overlay with the metric explanation.

### Metric Definitions

**JcLS Score** — Full rubric modal:
- Title: "JcLS Score — Jordan's Clinical Scoring"
- Subtitle: "A 100-point evidence-based CPR quality rubric."
- Body: "Weights derived from published adjusted odds ratios for neurologically intact survival (CPC 1-2) from out-of-hospital cardiac arrest research."
- Full 4-tier table:
  - Tier 1: Compression Quality (55 pts) — Depth Compliance (20), Rate Compliance (15), Combined Compliance/CiT (20)
  - Tier 2: Perfusion Continuity (25 pts) — CCF (15), Pause Quality (10: mean pause 6 + no long pauses 4)
  - Tier 3: Recoil Quality (10 pts) — Release Velocity (10)
  - Tier 4: System Performance (10 pts) — Time to First Compression (5), Time to First Shock (5)
- Each sub-metric shows its scoring bands
- Color bands: Green (>=80 target met), Yellow (60-79 needs improvement), Red (<60 below standard)
- Footer: "Applied to real-call sessions only. Score scales proportionally when metrics are unavailable."

**CCF** — Brief modal:
- "Chest Compression Fraction — the percentage of total CPR time spent actively delivering chest compressions. Directly correlates with neurologically intact survival. Target: >=80%. Source: ZOLL defibrillator."

**CiT (Combined Compliance)** — Brief modal:
- "Compressions in Target — the percentage of individual compressions where BOTH depth AND rate were simultaneously within the target range during that single compression. More stringent than measuring depth% and rate% separately, because a compression can have good depth but bad rate (or vice versa). Industry average: ~35%. Source: ZOLL defibrillator."

**Release Velocity** — Brief modal:
- "Release Velocity measures how quickly the chest wall returns to its resting position after each compression. Indicates quality of full chest recoil, which is critical for cardiac refill. Target: >=400 mm/s with low variability (SD <100). Source: ZOLL defibrillator."

**Standard metrics** (depth%, rate%, CPM, depth cm, duration):
- HTML `title` attribute tooltip on hover. No modal. Example: `title="Percentage of compressions within target depth range (5-6 cm)"`

## Expandable Trend Graphs

### Behavior
- Each of the 4 metric KPI cards (JcLS, CCF, CiT, Release Velocity) is clickable
- Click toggles a Chart.js line graph below the card
- Alpine.js `x-show` with transition for smooth expand/collapse
- Chart renders lazily on first expand (not on page load) to avoid performance hit

### Chart Details
- **Type:** Line chart with dots at each data point
- **X-axis:** Session date (real-call sessions only, chronological)
- **Y-axis:** Metric value
- **Target line:** Horizontal dashed line at target value
  - JcLS: 80 (green zone threshold)
  - CCF: 80%
  - CiT: 35% (industry average reference)
  - Release Velocity: 400 mm/s
- **Data source:** All real-call sessions, sorted by date
- **Styling:** Matches Ember Dark theme. Line color matches the metric's accent color.

### Data Requirements
- Dashboard route needs to pass trend data arrays to the template
- New fields in KPI dict: `jcls_trend`, `ccf_trend`, `cit_trend`, `rv_trend`
- Each is a list of `{date: "YYYY-MM-DD", value: number}` objects

## Decisions Made
- **Quality Score:** Removed entirely (not evidence-based, not from ZOLL)
- **ZOLL Quality Score:** Removed (misleading label for our formula)
- **Team Score:** Replaced with session JcLS
- **Simulated scoring:** No composite score, raw metrics only
- **Tooltips:** JcLS gets full rubric modal, CCF/CiT/RV get brief modals, standard metrics get title tooltips
- **Trend graphs:** All 4 dashboard metrics, x-axis by date, with target reference lines
