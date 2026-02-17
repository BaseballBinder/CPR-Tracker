# Admin Dashboard Design

**Date:** 2026-02-17
**Status:** Approved

## Overview

Expand the admin area from a single comparison dashboard into a full management console with its own layout template and sidebar navigation. The admin area is a separate "mode" of the same application — same server, same codebase, different UI shell.

## Architecture

**Approach:** Parallel app shell — `admin_base.html` provides a distinct layout (amber/gold accent instead of red) with its own sidebar, while sharing the same FastAPI backend and HTMX + Jinja2 patterns as the main app.

**Authentication:** Existing admin login via the landing page. Admin routes protected by admin auth middleware.

## Admin Sidebar Navigation

| Icon | Label | Route | Purpose |
|------|-------|-------|---------|
| grid | Dashboard | `/admin` | Overview cards: total services, sessions, active vs dormant, open tickets |
| building | Services | `/admin/services` | Master list of all services with key stats |
| — | Service Detail | `/admin/services/{slug}` | Drill into one service |
| ticket | Tickets | `/admin/tickets` | Bug/suggestion tracker synced with GitHub Issues |
| chart | Analytics | `/admin/analytics` | Cross-service trends and comparisons |
| upload | Data Tools | `/admin/data-tools` | CSV provider upload, data seeding |
| gear | Settings | `/admin/settings` | Admin credentials, global config |
| arrow-left | Back to Services | `/landing` | Return to service login |

## Feature Designs

### 1. Services Page (`/admin/services`)

**Service Registry Table:**
- Service name (clickable to drill in)
- Status indicator (active/dormant — dormant = no login in 30+ days)
- Provider count
- Session count (real + simulated)
- Last active timestamp
- App version (if trackable)

**Actions:**
- Add Service button (creates a new service, same as landing page flow)
- Disable/Enable toggle per service
- Edit service name

**Service Detail (`/admin/services/{slug}`):**
- Summary cards: providers, sessions, ROSC rate, avg JcLS score
- Recent sessions list (last 10-20)
- Provider roster snapshot
- Activity log (logins, imports, exports)

### 2. Activity Tracking Infrastructure

Each service directory gets an `activity.json` file that logs timestamped events:

```json
[
  {"type": "login", "timestamp": "2026-02-17T08:30:00", "detail": null},
  {"type": "session_import", "timestamp": "2026-02-17T09:15:00", "detail": {"session_id": "abc123", "type": "real_call"}},
  {"type": "provider_added", "timestamp": "2026-02-17T09:20:00", "detail": {"name": "John Smith"}},
  {"type": "export", "timestamp": "2026-02-17T10:00:00", "detail": {"format": "canroc_master"}}
]
```

Event types to track:
- `login` — service login
- `session_import` — real call or simulated session imported
- `provider_added` — provider added to roster
- `provider_csv_upload` — bulk provider CSV import
- `export` — CanROC export generated
- `settings_changed` — service settings modified

### 3. Tickets Page (`/admin/tickets`)

**Source of truth:** GitHub Issues. The admin dashboard is a viewer, not a separate database.

**Flow:**
1. Service user submits bug/suggestion via existing Help form
2. Submission creates a GitHub Issue (labeled `bug` or `suggestion`, tagged with service name)
3. Admin Tickets page fetches open/closed issues from GitHub API
4. Admin resolves by fixing and closing the GitHub Issue (via commit message or manually)
5. Closed tickets display the release version that resolved them

**Ticket list columns:**
- Issue number
- Type (Bug / Suggestion)
- Title
- Submitted by (service name)
- Date submitted
- Status (Open / Closed)
- Resolved in (release version)

**Offline fallback:** Submissions queue locally and sync when internet is available.

### 4. Analytics Page (`/admin/analytics`)

Evolves the current `/admin` dashboard into a dedicated analytics page.

**Overview Cards:**
- Total sessions across all services (this month / all time)
- Average ROSC rate
- Average JcLS score
- Most active service this month

**Comparison Charts:**
- Sessions per service (bar chart)
- Monthly session trends per service (line chart, overlaid)
- Average JcLS score by service (bar chart)
- ROSC rate by service (bar chart)

**Filters:**
- Date range picker
- Service multi-select
- Session type (real calls / simulated / both)

**Carries over:** Event annotations feature from current admin dashboard.

### 5. Data Tools Page (`/admin/data-tools`)

**Provider CSV Upload — Two modes:**

1. **Admin uploads for a service:** Select target service from dropdown, upload CSV
2. **Service self-upload:** CSV upload option on the service-level Providers page

**CSV format (minimum):**
```csv
Name,Certification
John Smith,ACP
Jane Doe,PCP
```

**Processing:**
- Validate headers (Name + Certification required)
- Show preview of parsed rows before committing
- Skip duplicates (matched by name)
- Report results: X added, Y skipped, Z errors

**Future expansion:**
- Bulk session export across services
- Data migration tools
- CanROC template updates for all services

## Visual Design

- Same dark theme as the main app
- Distinct accent color (amber/gold) to visually differentiate admin mode from service mode
- Consistent component patterns: cards, tables, charts (Chart.js)
- HTMX partials for all interactive elements

## Data Storage

No new database. Extends the existing JSON file approach:
- `activity.json` per service directory (new)
- GitHub Issues for tickets (external)
- Existing `config.json`, `sessions.json`, `providers.json` read by admin for aggregation
