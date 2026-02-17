# Score Unification & Info System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove all made-up composite scores (Quality Score, ZOLL Quality Score, Team Score), unify on JcLS as the sole composite score, and add info-tooltip modals to every major metric so users understand what they are looking at.
**Architecture:** A new reusable Jinja2 component (`metric_info.html`) renders a `?` button that opens an Alpine.js modal overlay with metric explanations. All `quality_score` calculations and references are stripped from `mock_data.py` and templates. Dashboard KPI cards for JcLS, CCF, CiT, and Release Velocity gain clickable expand/collapse trend charts powered by Chart.js with lazy initialization.
**Tech Stack:** Python 3.12, FastAPI, Jinja2, HTMX, Alpine.js, Chart.js, Tailwind CSS
**Design Doc:** `docs/plans/2026-02-16-score-unification-design.md`

---

## Task 1 — Create the Info Modal Component

**Files:**
- CREATE `templates/components/metric_info.html`

**Steps:**

1. Create `templates/components/metric_info.html` with the following content. This is a reusable Jinja2 include that renders an inline `?` button. When clicked, it opens an Alpine.js modal overlay with the metric explanation. The caller sets `info_id` (unique Alpine scope ID), `info_title`, and `info_body_template` (path to a partial that renders the body content).

```html
{#
  Metric Info Button + Modal Component

  Usage:
    {% set info_id = "jcls" %}
    {% set info_title = "JcLS Score" %}
    {% set info_subtitle = "Jordan's Clinical Scoring" %}
    {% set info_body_template = "components/metric_info/jcls_body.html" %}
    {% include "components/metric_info.html" %}

  For simple text-only modals:
    {% set info_id = "ccf" %}
    {% set info_title = "CCF" %}
    {% set info_subtitle = "Chest Compression Fraction" %}
    {% set info_text = "The percentage of total CPR time spent actively delivering chest compressions." %}
    {% include "components/metric_info.html" %}
#}

<span x-data="{ open: false }" class="inline-flex items-center">
    {# ? Button #}
    <button @click.stop="open = true" type="button"
            class="ml-1 w-4 h-4 rounded-full bg-[#342f31] border border-[rgba(255,255,255,0.15)] text-slate-400 hover:text-slate-200 hover:border-slate-400 text-[10px] font-bold flex items-center justify-center transition-colors cursor-pointer"
            title="What is {{ info_title }}?">
        ?
    </button>

    {# Modal Overlay #}
    <template x-teleport="body">
        <div x-show="open" x-cloak
             @keydown.escape.window="open = false"
             class="fixed inset-0 z-[60] flex items-center justify-center p-4">
            {# Backdrop #}
            <div x-show="open" x-transition:enter="transition ease-out duration-200" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100"
                 x-transition:leave="transition ease-in duration-150" x-transition:leave-start="opacity-100" x-transition:leave-end="opacity-0"
                 @click="open = false"
                 class="absolute inset-0 bg-black/60"></div>

            {# Modal Panel #}
            <div x-show="open" x-transition:enter="transition ease-out duration-200" x-transition:enter-start="opacity-0 scale-95" x-transition:enter-end="opacity-100 scale-100"
                 x-transition:leave="transition ease-in duration-150" x-transition:leave-start="opacity-100 scale-100" x-transition:leave-end="opacity-0 scale-95"
                 @click.stop
                 class="relative bg-[#2c2729] rounded-[6px] border border-[rgba(255,255,255,0.10)] shadow-xl w-full max-w-lg max-h-[80vh] overflow-y-auto z-10">

                {# Header #}
                <div class="flex items-center justify-between p-4 border-b border-[rgba(255,255,255,0.10)]">
                    <div>
                        <h3 class="text-base font-semibold text-slate-100">{{ info_title }}</h3>
                        {% if info_subtitle %}
                        <p class="text-xs text-slate-400 mt-0.5">{{ info_subtitle }}</p>
                        {% endif %}
                    </div>
                    <button @click="open = false" class="text-slate-400 hover:text-slate-200 transition-colors">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>

                {# Body #}
                <div class="p-4 text-sm text-slate-300 leading-relaxed">
                    {% if info_body_template is defined and info_body_template %}
                        {% include info_body_template %}
                    {% elif info_text is defined and info_text %}
                        <p>{{ info_text }}</p>
                    {% endif %}
                </div>

                {# Footer #}
                <div class="p-3 border-t border-[rgba(255,255,255,0.10)] text-right">
                    <button @click="open = false" class="px-3 py-1.5 text-xs font-medium text-slate-300 bg-[#342f31] rounded-[6px] hover:bg-[rgba(255,255,255,0.10)] transition-colors">
                        Close
                    </button>
                </div>
            </div>
        </div>
    </template>
</span>
```

2. Verify the component renders correctly by including it in the dashboard temporarily (this will be formalized in Task 5).

**Commit:** `feat: add reusable metric_info modal component`

---

## Task 2 — Create Metric Definition Body Templates

**Files:**
- CREATE `templates/components/metric_info/jcls_body.html`
- CREATE `templates/components/metric_info/ccf_body.html`
- CREATE `templates/components/metric_info/cit_body.html`
- CREATE `templates/components/metric_info/rv_body.html`

**Steps:**

1. Create the directory `templates/components/metric_info/`.

2. Create `jcls_body.html` with the full JcLS rubric table:

```html
{# JcLS Score - Full Rubric Body #}
<p class="mb-3">A 100-point evidence-based CPR quality rubric.</p>
<p class="text-xs text-slate-400 mb-4">Weights derived from published adjusted odds ratios for neurologically intact survival (CPC 1-2) from out-of-hospital cardiac arrest research.</p>

{# Tier Table #}
<div class="space-y-3">
    {# Tier 1 #}
    <div class="bg-[#252224] rounded-[6px] p-3 border border-[rgba(255,255,255,0.10)]">
        <h4 class="text-xs font-semibold text-slate-200 mb-2">Tier 1: Compression Quality (55 pts)</h4>
        <div class="space-y-1 text-xs text-slate-400">
            <div class="flex justify-between"><span>1A. Depth Compliance</span><span class="text-slate-300">20 pts</span></div>
            <div class="flex justify-between"><span>1B. Rate Compliance</span><span class="text-slate-300">15 pts</span></div>
            <div class="flex justify-between"><span>1C. Combined Compliance (CiT)</span><span class="text-slate-300">20 pts</span></div>
        </div>
    </div>

    {# Tier 2 #}
    <div class="bg-[#252224] rounded-[6px] p-3 border border-[rgba(255,255,255,0.10)]">
        <h4 class="text-xs font-semibold text-slate-200 mb-2">Tier 2: Perfusion Continuity (25 pts)</h4>
        <div class="space-y-1 text-xs text-slate-400">
            <div class="flex justify-between"><span>2A. CCF</span><span class="text-slate-300">15 pts</span></div>
            <div class="flex justify-between"><span>2B. Pause Quality</span><span class="text-slate-300">10 pts</span></div>
            <div class="pl-4 flex justify-between"><span>Mean Pause Duration</span><span class="text-slate-300">6 pts</span></div>
            <div class="pl-4 flex justify-between"><span>No Long Pauses (&gt;10s)</span><span class="text-slate-300">4 pts</span></div>
        </div>
    </div>

    {# Tier 3 #}
    <div class="bg-[#252224] rounded-[6px] p-3 border border-[rgba(255,255,255,0.10)]">
        <h4 class="text-xs font-semibold text-slate-200 mb-2">Tier 3: Recoil Quality (10 pts)</h4>
        <div class="space-y-1 text-xs text-slate-400">
            <div class="flex justify-between"><span>3A. Release Velocity</span><span class="text-slate-300">10 pts</span></div>
        </div>
    </div>

    {# Tier 4 #}
    <div class="bg-[#252224] rounded-[6px] p-3 border border-[rgba(255,255,255,0.10)]">
        <h4 class="text-xs font-semibold text-slate-200 mb-2">Tier 4: System Performance (10 pts)</h4>
        <div class="space-y-1 text-xs text-slate-400">
            <div class="flex justify-between"><span>4A. Time to First Compression</span><span class="text-slate-300">5 pts</span></div>
            <div class="flex justify-between"><span>4B. Time to First Shock</span><span class="text-slate-300">5 pts</span></div>
        </div>
    </div>
</div>

{# Color Bands #}
<div class="mt-4 flex items-center gap-3 text-xs">
    <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-green-500"></span> <span class="text-slate-400">&ge;80 Target Met</span></div>
    <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-yellow-500"></span> <span class="text-slate-400">60-79 Needs Improvement</span></div>
    <div class="flex items-center gap-1"><span class="w-3 h-3 rounded-full bg-red-500"></span> <span class="text-slate-400">&lt;60 Below Standard</span></div>
</div>

<p class="mt-3 text-xs text-slate-500 italic">Applied to real-call sessions only. Score scales proportionally when metrics are unavailable.</p>
```

3. Create `ccf_body.html`:

```html
{# CCF - Brief Info Body #}
<p>Chest Compression Fraction &mdash; the percentage of total CPR time spent actively delivering chest compressions.</p>
<p class="mt-2">Directly correlates with neurologically intact survival.</p>
<div class="mt-3 flex items-center gap-2 text-xs">
    <span class="px-2 py-0.5 bg-green-900/30 text-green-400 rounded font-medium">Target: &ge;80%</span>
</div>
<p class="mt-2 text-xs text-slate-500">Source: ZOLL defibrillator</p>
```

4. Create `cit_body.html`:

```html
{# CiT (Combined Compliance) - Brief Info Body #}
<p>Compressions in Target &mdash; the percentage of individual compressions where <strong class="text-slate-200">BOTH</strong> depth AND rate were simultaneously within the target range during that single compression.</p>
<p class="mt-2">More stringent than measuring depth% and rate% separately, because a compression can have good depth but bad rate (or vice versa).</p>
<div class="mt-3 flex items-center gap-2 text-xs">
    <span class="px-2 py-0.5 bg-amber-900/30 text-amber-400 rounded font-medium">Industry avg: ~35%</span>
</div>
<p class="mt-2 text-xs text-slate-500">Source: ZOLL defibrillator</p>
```

5. Create `rv_body.html`:

```html
{# Release Velocity - Brief Info Body #}
<p>Release Velocity measures how quickly the chest wall returns to its resting position after each compression.</p>
<p class="mt-2">Indicates quality of full chest recoil, which is critical for cardiac refill between compressions.</p>
<div class="mt-3 flex items-center gap-2 text-xs">
    <span class="px-2 py-0.5 bg-green-900/30 text-green-400 rounded font-medium">Target: &ge;400 mm/s</span>
    <span class="px-2 py-0.5 bg-amber-900/30 text-amber-400 rounded font-medium">Low variability: SD &lt;100</span>
</div>
<p class="mt-2 text-xs text-slate-500">Source: ZOLL defibrillator</p>
```

**Commit:** `feat: add metric definition body templates for info modals`

---

## Task 3 — Remove Quality Score from Python Backend

**Files:**
- MODIFY `app/mock_data.py`

**Steps:**

1. **In `get_dashboard_kpis()` (~line 522):** Remove the `quality` key from the inner `calc_metrics` helper. Specifically, delete line 541 (`avg_quality = round((avg_depth + avg_rate) / 2, 1)`) and change the return on line 542 to not include `"quality"`. Then remove these keys from the returned dict:
   - `"avg_quality_score"` (line 613)
   - `"real_quality_score"` (line 619)
   - `"sim_quality_score"` (line 625)

   Keep all other keys (depth, rate, ccf, jcls, etc.) intact.

2. **In `get_provider_stats()` (~line 648):** Remove the quality_score calculation at lines 710-711:
   ```python
   # DELETE these 2 lines:
   # Quality Score = (Depth Compliance + Rate Compliance) / 2
   quality_score = round((avg_depth_compliance + avg_rate_compliance) / 2, 1)
   ```
   Remove `"quality_score": quality_score` from the return dict (line 718). Add `"quality_score": 0` to the empty-stats early return dict (line 657) **only if backwards compatibility is needed during transition** -- actually, remove it from both. Also add `avg_jcls_score` to the stats dict by computing it from real-call sessions for this provider:

   After the existing averages calculation block (around line 707), add:
   ```python
   # Compute avg JcLS from real-call sessions
   jcls_values_list = [s.get("metrics", {}).get("jcls_score") for s in real_calls
                       if s.get("metrics", {}).get("jcls_score") is not None]
   avg_jcls_score = round(sum(jcls_values_list) / len(jcls_values_list), 1) if jcls_values_list else None
   ```
   Add `"avg_jcls_score": avg_jcls_score` to the return dict.

3. **In `_calculate_stats_for_sessions()` (~line 734):** Remove quality_score calculation at line 788:
   ```python
   # DELETE:
   quality_score = round((avg_depth + avg_rate) / 2, 1) if (avg_depth or avg_rate) else 0
   ```
   Remove `"quality_score": quality_score` from the return dict (line 794). Remove `"quality_score": 0` from the empty return dict (line 744). Add avg JcLS computation:
   ```python
   jcls_vals = [s.get("metrics", {}).get("jcls_score") for s in real_calls
                if s.get("metrics", {}).get("jcls_score") is not None]
   avg_jcls_score = round(sum(jcls_vals) / len(jcls_vals), 1) if jcls_vals else None
   ```
   Add `"avg_jcls_score": avg_jcls_score` to both return dicts (empty and computed).

4. **In `get_ranked_providers()` (~line 865):** The function already computes `avg_jcls`. Keep that. Remove the `quality_score` key from the appended dict (line 885). Update sort key (line 895) to remove `x["quality_score"]` fallback -- use depth compliance as fallback:
   ```python
   provider_stats.sort(key=lambda x: (x["session_count"] > 0, x.get("avg_jcls_score") or 0, x["avg_depth_compliance"]), reverse=True)
   ```

5. **In `get_ranked_providers_by_type()` (~line 899):** Remove `quality_score = round((avg_depth + avg_rate) / 2, 1)` (line 936). Remove `"quality_score": quality_score` from the appended dict (line 947). Update sort key (line 956) to remove quality_score fallback:
   ```python
   provider_stats.sort(key=lambda x: (x.get("avg_jcls_score") or 0, x["avg_depth_compliance"]), reverse=True)
   ```

6. **In `get_real_call_teams()` (~line 1001):** Remove the `quality_score` calculation at line 1059:
   ```python
   # DELETE:
   quality_score = round((depth_compliance + rate_compliance) / 2, 1)
   ```
   Remove `"quality_score": quality_score` from the team dict (line 1088). Remove `calculate_team_score` call (line 1063) and `team_score` from the dict (line 1087). **Replace** with session JcLS score:
   ```python
   jcls_score = metrics.get("jcls_score")
   ```
   Add `"jcls_score": jcls_score` to the team dict. Keep the sort key map but replace `"team_score"` and `"quality_score"` keys with `"jcls_score"`:
   ```python
   sort_key_map = {
       "jcls_score": lambda x: x.get("jcls_score") or 0,
       "ccf": lambda x: x["ccf"],
       "depth_compliance": lambda x: x["depth_compliance"],
       "rate_compliance": lambda x: x["rate_compliance"],
       "total_compressions": lambda x: x["total_compressions"],
       "date": lambda x: x["date"] or "",
   }
   sort_key = sort_key_map.get(sort_by, sort_key_map["jcls_score"])
   ```

7. **Delete `calculate_team_score()` function** (~lines 965-998). It is no longer called anywhere.

**Commit:** `refactor: remove quality_score and team_score from backend calculations`

---

## Task 4 — Add Trend Data to Dashboard KPIs

**Files:**
- MODIFY `app/mock_data.py` (in `get_dashboard_kpis()`)
- MODIFY `app/routers/pages.py` (dashboard route)

**Steps:**

1. **In `get_dashboard_kpis()`**, after the existing JcLS/CiT/RV averages block (~line 604), add trend data collection. Iterate over real-call sessions sorted by date and collect `{date, value}` dicts for each metric:

```python
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
```

2. Add these four keys to the return dict:
```python
"jcls_trend": jcls_trend,
"ccf_trend": ccf_trend,
"cit_trend": cit_trend,
"rv_trend": rv_trend,
```

3. No changes needed in `pages.py` for the dashboard route -- it already passes `kpis` which will now contain the trend arrays. The template will access them as `kpis.jcls_trend` etc.

**Commit:** `feat: add trend data arrays to dashboard KPIs`

---

## Task 5 — Update Dashboard Template

**Files:**
- MODIFY `templates/pages/dashboard.html`

**Steps:**

1. **Add `?` info buttons to the primary KPI row (lines 11-54).** For the JcLS card and CCF card, add the info button after the `stat_card.html` include. Since `stat_card.html` is a self-contained include, we will instead place the `?` button as a sibling element. The cleanest approach: wrap each metric KPI card in a `<div>` with `relative` positioning and place the `?` button absolutely in the top-right. However, since stat_card.html is an include, we should instead add the info button *before* the include by setting the variable, then place the include, then overlay. Actually the simplest approach is to put the info button right after the include inside the grid cell.

   Replace the JcLS Score card block (lines 12-20) with:
   ```html
   {# JcLS Score -- Hero Card #}
   <div class="relative">
       {% set stat_label = "JcLS Score" %}
       {% set stat_value = kpis.avg_jcls_score if kpis.avg_jcls_score else "--" %}
       {% set stat_icon = "heart" %}
       {% set stat_icon_bg = "bg-red-900/20" %}
       {% set stat_icon_color = "text-[#dc2626]" %}
       {% set stat_trend = "" %}
       {% set stat_trend_direction = "neutral" %}
       {% set stat_trend_label = "Real calls only" %}
       {% include "components/stat_card.html" %}
       <div class="absolute top-2 right-2">
           {% set info_id = "jcls" %}
           {% set info_title = "JcLS Score" %}
           {% set info_subtitle = "Jordan's Clinical Scoring" %}
           {% set info_body_template = "components/metric_info/jcls_body.html" %}
           {% set info_text = "" %}
           {% include "components/metric_info.html" %}
       </div>
   </div>
   ```

   Do the same for the CCF card (lines 23-31), CiT card, and Release Velocity card using appropriate `info_id`, `info_title`, `info_subtitle`, and `info_body_template`/`info_text` values.

2. **Remove the "ZOLL Quality Score" card from the secondary KPI row (lines 84-92).** Delete the entire `<div>` block for the ZOLL Quality Score card. Change the grid from `sm:grid-cols-3` to `sm:grid-cols-2` since there are now only 2 items (CiT and Release Velocity). Also add `?` info buttons to the CiT and Release Velocity cards:

   For CiT card (lines 59-65), add inside the card div:
   ```html
   <div class="absolute top-2 right-2">
       {% set info_id = "cit" %}
       {% set info_title = "CiT (Combined Compliance)" %}
       {% set info_subtitle = "Compressions in Target" %}
       {% set info_body_template = "components/metric_info/cit_body.html" %}
       {% set info_text = "" %}
       {% include "components/metric_info.html" %}
   </div>
   ```
   (And wrap the CiT card in `<div class="relative">`)

   For Release Velocity card (lines 68-82), same pattern with `rv` info.

3. **Remove the "Real Life Quality Score" summary bar** (lines 270-285, the block with `kpis.real_quality_score`). Delete the entire `<div class="mt-6 p-4 rounded-lg ...">` block.

4. **Remove the "Simulated Quality Score" summary bar** (lines 342-357, the block with `kpis.sim_quality_score`). Delete the entire `<div class="mt-6 p-4 rounded-lg ...">` block.

5. **Update the Simulated Top Performers section** (lines 434-461). Remove the quality_score display (line 449: `<span class="text-sm text-slate-400">{{ performer.quality_score }}%</span>`). Replace with session count:
   ```html
   <span class="text-xs text-slate-400">{{ performer.session_count }} session{% if performer.session_count != 1 %}s{% endif %}</span>
   ```

6. **Add expandable trend graphs below the primary KPI row.** After the primary KPI grid (after line 54), add a new section with 4 collapsible trend charts. Use Alpine.js `x-data` to manage open/close state per metric, and Chart.js for rendering. The charts should lazy-initialize on first open:

```html
{# Expandable Trend Graphs #}
<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6" x-data="dashboardTrends()">
    {# JcLS Trend #}
    <div class="bg-[#2c2729] rounded-[6px] border border-[rgba(255,255,255,0.10)] shadow-sm overflow-hidden">
        <button @click="toggle('jcls')" class="w-full flex items-center justify-between p-3 hover:bg-[#252224] transition-colors">
            <span class="text-sm font-medium text-slate-300">JcLS Trend</span>
            <svg :class="open.jcls ? 'rotate-180' : ''" class="w-4 h-4 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
        </button>
        <div x-show="open.jcls" x-collapse>
            <div class="p-3 pt-0">
                <canvas x-ref="jclsChart" class="w-full" height="160"></canvas>
            </div>
        </div>
    </div>

    {# CCF Trend #}
    <div class="bg-[#2c2729] rounded-[6px] border border-[rgba(255,255,255,0.10)] shadow-sm overflow-hidden">
        <button @click="toggle('ccf')" class="w-full flex items-center justify-between p-3 hover:bg-[#252224] transition-colors">
            <span class="text-sm font-medium text-slate-300">CCF Trend</span>
            <svg :class="open.ccf ? 'rotate-180' : ''" class="w-4 h-4 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
        </button>
        <div x-show="open.ccf" x-collapse>
            <div class="p-3 pt-0">
                <canvas x-ref="ccfChart" class="w-full" height="160"></canvas>
            </div>
        </div>
    </div>

    {# CiT Trend #}
    <div class="bg-[#2c2729] rounded-[6px] border border-[rgba(255,255,255,0.10)] shadow-sm overflow-hidden">
        <button @click="toggle('cit')" class="w-full flex items-center justify-between p-3 hover:bg-[#252224] transition-colors">
            <span class="text-sm font-medium text-slate-300">CiT Trend</span>
            <svg :class="open.cit ? 'rotate-180' : ''" class="w-4 h-4 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
        </button>
        <div x-show="open.cit" x-collapse>
            <div class="p-3 pt-0">
                <canvas x-ref="citChart" class="w-full" height="160"></canvas>
            </div>
        </div>
    </div>

    {# Release Velocity Trend #}
    <div class="bg-[#2c2729] rounded-[6px] border border-[rgba(255,255,255,0.10)] shadow-sm overflow-hidden">
        <button @click="toggle('rv')" class="w-full flex items-center justify-between p-3 hover:bg-[#252224] transition-colors">
            <span class="text-sm font-medium text-slate-300">Release Velocity Trend</span>
            <svg :class="open.rv ? 'rotate-180' : ''" class="w-4 h-4 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
        </button>
        <div x-show="open.rv" x-collapse>
            <div class="p-3 pt-0">
                <canvas x-ref="rvChart" class="w-full" height="160"></canvas>
            </div>
        </div>
    </div>
</div>

<script>
function dashboardTrends() {
    const trendData = {
        jcls: {{ kpis.jcls_trend | tojson }},
        ccf: {{ kpis.ccf_trend | tojson }},
        cit: {{ kpis.cit_trend | tojson }},
        rv: {{ kpis.rv_trend | tojson }},
    };
    const targets = { jcls: 80, ccf: 80, cit: 35, rv: 400 };
    const colors = {
        jcls: 'rgb(220, 38, 38)',
        ccf: 'rgb(22, 163, 74)',
        cit: 'rgb(249, 115, 22)',
        rv: 'rgb(147, 51, 234)',
    };
    const charts = {};

    return {
        open: { jcls: false, ccf: false, cit: false, rv: false },
        toggle(key) {
            this.open[key] = !this.open[key];
            if (this.open[key] && !charts[key]) {
                this.$nextTick(() => {
                    const canvas = this.$refs[key + 'Chart'];
                    if (!canvas) return;
                    const data = trendData[key] || [];
                    charts[key] = new Chart(canvas, {
                        type: 'line',
                        data: {
                            labels: data.map(d => d.date),
                            datasets: [
                                {
                                    label: key.toUpperCase(),
                                    data: data.map(d => d.value),
                                    borderColor: colors[key],
                                    backgroundColor: colors[key].replace('rgb', 'rgba').replace(')', ', 0.1)'),
                                    tension: 0.3,
                                    pointRadius: 4,
                                    pointHoverRadius: 6,
                                    fill: false,
                                },
                                {
                                    label: 'Target',
                                    data: data.map(() => targets[key]),
                                    borderColor: 'rgba(255,255,255,0.2)',
                                    borderDash: [5, 5],
                                    pointRadius: 0,
                                    fill: false,
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: {
                                    callbacks: {
                                        label: (ctx) => ctx.dataset.label + ': ' + ctx.parsed.y + (key === 'rv' ? ' mm/s' : (key === 'jcls' ? '' : '%'))
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: key !== 'rv',
                                    grid: { color: 'rgba(255,255,255,0.05)' },
                                    ticks: { color: 'rgb(148,163,184)', font: { size: 10 } }
                                },
                                x: {
                                    grid: { display: false },
                                    ticks: { color: 'rgb(148,163,184)', font: { size: 10 }, maxRotation: 45 }
                                }
                            }
                        }
                    });
                });
            }
        }
    };
}
</script>
```

**Commit:** `feat: update dashboard - remove ZOLL Quality Score, add info buttons and trend graphs`

---

## Task 6 — Update Rankings Page

**Files:**
- MODIFY `templates/pages/rankings.html`

**Steps:**

1. **Delete the info bar** (lines 11-20). Remove the entire `<div class="bg-[#2c2729] ...">` block that says "Rankings are based on Quality Score = (Depth + Rate) / 2".

2. **Simulated provider rankings table (lines 70-136):**
   - Change column header from `Quality Score` to `Depth %` and `Rate %` only. Actually, the table already has Depth % and Rate % columns. So **remove the Quality Score column header** at line 90: delete `<th class="px-4 py-3 font-medium">Quality Score</th>`.
   - Remove the Quality Score data cell at line 116: delete `<td class="px-4 py-3 text-slate-200 font-bold">{{ provider.quality_score }}%</td>`.
   - Update the empty-state colspan from 6 to 5 (line 122).

3. **Real-life provider rankings table (lines 138-204):**
   - Change column header from `Quality Score` to `JcLS` at line 158: replace `<th class="px-4 py-3 font-medium">Quality Score</th>` with `<th class="px-4 py-3 font-medium">JcLS</th>`.
   - Replace the Quality Score data cell at line 184 with a JcLS display using colored dot:
     ```html
     <td class="px-4 py-3">
         {% if provider.avg_jcls_score %}
         <div class="flex items-center gap-1.5">
             <span class="w-2 h-2 rounded-full flex-shrink-0
                 {% if provider.avg_jcls_score >= 80 %}bg-green-500
                 {% elif provider.avg_jcls_score >= 60 %}bg-yellow-500
                 {% else %}bg-red-500{% endif %}"></span>
             <span class="font-bold text-slate-200">{{ provider.avg_jcls_score }}</span>
         </div>
         {% else %}
         <span class="text-slate-400">&mdash;</span>
         {% endif %}
     </td>
     ```

4. **Team rankings table (lines 207-298):**
   - Change column header from `Quality Score` to `JcLS` at line 228: replace `<th class="px-4 py-3 font-medium">Quality Score</th>` with `<th class="px-4 py-3 font-medium">JcLS</th>`.
   - Replace the Quality Score data cell (lines 262-265) with JcLS display:
     ```html
     <td class="px-4 py-3">
         {% if team.jcls_score %}
         <span class="font-bold {% if team.jcls_score >= 80 %}text-[#16a34a]{% elif team.jcls_score >= 60 %}text-amber-500{% else %}text-[#dc2626]{% endif %}">
             {{ team.jcls_score }}
         </span>
         {% else %}
         <span class="text-slate-400">&mdash;</span>
         {% endif %}
     </td>
     ```

**Commit:** `refactor: update rankings page - remove Quality Score, add JcLS`

---

## Task 7 — Update Provider Detail Page

**Files:**
- MODIFY `templates/pages/provider_detail.html`

**Steps:**

1. **"As Team Lead" summary card (lines 91-95):** Replace `Quality: <span ...>{{ detailed_stats.as_lead.quality_score }}%</span>` with JcLS:
   ```html
   {% if detailed_stats.as_lead.avg_jcls_score %}
   <div class="mt-3 pt-3 border-t border-[rgba(255,255,255,0.10)] text-xs text-slate-400">
       JcLS: <span class="font-medium {% if detailed_stats.as_lead.avg_jcls_score >= 80 %}text-green-400{% elif detailed_stats.as_lead.avg_jcls_score >= 60 %}text-yellow-400{% else %}text-red-400{% endif %}">{{ detailed_stats.as_lead.avg_jcls_score }}</span>
   </div>
   {% endif %}
   ```
   (Note: `avg_jcls_score` will be added to `_calculate_stats_for_sessions` return dict in Task 3.)

2. **"As Provider" summary card (lines 111-115):** Same change as above but referencing `detailed_stats.as_provider.avg_jcls_score`.

3. **"Combined Quality Score" summary card (lines 118-134):** Replace the entire card. Change label from "Combined Quality" to "Avg JcLS". Change `{{ detailed_stats.combined.quality_score }}%` to `{{ detailed_stats.combined.avg_jcls_score if detailed_stats.combined.avg_jcls_score else "--" }}`. Update subtitle from "All sessions combined" to "Real calls only". Add JcLS color indicator.

4. **"As Team Lead Stats" breakdown section (lines 190-194):** Replace `Quality Score` label/value pair with JcLS:
   ```html
   <div class="flex justify-between items-center">
       <span class="text-sm text-slate-300">JcLS Score</span>
       {% if detailed_stats.as_lead.avg_jcls_score %}
       <span class="text-sm font-semibold {% if detailed_stats.as_lead.avg_jcls_score >= 80 %}text-green-400{% elif detailed_stats.as_lead.avg_jcls_score >= 60 %}text-yellow-400{% else %}text-red-400{% endif %}">
           {{ detailed_stats.as_lead.avg_jcls_score }}
       </span>
       {% else %}
       <span class="text-sm text-slate-400">&mdash;</span>
       {% endif %}
   </div>
   ```

5. **"As Provider Stats" breakdown section (lines 231-234):** Same replacement as above, using `detailed_stats.as_provider.avg_jcls_score`.

6. **"Combined Stats" breakdown section (lines 272-275):** Same replacement using `detailed_stats.combined.avg_jcls_score`.

7. **Chart panel metric options (line 309):** Replace `"Quality Score"` with `"JcLS Score"`:
   ```python
   {% set chart_options = ["JcLS Score", "Depth Compliance", "Rate Compliance"] %}
   ```

8. **Recent Sessions inline list (lines 318-336):** Replace the `session_quality` calculation (line 321) and display. Instead of computing `(depth_pct + rate_pct) / 2`, show JcLS if available, otherwise show `--`:
   ```html
   {% set jcls = session.metrics.get('jcls_score') if session.metrics else none %}
   ```
   Replace the quality display (line 328) with:
   ```html
   {% if jcls is not none %}
   <div class="flex items-center gap-1">
       <span class="w-2 h-2 rounded-full {% if jcls >= 80 %}bg-green-500{% elif jcls >= 60 %}bg-yellow-500{% else %}bg-red-500{% endif %}"></span>
       <span class="text-sm font-medium text-slate-300">{{ jcls }}</span>
   </div>
   {% elif session.session_type == 'real_call' %}
   <span class="text-xs text-slate-400">No JcLS</span>
   {% else %}
   <span class="text-xs text-slate-400">Sim</span>
   {% endif %}
   ```

**Commit:** `refactor: update provider detail page - replace Quality Score with JcLS`

---

## Task 8 — Update Team Analysis Page

**Files:**
- MODIFY `templates/pages/team_analysis.html`
- MODIFY `app/routers/pages.py` (team_analysis route)

**Steps:**

1. **"Avg Quality Score" stat card (lines 27-40):** Replace the label and value. Change `avg_quality` to `avg_jcls`:
   - Label: `Avg JcLS Score`
   - Value: `{{ avg_jcls }}` (instead of `{{ avg_quality }}%`)
   - Add JcLS color class to the value.

2. **"Best Team Score" stat card (lines 61-78):** Replace `team_score` with `jcls_score`:
   - Value: `{{ best_team.jcls_score if best_team.jcls_score else "--" }}`
   - Label: `Best JcLS Score`

3. **Performance Trend Chart (lines 109-275):**
   - Remove "Quality Score" dataset (lines 147-156) from `allDatasets`
   - Remove "Team Score" dataset (lines 167-176)
   - Replace with a single "JcLS Score" dataset
   - Update the select dropdown options: remove `<option value="quality">Quality Score</option>` and `<option value="team_score">Team Score</option>`, add `<option value="jcls">JcLS Score</option>`
   - Update the filter logic in the change handler accordingly
   - The route will need to pass `chart_jcls` data (see step 8 below)

4. **Sort options (lines 278-311):**
   - Replace `<a href="/teams?sort_by=team_score" ...>Team Score</a>` with `<a href="/teams?sort_by=jcls_score" ...>JcLS Score</a>`
   - Remove the `<a href="/teams?sort_by=quality_score" ...>Quality Score</a>` link entirely

5. **Team rankings table header (lines 321-334):**
   - Replace `<th ...>Score</th>` (line 327, the team_score column) with `<th ...>JcLS</th>`
   - Remove `<th ...>Quality</th>` column (line 329)

6. **Team rankings table body (lines 336-453):**
   - Replace team_score cell (line 395): `{{ team.team_score }}` with JcLS display:
     ```html
     <td class="px-4 py-3">
         {% if team.jcls_score %}
         <span class="font-semibold {% if team.jcls_score >= 80 %}text-green-400{% elif team.jcls_score >= 60 %}text-yellow-400{% else %}text-red-400{% endif %}">
             {{ team.jcls_score }}
         </span>
         {% else %}
         <span class="text-slate-400">&mdash;</span>
         {% endif %}
     </td>
     ```
   - Remove the quality_score cell at line 410: `<td ...>{{ team.quality_score }}%</td>`
   - Update `colspan` in the empty state from 11 to 10

7. **Delete the "Score Explanation Card"** at the bottom (lines 458-480). Remove the entire `<div class="mt-6 bg-[#252224] ...">` block that explains "Team Score = 40% CCF + 30% QS + 15% Depth + 15% Rate".

8. **Update the `team_analysis` route in `app/routers/pages.py`** (lines 176-241):
   - Change the default `sort_by` parameter from `"team_score"` to `"jcls_score"`
   - Replace `avg_quality` calculation (lines 191-193): compute `avg_jcls` instead:
     ```python
     jcls_scores = [t["jcls_score"] for t in team_instances if t.get("jcls_score")]
     avg_jcls = round(sum(jcls_scores) / len(jcls_scores), 1) if jcls_scores else 0
     ```
   - Update `best_team` to use jcls_score sort:
     ```python
     best_team_list = get_real_call_teams(sort_by="jcls_score")
     ```
   - Replace chart data: remove `chart_quality` and `chart_team_score`, add `chart_jcls`:
     ```python
     chart_jcls = [t.get("jcls_score") or 0 for t in trend_data_sorted]
     ```
   - Update template context: remove `avg_quality`, `chart_quality`, `chart_team_score`. Add `avg_jcls`, `chart_jcls`.

**Commit:** `refactor: update team analysis page - replace Team Score and Quality Score with JcLS`

---

## Task 9 — Update Other Templates (Providers Table, Teams Table, Rankings Partials)

**Files:**
- MODIFY `templates/pages/providers.html`
- MODIFY `templates/partials/providers/table.html`
- MODIFY `templates/partials/rankings/providers.html`
- MODIFY `templates/partials/rankings/teams.html`
- MODIFY `templates/partials/teams/table.html`

**Steps:**

1. **`templates/pages/providers.html` (lines 104-224):**
   - Change column header at line 111 from `Quality Score` to `JcLS`
   - Replace the quality score data cell (lines 152-160) with JcLS display:
     ```html
     <td class="px-4 py-3 text-slate-200">
         {% if provider.stats and provider.stats.avg_jcls_score %}
         <span class="font-medium {% if provider.stats.avg_jcls_score >= 80 %}text-[#16a34a]{% elif provider.stats.avg_jcls_score >= 60 %}text-amber-600{% else %}text-[#dc2626]{% endif %}">
             {{ provider.stats.avg_jcls_score }}
         </span>
         {% elif provider.stats and provider.stats.session_count > 0 %}
         <span class="text-slate-400">&mdash;</span>
         {% else %}
         <span class="text-slate-400">&mdash;</span>
         {% endif %}
     </td>
     ```

2. **`templates/partials/providers/table.html` (lines 1-89):**
   - Change column header at line 7 from `Quality Score` to `JcLS`
   - Replace quality_score cell (line 35) from `{{ provider.quality_score }}%` to JcLS display:
     ```html
     <td class="px-4 py-3">
         {% if provider.avg_jcls_score %}
         <span class="font-bold {% if provider.avg_jcls_score >= 80 %}text-[#16a34a]{% elif provider.avg_jcls_score >= 60 %}text-amber-500{% else %}text-[#dc2626]{% endif %}">
             {{ provider.avg_jcls_score }}
         </span>
         {% else %}
         <span class="text-slate-400">&mdash;</span>
         {% endif %}
     </td>
     ```

3. **`templates/partials/rankings/providers.html` (lines 1-55):**
   - Change column header at line 8 from `Quality Score` to `JcLS`
   - Replace quality_score cell (line 35) same as above

4. **`templates/partials/rankings/teams.html` (lines 1-53):**
   - Change column header at line 10 from `Quality Score` to `JcLS`
   - The data cells currently show `--` (placeholder), which is fine. If data is wired up later, it will use `jcls_score`.

5. **`templates/partials/teams/table.html` (lines 1-40):**
   - Change column header at line 9 from `Quality Score` to `JcLS`
   - Same placeholder `--` is fine for now.

**Commit:** `refactor: update provider/team tables - rename Quality Score to JcLS`

---

## Task 10 — Update Session Detail Modal

**Files:**
- MODIFY `templates/partials/sessions/detail_modal.html`

**Steps:**

1. **Remove the "ZOLL Quality Score" reference line** (line 173). In the JcLS hero score section, find:
   ```html
   {% if session.metrics.compressions_in_target_percent is not none %}
   <p class="text-xs text-slate-500 mt-1">ZOLL Quality Score: {{ ((session.metrics.correct_depth_percent or 0) + (session.metrics.correct_rate_percent or 0)) / 2 | round(1) }}%</p>
   {% endif %}
   ```
   Delete these 3 lines entirely (lines 172-174).

**Commit:** `fix: remove ZOLL Quality Score reference from session detail modal`

---

## Task 11 — Clean Up Unused Code

**Files:**
- MODIFY `app/mock_data.py`
- MODIFY `app/routers/pages.py`

**Steps:**

1. **Verify `calculate_team_score()` is deleted** (done in Task 3). Grep the codebase for any remaining references to `calculate_team_score` and remove them.

2. **In `app/routers/pages.py`**, verify no route passes `quality_score` or `team_score` variables that are no longer used:
   - Dashboard route (line 50-64): verify `top_performers` still works. `get_top_performers()` calls `get_ranked_providers()` which was updated in Task 3. The `quality_score` field may still be in the returned dicts from `get_ranked_providers`. If so, it is harmless but unused. No template references it anymore after Task 5.
   - Rankings route (line 159-173): No changes needed, the functions return updated dicts.

3. **Grep for remaining `quality_score` references in all templates.** Any lingering references should be cleaned up:
   - Search `templates/` recursively for `quality_score`
   - If found in any file not covered by Tasks 5-10, update accordingly.

4. **Grep for remaining `team_score` references in all templates.**
   - Search `templates/` recursively for `team_score`
   - If found in any file not covered by Tasks 5-10, update accordingly.

5. **In `app/mock_data.py`, clean up the `get_top_performers()` function** (line 859-862). It delegates to `get_ranked_providers()`. No changes needed as long as the template uses updated field names. But verify the dashboard top performers section references the right fields.

6. **In `app/mock_data.py`, clean up the `calc_metrics` helper** inside `get_dashboard_kpis()`. After removing `quality`, the function should only return `{"depth": ..., "rate": ..., "ccf": ...}`. Verify callers use the new keys.

**Commit:** `chore: clean up unused quality_score and team_score references`

---

## Summary of All Files Touched

| File | Action | Tasks |
|------|--------|-------|
| `templates/components/metric_info.html` | CREATE | 1 |
| `templates/components/metric_info/jcls_body.html` | CREATE | 2 |
| `templates/components/metric_info/ccf_body.html` | CREATE | 2 |
| `templates/components/metric_info/cit_body.html` | CREATE | 2 |
| `templates/components/metric_info/rv_body.html` | CREATE | 2 |
| `app/mock_data.py` | MODIFY | 3, 4, 11 |
| `app/routers/pages.py` | MODIFY | 4, 8, 11 |
| `templates/pages/dashboard.html` | MODIFY | 5 |
| `templates/pages/rankings.html` | MODIFY | 6 |
| `templates/pages/provider_detail.html` | MODIFY | 7 |
| `templates/pages/team_analysis.html` | MODIFY | 8 |
| `templates/pages/providers.html` | MODIFY | 9 |
| `templates/partials/providers/table.html` | MODIFY | 9 |
| `templates/partials/rankings/providers.html` | MODIFY | 9 |
| `templates/partials/rankings/teams.html` | MODIFY | 9 |
| `templates/partials/teams/table.html` | MODIFY | 9 |
| `templates/partials/sessions/detail_modal.html` | MODIFY | 10 |

## Execution Order & Dependencies

```
Task 1 (metric_info component) ----+
                                    |
Task 2 (metric body templates) ----+--> Task 5 (dashboard)
                                    |
Task 3 (remove quality_score) -----+--> Task 6 (rankings)
                                    |-> Task 7 (provider detail)
Task 4 (trend data) ---------------+--> Task 5 (dashboard)
                                    |-> Task 8 (team analysis)
                                    |-> Task 9 (other templates)
                                    |-> Task 10 (session modal)
                                    +-> Task 11 (cleanup)
```

Tasks 1-4 can be done in parallel. Tasks 5-10 depend on Tasks 1-4. Task 11 is last.
