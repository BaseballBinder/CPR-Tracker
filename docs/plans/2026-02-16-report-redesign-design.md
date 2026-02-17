# Team Performance Report Redesign — Design Document

**Date:** 2026-02-16
**Status:** Approved

## Overview

Redesign the Team Performance Report (the printable PDF/paper report generated from real-call sessions) to reflect the JcLS scoring system and consolidate metrics into a cleaner layout. The report uses a white paper theme for print fidelity.

**Scope:** Team Report only (the Alpine.js-driven report in `reports.html`). Provider Report partial is not in scope.

## What Stays the Same

These sections are unchanged in structure and content:

- Header (COSG logo centered, "CPR Performance Report" title, "Team Debriefing Document" subtitle)
- Call Information bar (Date, Event Type, Team Lead, Duration, Outcome — 5-column grid)
- Team Members pills
- Zoll RescueNet Graph drag-and-drop upload
- Vital Signs Trending Graph drag-and-drop upload
- Learning Opportunities textarea
- Footer (JcLS logo centered)

## Change 1: JcLS Hero Score

**Location:** Between Call Information bar and Key Metric Cards.

A centered card showing:
- Large score number (e.g., **72**), color-coded: green (>=80), amber (60-79), red (<60)
- Tier label: "Excellent" / "Proficient" / "Developing" / "Needs Improvement"
- Subtitle: "Jordan's Clinical Scoring"
- Light background tint matching tier color (green-50, amber-50, red-50)
- Bordered card, full width, centered content

**Data source:** `sessionData.metrics.jcls_score` (already available in session JSON).

Tier label mapping:
- >=80: "Excellent"
- 60-79: "Proficient"
- 40-59: "Developing"
- <40: "Needs Improvement"
- null/undefined: show "—" with "No JcLS data" subtitle

## Change 2: Consolidated Metric Cards (6 cards, 3x2 grid)

**Replaces:** Current 5 key metric cards (CCF, Depth %, Rate %, # Compressions, Shocks) AND the separate Additional Metrics section (Avg Rate, Avg Depth, EtCO2).

**New layout:** 6 cards in a `grid-cols-3` (2 rows of 3):

| Card | Primary Value | Subtitle | Color Theme |
|------|-------------|----------|-------------|
| CCF | `{compression_fraction}%` | Target: >80% | Blue |
| Depth Compliance | `{correct_depth_percent}%` | `{compression_depth} cm avg` | Emerald |
| Rate Compliance | `{correct_rate_percent}%` | `{compression_rate} CPM avg` | Amber |
| Compressions | `{total_compressions}` formatted with commas | Total count | Purple |
| Shocks | `{shocks_delivered}` | `{shocks * 200} Joules` | Yellow |
| EtCO2 | `{etco2} mmHg` or "—" | "✓ Recorded" / "! Remember EtCO2" | Green (recorded) / Red (missing) |

Each card: light color tint background (e.g., `bg-blue-50`), matching border (e.g., `border-blue-200`), metric label in darker shade, value in bold darker shade.

**Removed:** The entire Additional Metrics section (3-column row with rate/depth/EtCO2 status indicators). Its data is folded into the cards above.

## Change 3: Metric Reference Page (Page 2)

**Location:** After the footer, with `page-break-before: always` CSS to force it onto a new printed page.

### Section A — JcLS Scoring Rubric

Condensed rubric table:

| Tier | Component | Points |
|------|-----------|--------|
| **Tier 1: Compression Quality** | | **55** |
| | 1A. Depth Compliance | 20 |
| | 1B. Rate Compliance | 15 |
| | 1C. Combined Compliance (CiT) | 20 |
| **Tier 2: Perfusion Continuity** | | **25** |
| | 2A. CCF | 15 |
| | 2B. Pause Quality (Mean Pause + No Long Pauses) | 10 |
| **Tier 3: Recoil Quality** | | **10** |
| | 3A. Release Velocity | 10 |
| **Tier 4: System Performance** | | **10** |
| | 4A. Time to First Compression | 5 |
| | 4B. Time to First Shock | 5 |

Color band legend:
- Green >=80: Excellent
- Amber 60-79: Proficient
- Amber 40-59: Developing
- Red <40: Needs Improvement

Note: "Score scales proportionally when metrics are unavailable."

### Section B — Individual Metric Definitions

| Metric | Definition | Target |
|--------|-----------|--------|
| CCF | Chest Compression Fraction — percentage of cardiac arrest time with active chest compressions | >=80% |
| Depth Compliance | Percentage of compressions achieving the guideline target depth of 5.0–6.0 cm | Higher is better |
| Rate Compliance | Percentage of compressions within the guideline target rate of 100–120 compressions per minute | Higher is better |
| EtCO2 | End-tidal carbon dioxide — capnography measurement indicating perfusion quality during CPR | 10–20+ mmHg |

### Section C — Citations

> JcLS (Jordan's Clinical Scoring) is a 100-point evidence-based CPR quality rubric. Tier weights are derived from adjusted odds ratios for neurologically intact survival (CPC 1-2) reported in the studies below.

1. Cheskes S, Schmicker RH, Christenson J, et al. Perishock Pause: An Independent Predictor of Survival From Out-of-Hospital Shockable Cardiac Arrest. *Circulation.* 2011;124(1):58-66.
2. Idris AH, Guffey D, Pepe PE, et al. Chest Compression Rates and Survival Following Out-of-Hospital Cardiac Arrest. *Critical Care Medicine.* 2015;43(4):840-848.
3. Panchal AR, Bartos JA, Cabañas JG, et al. Part 3: Adult Basic and Advanced Life Support: 2020 American Heart Association Guidelines for Cardiopulmonary Resuscitation and Emergency Cardiovascular Care. *Circulation.* 2020;142(16_suppl_2):S366-S468.

## Files to Modify

- `templates/pages/reports.html` — Team report template (JcLS hero, consolidated cards, reference page, remove Additional Metrics section)
- `templates/pages/reports.html` — JavaScript `getRateStatus()` and `getDepthStatus()` can be removed (no longer needed without the Additional Metrics section)

No backend changes needed — all data is already in the session JSON.
