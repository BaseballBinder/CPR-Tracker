Working Assumptions Confirmed

Admin-only system; providers do not log in or access the app directly.

Primary inputs: CSV import and paste-from-text (ChatGPT analysis output).

Session entry uses a guided modal wizard to enforce format and reduce errors.

Non-identifiable clinical data only; no patient identifiers stored.

CPRReports include charts + tables with trends and improvement metrics.

Time ranges: event-to-event, weekly, monthly, yearly, all-time.

Visual tone: fire department professional, reds + slate + dark neutrals; I will pick a modern humanist sans.

A) Product UX Principles + Navigation Map

Principle: calm, high-readability data-first layout with generous whitespace and strict typographic hierarchy.

Principle: error-proof data entry; emphasize guided steps and inline validation.

Principle: rapid report generation; reduce clicks between provider selection and export.

Principle: separate clinical event data visually from operational metadata (even if non-identifiable).

Principle: mobile-friendly table views with stacked card fallbacks.

Navigation map: Sidebar + Topbar

Sidebar: Dashboard, Sessions, Providers, Rankings, Team Analysis, CPRReports, Import/Export, Settings.

Topbar: Search, Date range selector, Quick Export button, Admin profile menu.

Tradeoff: a single global date range filter simplifies trends but may hide outliers; default to global with per-page override.

B) Design System

Color palette, light mode required

Primary: Fire Red 600 for primary actions and emphasis.

Secondary: Slate 700 for text and secondary controls.

Surface: Slate 50 and Slate 100 for panels; White for base.

Accent: Ember 500 for highlights; Steel 500 for neutral accents.

Status: Success Green 600, Warning Amber 600, Error Red 700, Info Blue 600.

Patient-data separation: Pale Warm Gray 100 background with a thin Ember 300 border and “Clinical Event Data” label.

Dark mode optional: invert surfaces to Slate 900/800, keep Fire Red 500 as primary, ensure contrast.

Typography

Font: Source Sans 3, fallback to system sans.

Scale: 12, 14, 16, 18, 20, 24, 30, 36.

Use: 16 body, 14 secondary, 20 section headers, 30 page title.

Spacing, radius, shadows

Spacing: 4, 8, 12, 16, 24, 32, 48.

Radius: 6 for inputs/cards, 999 for pills.

Shadows: subtle 1-level for cards; no heavy shadows.

Components styling

Buttons: primary filled red, secondary outline slate, tertiary ghost.

Forms: grouped fields, clear labels, inline help; error states in red with helper text.

Tables: sticky header, zebra rows, hover highlight; empty state with CTA.

Badges: neutral, success, warning, error, info; compliance colors used only for status.

Accessibility

Contrast: at least 4.5:1 for text, 3:1 for large text and UI elements.

Keyboard: focus ring always visible; skip links for tables.

Motion: short, purposeful transitions; no auto-animated charts on load for low-end devices.

C) Page-by-Page Skeleton Spec

Dashboard

Purpose: glanceable metrics, trends, and quick exports.

Primary CTA: Quick Export CPRReport.

Filters: date range, event type, provider, team, location type.

Layout: KPI row, trend charts, top performers, recent sessions.

Tables: recent sessions with key metrics.

Empty state: “No sessions yet” with Import CTA.

Error state: failed data load with retry.

Loading: skeleton cards + chart placeholders.

Rankings

Purpose: rank providers and teams by key CPR metrics.

Primary CTA: Export rankings report.

Filters: date range, metric selector, event type.

Layout: metric selector bar, two tabs or sections for Provider and Team.

Tables: rank, provider/team, metric value, change from last period.

Empty state: guidance to import sessions.

Error/loading: same as Dashboard.

Sessions List

Purpose: browse and search all sessions.

Primary CTA: New Session.

Filters: date range, event type, outcome, provider, team.

Layout: filters + table; optional summary row.

Columns: date/time, event type, team, key CPR metrics, outcome, actions.

Empty state: “No sessions match filters”.

Error/loading: standard.

New Session (wizard modal)

Purpose: guided data entry.

Primary CTA: Save Session.

Steps: 1) Event context, 2) Team/providers, 3) CPR metrics, 4) Outcomes/notes, 5) Review.

Validation: inline with step blocking.

Empty state: not applicable.

Error/loading: field-level errors and save failure toast.

Providers List

Purpose: manage provider roster and view performance.

Primary CTA: Add Provider.

Filters: status, team, certification level.

Layout: table + quick stats.

Columns: name, team, activity count, last session, trend indicator.

Empty state: add provider CTA.

Provider Detail

Purpose: individual performance and reports.

Primary CTA: Export CPRReport for provider.

Filters: date range, event type.

Layout: header stats, trend charts, session table.

Tables: sessions with key CPR metrics and outcomes.

Empty state: no sessions.

Team Analysis

Purpose: analyze team combinations and outcomes.

Primary CTA: Export team report.

Filters: date range, team combo size, event type.

Layout: combo ranking table + chart trends.

Tables: team combo, sessions count, target metrics, change.

Empty state: no combos.

CPRReports

Purpose: generate and export reports (provider, team, department).

Primary CTA: Export report.

Filters: report target (provider/team/department), scope (event, range, all-time).

Layout: report builder panel + preview.

Tables: summary metrics and per-session details.

Empty state: prompt to select a target.

Error/loading: export failure toast, preview skeleton.

Import/Export

Purpose: ingest data and export raw datasets.

Primary CTA: Import CSV or Paste Text.

Layout: import panel, validation results, import history.

Tables: recent imports with status.

Empty state: instructions for CSV format and paste template.

Settings

Purpose: system configuration and data definitions.

Primary CTA: Save settings.

Layout: tabs for teams, providers, metrics definitions, export formats.

Empty state: not applicable.

D) Reusable Components

PageHeader: title, subtitle, actions, breadcrumbs.

FiltersBar: filter chips, date range, apply/reset.

StatCard: KPI display with trend delta.

ChartPanel: chart with legend, tooltip, and empty state.

DataTable: sortable table with sticky header and pagination.

WizardModal: step-based input with progress.

FieldGroup: label, input, helper, error.

Badge: status indicator with compliance color.

EmptyState: illustration, description, CTA.

Toast: success/error notifications.

Skeleton: loading placeholders.

E) HTMX Interaction Plan

HTMX partials: filters update tables and charts on Dashboard, Rankings, Sessions, Provider Detail, Team Analysis.

Modal patterns: WizardModal loads step content via partial; next/back loads without page refresh.

Validation feedback: server-side validation returns partial with inline errors; toast on save.

Export: button triggers server job and returns download link or inline status message.

F) Implementation Handoff Pack for Claude

Suggested template/file structure

base.html, /templates/partials/, /templates/pages/.

/templates/partials include: filters, table, statcard, chartpanel, wizard steps.

/static/css for Tailwind output, /static/js for Alpine and Chart.js initializers.

Route list and templates

/ Dashboard -> dashboard.html.

/sessions -> sessions.html.

/sessions/new -> wizard_step_1.html through wizard_step_5.html.

/providers -> providers.html.

/providers/{id} -> provider_detail.html.

/rankings -> rankings.html.

/teams -> team_analysis.html.

/reports -> reports.html.

/import-export -> import_export.html.

/settings -> settings.html.

Non-negotiable style rules

Use palette and typography strictly; avoid additional colors.

Keep high contrast and large touch targets for station screens.

Clinical event data must be visually separated and labeled.

Tables must have sticky headers and consistent column widths.

Claude checklist

Keep admin-only navigation; no provider login flows.

Implement wizard modal for new session.

Ensure export is one-click from CPRReports and Provider Detail.

Use HTMX partials for filters and pagination.

Maintain chart + table pairing on reports and analytics pages.

If you want, I can also incorporate your sample CPRReport content and map each metric to the page skeletons.