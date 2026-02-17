# Team Report Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add JcLS hero score, consolidate metric cards into a 3x2 grid, and add a Metric Reference page with citations as page 2 of the printed report.

**Architecture:** All changes are in a single template file (`templates/pages/reports.html`). The team report is an Alpine.js component that renders a white "paper" preview from preloaded session JSON. No backend changes needed — `jcls_score` is already in `sessionData.metrics`. Three edits: insert JcLS hero, replace metrics sections with consolidated 6-card grid, append reference page after footer.

**Tech Stack:** Jinja2 templates, Alpine.js (x-text, x-show, :class bindings), Tailwind CSS, CSS print styles

---

### Task 1: Add JcLS Hero Score

**Files:**
- Modify: `templates/pages/reports.html:193-194` (insert between Team Members and Key Performance Metrics)

**Step 1: Insert JcLS hero card**

Find this block (line ~193-196):

```html
                                {# ===== KEY PERFORMANCE METRICS ===== #}
                                <div>
                                    <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Key Performance Metrics</h3>
```

Insert BEFORE it (after the Team Members closing `</div>`):

```html
                                {# ===== JcLS HERO SCORE ===== #}
                                <div class="rounded-lg p-4 text-center border"
                                     :class="(() => {
                                         const s = sessionData.metrics?.jcls_score;
                                         if (s == null) return 'bg-gray-50 border-gray-200';
                                         if (s >= 80) return 'bg-emerald-50 border-emerald-300';
                                         if (s >= 60) return 'bg-amber-50 border-amber-300';
                                         return 'bg-red-50 border-red-300';
                                     })()">
                                    <p class="text-xs text-gray-500 uppercase tracking-wide mb-1">JcLS Score</p>
                                    <p class="text-5xl font-bold leading-none"
                                       :class="(() => {
                                           const s = sessionData.metrics?.jcls_score;
                                           if (s == null) return 'text-gray-400';
                                           if (s >= 80) return 'text-emerald-600';
                                           if (s >= 60) return 'text-amber-600';
                                           return 'text-red-600';
                                       })()"
                                       x-text="sessionData.metrics?.jcls_score ?? '—'"></p>
                                    <p class="text-sm font-semibold mt-1"
                                       :class="(() => {
                                           const s = sessionData.metrics?.jcls_score;
                                           if (s == null) return 'text-gray-400';
                                           if (s >= 80) return 'text-emerald-700';
                                           if (s >= 60) return 'text-amber-700';
                                           return 'text-red-700';
                                       })()"
                                       x-text="(() => {
                                           const s = sessionData.metrics?.jcls_score;
                                           if (s == null) return 'No JcLS Data';
                                           if (s >= 80) return 'Excellent';
                                           if (s >= 60) return 'Proficient';
                                           if (s >= 40) return 'Developing';
                                           return 'Needs Improvement';
                                       })()"></p>
                                    <p class="text-xs text-gray-400 mt-1">Jordan's Clinical Scoring</p>
                                </div>
```

**Step 2: Verify visually**

Run: `./venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000`

Navigate to Reports → select a real-call session → confirm the JcLS hero card appears between Team Members and Key Performance Metrics with correct color coding.

---

### Task 2: Replace Metrics with Consolidated 6-Card Grid

**Files:**
- Modify: `templates/pages/reports.html` — replace lines covering Key Performance Metrics + Additional Metrics sections

**Step 1: Replace the Key Performance Metrics AND Additional Metrics sections**

Find and replace the entire block from `{# ===== KEY PERFORMANCE METRICS ===== #}` through the end of the `{# ===== ADDITIONAL METRICS ===== #}` section (lines ~195-252). Replace with:

```html
                                {# ===== KEY PERFORMANCE METRICS (6-card consolidated grid) ===== #}
                                <div>
                                    <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Key Performance Metrics</h3>
                                    <div class="grid grid-cols-3 gap-2">
                                        {# CCF #}
                                        <div class="bg-blue-50 rounded-lg p-2 text-center border border-blue-200">
                                            <p class="text-xs text-blue-700 font-medium">CCF</p>
                                            <p class="text-2xl font-bold text-blue-600" x-text="(sessionData.metrics?.compression_fraction || 0) + '%'"></p>
                                            <p class="text-xs text-blue-500">Target: &gt;80%</p>
                                        </div>
                                        {# Depth Compliance #}
                                        <div class="bg-emerald-50 rounded-lg p-2 text-center border border-emerald-200">
                                            <p class="text-xs text-emerald-700 font-medium">Depth Compliance</p>
                                            <p class="text-2xl font-bold text-emerald-600" x-text="(sessionData.metrics?.correct_depth_percent || 0) + '%'"></p>
                                            <p class="text-xs text-emerald-500" x-text="(sessionData.metrics?.compression_depth || '—') + ' cm avg'"></p>
                                        </div>
                                        {# Rate Compliance #}
                                        <div class="bg-amber-50 rounded-lg p-2 text-center border border-amber-200">
                                            <p class="text-xs text-amber-700 font-medium">Rate Compliance</p>
                                            <p class="text-2xl font-bold text-amber-600" x-text="(sessionData.metrics?.correct_rate_percent || 0) + '%'"></p>
                                            <p class="text-xs text-amber-500" x-text="(sessionData.metrics?.compression_rate || '—') + ' CPM avg'"></p>
                                        </div>
                                        {# Total Compressions #}
                                        <div class="bg-purple-50 rounded-lg p-2 text-center border border-purple-200">
                                            <p class="text-xs text-purple-700 font-medium">Compressions</p>
                                            <p class="text-2xl font-bold text-purple-600" x-text="sessionData.metrics?.total_compressions?.toLocaleString() || '—'"></p>
                                            <p class="text-xs text-purple-500">Total Count</p>
                                        </div>
                                        {# Shocks #}
                                        <div class="bg-yellow-50 rounded-lg p-2 text-center border border-yellow-200">
                                            <p class="text-xs text-yellow-700 font-medium">Shocks</p>
                                            <p class="text-2xl font-bold text-yellow-600" x-text="sessionData.shocks_delivered || 0"></p>
                                            <p class="text-xs text-yellow-600" x-text="((sessionData.shocks_delivered || 0) * 200) + ' Joules'"></p>
                                        </div>
                                        {# EtCO2 #}
                                        <div class="rounded-lg p-2 text-center border"
                                             :class="isValidEtCO2(sessionData.metrics?.etco2) ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'">
                                            <p class="text-xs font-medium" :class="isValidEtCO2(sessionData.metrics?.etco2) ? 'text-emerald-700' : 'text-red-700'">EtCO2</p>
                                            <p class="text-2xl font-bold" :class="isValidEtCO2(sessionData.metrics?.etco2) ? 'text-emerald-600' : 'text-red-600'" x-text="isValidEtCO2(sessionData.metrics?.etco2) ? sessionData.metrics.etco2 + ' mmHg' : '—'"></p>
                                            <p class="text-xs font-medium" :class="isValidEtCO2(sessionData.metrics?.etco2) ? 'text-emerald-500' : 'text-red-500'" x-text="isValidEtCO2(sessionData.metrics?.etco2) ? '✓ Recorded' : '! Remember EtCO2'"></p>
                                        </div>
                                    </div>
                                </div>
```

**Step 2: Verify visually**

Reload the Reports page → confirm 6 cards in a 3x2 grid, subtitles show raw values (cm, CPM), EtCO2 has conditional coloring.

---

### Task 3: Remove unused JS functions

**Files:**
- Modify: `templates/pages/reports.html` — JavaScript section

**Step 1: Delete `getRateStatus()` and `getDepthStatus()` functions**

These two functions (approximately lines 522-549) are no longer referenced by any template element since the Additional Metrics section was removed. Delete them entirely — from `// Get compression rate status` through the closing `}` of `getDepthStatus`.

**Step 2: Verify no JS errors**

Reload the page, open browser console, select a session. Confirm no ReferenceError for getRateStatus or getDepthStatus.

---

### Task 4: Add Metric Reference Page (Page 2)

**Files:**
- Modify: `templates/pages/reports.html` — insert after the footer `</div>` (line ~332) but still inside the `<template x-if="selectedSessionId && sessionData">` block

**Step 1: Insert the reference page**

Find the footer section (line ~328-332):

```html
                                {# ===== FOOTER with JcLS Logo Centered ===== #}
                                <div class="flex justify-center pt-4 border-t border-gray-200 mt-4">
                                    <img src="/static/images/logos/JcLS.png" alt="JcLS" class="h-24 object-contain" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                                    <span class="text-gray-400 text-xs italic hidden items-center">Add JcLS.png</span>
                                </div>
```

Insert AFTER this `</div>` (but still inside the `<div class="space-y-3 print:space-y-2">` wrapper):

```html
                                {# ===== PAGE 2: METRIC REFERENCE ===== #}
                                <div class="mt-8" style="page-break-before: always;">
                                    <h2 class="text-xl font-bold text-gray-900 mb-4 text-center">Metric Definitions & Scoring Reference</h2>

                                    {# JcLS Rubric #}
                                    <div class="mb-6">
                                        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">JcLS Scoring Rubric (100 Points)</h3>
                                        <table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                                            <thead class="bg-gray-100">
                                                <tr>
                                                    <th class="text-left px-3 py-2 text-gray-600 font-medium">Tier</th>
                                                    <th class="text-left px-3 py-2 text-gray-600 font-medium">Component</th>
                                                    <th class="text-right px-3 py-2 text-gray-600 font-medium">Points</th>
                                                </tr>
                                            </thead>
                                            <tbody class="divide-y divide-gray-200">
                                                <tr class="bg-gray-50 font-semibold">
                                                    <td class="px-3 py-1.5 text-gray-800" rowspan="4">Tier 1: Compression Quality</td>
                                                    <td class="px-3 py-1.5 text-gray-800" colspan="2"><span class="float-right font-bold">55</span></td>
                                                </tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">1A. Depth Compliance</td><td class="px-3 py-1 text-right text-gray-700">20</td></tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">1B. Rate Compliance</td><td class="px-3 py-1 text-right text-gray-700">15</td></tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">1C. Combined Compliance (CiT)</td><td class="px-3 py-1 text-right text-gray-700">20</td></tr>

                                                <tr class="bg-gray-50 font-semibold">
                                                    <td class="px-3 py-1.5 text-gray-800" rowspan="3">Tier 2: Perfusion Continuity</td>
                                                    <td class="px-3 py-1.5 text-gray-800" colspan="2"><span class="float-right font-bold">25</span></td>
                                                </tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">2A. CCF</td><td class="px-3 py-1 text-right text-gray-700">15</td></tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">2B. Pause Quality</td><td class="px-3 py-1 text-right text-gray-700">10</td></tr>

                                                <tr class="bg-gray-50 font-semibold">
                                                    <td class="px-3 py-1.5 text-gray-800" rowspan="2">Tier 3: Recoil Quality</td>
                                                    <td class="px-3 py-1.5 text-gray-800" colspan="2"><span class="float-right font-bold">10</span></td>
                                                </tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">3A. Release Velocity</td><td class="px-3 py-1 text-right text-gray-700">10</td></tr>

                                                <tr class="bg-gray-50 font-semibold">
                                                    <td class="px-3 py-1.5 text-gray-800" rowspan="3">Tier 4: System Performance</td>
                                                    <td class="px-3 py-1.5 text-gray-800" colspan="2"><span class="float-right font-bold">10</span></td>
                                                </tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">4A. Time to First Compression</td><td class="px-3 py-1 text-right text-gray-700">5</td></tr>
                                                <tr><td class="px-3 py-1 text-gray-600 pl-6">4B. Time to First Shock</td><td class="px-3 py-1 text-right text-gray-700">5</td></tr>
                                            </tbody>
                                        </table>

                                        {# Score bands #}
                                        <div class="flex items-center gap-4 mt-2 text-xs text-gray-600">
                                            <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-emerald-500"></span> ≥80 Excellent</div>
                                            <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-amber-500"></span> 60–79 Proficient</div>
                                            <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-orange-500"></span> 40–59 Developing</div>
                                            <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-red-500"></span> &lt;40 Needs Improvement</div>
                                        </div>
                                        <p class="text-xs text-gray-400 mt-1 italic">Score scales proportionally when metrics are unavailable.</p>
                                    </div>

                                    {# Metric Definitions #}
                                    <div class="mb-6">
                                        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Individual Metric Definitions</h3>
                                        <table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                                            <thead class="bg-gray-100">
                                                <tr>
                                                    <th class="text-left px-3 py-2 text-gray-600 font-medium w-1/4">Metric</th>
                                                    <th class="text-left px-3 py-2 text-gray-600 font-medium">Definition</th>
                                                    <th class="text-left px-3 py-2 text-gray-600 font-medium w-1/5">Target</th>
                                                </tr>
                                            </thead>
                                            <tbody class="divide-y divide-gray-200">
                                                <tr>
                                                    <td class="px-3 py-2 text-gray-800 font-medium">CCF</td>
                                                    <td class="px-3 py-2 text-gray-600">Chest Compression Fraction — percentage of cardiac arrest time with active chest compressions</td>
                                                    <td class="px-3 py-2 text-gray-700">≥80%</td>
                                                </tr>
                                                <tr>
                                                    <td class="px-3 py-2 text-gray-800 font-medium">Depth Compliance</td>
                                                    <td class="px-3 py-2 text-gray-600">Percentage of compressions achieving the guideline target depth of 5.0–6.0 cm</td>
                                                    <td class="px-3 py-2 text-gray-700">Higher is better</td>
                                                </tr>
                                                <tr>
                                                    <td class="px-3 py-2 text-gray-800 font-medium">Rate Compliance</td>
                                                    <td class="px-3 py-2 text-gray-600">Percentage of compressions within the guideline target rate of 100–120 compressions per minute</td>
                                                    <td class="px-3 py-2 text-gray-700">Higher is better</td>
                                                </tr>
                                                <tr>
                                                    <td class="px-3 py-2 text-gray-800 font-medium">EtCO2</td>
                                                    <td class="px-3 py-2 text-gray-600">End-tidal carbon dioxide — capnography measurement indicating perfusion quality during CPR</td>
                                                    <td class="px-3 py-2 text-gray-700">10–20+ mmHg</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>

                                    {# Citations #}
                                    <div>
                                        <h3 class="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">References</h3>
                                        <p class="text-xs text-gray-500 mb-3 italic">JcLS (Jordan's Clinical Scoring) is a 100-point evidence-based CPR quality rubric. Tier weights are derived from adjusted odds ratios for neurologically intact survival (CPC 1-2) reported in the studies below.</p>
                                        <ol class="list-decimal list-inside text-xs text-gray-600 space-y-2">
                                            <li>Cheskes S, Schmicker RH, Christenson J, et al. Perishock Pause: An Independent Predictor of Survival From Out-of-Hospital Shockable Cardiac Arrest. <em>Circulation.</em> 2011;124(1):58-66.</li>
                                            <li>Idris AH, Guffey D, Pepe PE, et al. Chest Compression Rates and Survival Following Out-of-Hospital Cardiac Arrest. <em>Critical Care Medicine.</em> 2015;43(4):840-848.</li>
                                            <li>Panchal AR, Bartos JA, Cabañas JG, et al. Part 3: Adult Basic and Advanced Life Support: 2020 American Heart Association Guidelines for Cardiopulmonary Resuscitation and Emergency Cardiovascular Care. <em>Circulation.</em> 2020;142(16_suppl_2):S366-S468.</li>
                                        </ol>
                                    </div>
                                </div>
```

**Step 2: Update print styles**

In the print `<style>` block, add the reference page to the visibility rules. Find:

```css
    #team-report-template, #team-report-template * {
        visibility: visible;
    }
```

This already covers the reference page since it's inside `#team-report-template`. No change needed here.

**Step 3: Verify visually**

Reload → select a session → scroll down past footer → confirm the reference page appears with rubric table, metric definitions, score bands, and citations. Use Print Preview (Ctrl+P) to confirm it starts on a new page.

---

### Task 5: Final Verification

**Step 1: Verify app starts clean**

Run: `./venv/Scripts/python.exe -c "from app.main import app; print('OK')"`

**Step 2: Verify no JS console errors**

Open Reports page, select a session, open browser DevTools console. Confirm zero errors.

**Step 3: Print preview check**

Ctrl+P on the report. Confirm:
- Page 1: Header, call info, team members, JcLS hero, 6 metric cards (3x2), Zoll upload, Vitals upload, Learning Opportunities, JcLS footer logo
- Page 2: Metric Definitions & Scoring Reference (rubric, definitions, citations)
