# Admin Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expand the admin area from a single-page dashboard into a full management console with its own sidebar, service registry, activity tracking, GitHub Issues-backed ticket viewer, cross-service analytics, and CSV provider upload tooling.

**Architecture:** Parallel app shell approach — a new `admin_base.html` template provides the admin layout (amber/gold accent) with its own sidebar navigation, while all admin pages share the same FastAPI backend and HTMX + Jinja2 patterns. Admin routes move to a dedicated `app/routers/admin.py` router. Activity tracking uses `activity.json` files per service directory. Tickets are backed by GitHub Issues (read-only viewer).

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, Chart.js, Tailwind CSS (vendored), JSON file storage, GitHub API (for tickets)

---

## Task 1: Admin Router & Auth Middleware Update

Extract admin routes into a dedicated router and update the auth middleware to allow all `/admin/*` paths.

**Files:**
- Create: `app/routers/admin.py`
- Modify: `app/main.py:89-92`
- Modify: `app/middleware/auth.py:13-23`
- Modify: `app/routers/api.py` (remove admin endpoints that move)
- Modify: `app/routers/pages.py` (remove admin page route)

**Step 1: Create `app/routers/admin.py`**

```python
"""
Admin area routes — pages and API endpoints for the admin management console.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.services.admin_service import (
    is_admin_authenticated, set_admin_authenticated,
    check_admin_password, ensure_admin_credentials,
    get_all_services_data, load_annotations, add_annotation, delete_annotation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")


# ============================================================================
# Admin Auth Guard
# ============================================================================

def _require_admin(request: Request):
    """Redirect to /admin/login if not authenticated."""
    if not is_admin_authenticated():
        raise HTTPException(status_code=401, detail="Admin authentication required")


# ============================================================================
# Auth Pages & API
# ============================================================================

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page."""
    if is_admin_authenticated():
        return RedirectResponse(url="/admin", status_code=302)
    return request.app.state.templates.TemplateResponse(
        "admin/login.html", {"request": request, "page_title": "Admin Login"}
    )


@router.post("/api/login")
async def admin_login(request: Request):
    """Authenticate as admin."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        username = data.get("username", "")
        password = data.get("password", "")
    else:
        form = await request.form()
        username = form.get("username", "")
        password = form.get("password", "")

    if check_admin_password(username, password):
        set_admin_authenticated(True)
        return {"success": True, "redirect": "/admin"}
    return {"success": False, "error": "Invalid admin credentials"}


@router.post("/api/logout")
async def admin_logout():
    """Log out admin."""
    set_admin_authenticated(False)
    return {"success": True, "redirect": "/landing"}


# ============================================================================
# Admin Pages
# ============================================================================

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard — overview page."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    services_data = get_all_services_data()
    return request.app.state.templates.TemplateResponse(
        "admin/dashboard.html",
        {"request": request, "page_title": "Admin Dashboard", "services_data": services_data}
    )
```

**Step 2: Update auth middleware to allow all `/admin` routes**

In `app/middleware/auth.py`, replace the PUBLIC_PATHS and PUBLIC_PREFIXES:

```python
PUBLIC_PATHS = {
    "/landing",
    "/__health",
}

PUBLIC_PREFIXES = (
    "/static/",
    "/api/auth/",
    "/admin",       # All admin routes handled by admin router's own auth
)
```

**Step 3: Register the admin router in `app/main.py`**

After `from app.routers import pages, partials, api`, add:
```python
from app.routers import pages, partials, api, admin
```

After `app.include_router(api.router)`, add:
```python
app.include_router(admin.router)
```

**Step 4: Move admin endpoints out of `app/routers/api.py`**

Remove these endpoints from `api.py` (they now live in admin router):
- `POST /api/admin/login` (line 1321)
- `POST /api/admin/logout` (line 1343)
- `GET /api/admin/services-data` (line 1351)
- `POST /api/admin/test-data/generate` (line 1365)
- `DELETE /api/admin/test-data/delete` (line 1378)
- `GET /api/admin/annotations` (line 1395)
- `POST /api/admin/annotations` (line 1404)
- `DELETE /api/admin/annotations/{annotation_id}` (line 1421)

Re-add them in `app/routers/admin.py` under the `/admin` prefix (so `/admin/api/services-data`, etc.).

**Step 5: Remove the admin page route from `app/routers/pages.py`**

Remove the `@router.get("/admin")` handler from `pages.py`.

**Step 6: Run the app to verify routing works**

Run: `.venv/Scripts/python.exe -c "from app.main import app; print('OK')"`
Expected: `OK` (no import errors)

**Step 7: Commit**

```bash
git add app/routers/admin.py app/main.py app/middleware/auth.py app/routers/api.py app/routers/pages.py
git commit -m "refactor: extract admin routes into dedicated router"
```

---

## Task 2: Admin Base Template & Sidebar

Create the admin layout template with amber/gold accent sidebar.

**Files:**
- Create: `templates/admin/admin_base.html`
- Create: `templates/admin/components/sidebar.html`
- Create: `templates/admin/components/topbar.html`

**Step 1: Create `templates/admin/components/sidebar.html`**

Model this on `templates/components/sidebar.html` but with amber accent (`#f59e0b` instead of `#dc2626`) and admin-specific nav items.

```html
<!-- Admin Sidebar navigation -->
<aside
    :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    class="fixed inset-y-0 left-0 z-50 w-64 bg-[#221e28] text-white transform transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:inset-auto"
>
    <!-- Logo / Brand -->
    <div class="h-16 flex items-center px-4 border-b border-[rgba(245,158,11,0.22)]">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-[#f59e0b] rounded-[6px] flex items-center justify-center">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
            </div>
            <div>
                <div class="font-semibold text-base">Admin Console</div>
                <div class="text-xs text-slate-400">CPR Tracker</div>
            </div>
        </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <!-- Dashboard -->
        <a href="/admin"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors
                  {% if request.url.path == '/admin' %}bg-[#f59e0b] text-white{% else %}text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white{% endif %}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path>
            </svg>
            Dashboard
        </a>

        <!-- Services -->
        <a href="/admin/services"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors
                  {% if request.url.path.startswith('/admin/services') %}bg-[#f59e0b] text-white{% else %}text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white{% endif %}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>
            </svg>
            Services
        </a>

        <!-- Tickets -->
        <a href="/admin/tickets"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors
                  {% if request.url.path.startswith('/admin/tickets') %}bg-[#f59e0b] text-white{% else %}text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white{% endif %}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"></path>
            </svg>
            Tickets
        </a>

        <!-- Analytics -->
        <a href="/admin/analytics"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors
                  {% if request.url.path.startswith('/admin/analytics') %}bg-[#f59e0b] text-white{% else %}text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white{% endif %}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
            Analytics
        </a>

        <!-- Data Tools -->
        <a href="/admin/data-tools"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors
                  {% if request.url.path.startswith('/admin/data-tools') %}bg-[#f59e0b] text-white{% else %}text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white{% endif %}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
            </svg>
            Data Tools
        </a>

        <!-- Divider -->
        <div class="border-t border-[rgba(255,255,255,0.10)] my-4"></div>

        <!-- Settings -->
        <a href="/admin/settings"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors
                  {% if request.url.path.startswith('/admin/settings') %}bg-[#f59e0b] text-white{% else %}text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white{% endif %}">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            </svg>
            Settings
        </a>

        <!-- Back to Services -->
        <a href="/landing"
           class="flex items-center gap-3 px-3 py-2 rounded-[6px] text-sm font-medium transition-colors text-slate-300 hover:bg-[rgba(245,200,120,0.07)] hover:text-white">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 17l-5-5m0 0l5-5m-5 5h12"></path>
            </svg>
            Back to Services
        </a>
    </nav>

    <!-- Footer -->
    <div class="p-4 border-t border-[rgba(245,158,11,0.22)] flex justify-center">
        <img src="/static/images/logos/JcLS.png" alt="JcLS" class="h-12 object-contain opacity-90">
    </div>
</aside>
```

**Step 2: Create `templates/admin/components/topbar.html`**

```html
<!-- Admin Topbar -->
<header class="h-16 bg-[#36323e] border-b border-[rgba(245,158,11,0.15)] flex items-center justify-between px-6">
    <div class="flex items-center gap-4">
        <!-- Mobile menu button -->
        <button @click="sidebarOpen = !sidebarOpen" class="lg:hidden text-slate-300 hover:text-white">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
            </svg>
        </button>
        <h1 class="text-lg font-semibold text-[#e2e8f0]">{{ page_title }}</h1>
    </div>
    <div class="flex items-center gap-3">
        <span class="text-xs text-[#64748b] bg-[#46424e] px-2 py-1 rounded">Admin Mode</span>
        <button hx-post="/admin/api/logout"
                hx-swap="none"
                hx-on::after-request="window.location.href='/landing'"
                class="px-3 py-1.5 text-sm text-slate-300 hover:text-white border border-[rgba(255,255,255,0.15)] rounded-md hover:bg-[rgba(255,255,255,0.05)] transition-colors">
            Logout
        </button>
    </div>
</header>
```

**Step 3: Create `templates/admin/admin_base.html`**

Model this on `templates/base.html` but use admin sidebar/topbar:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ page_title }} - CPR Tracker Admin</title>

    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600;700&display=swap" rel="stylesheet">

    <!-- Tailwind (vendored) -->
    <link href="/static/vendor/css/tailwind.min.css" rel="stylesheet">

    <!-- HTMX -->
    <script src="/static/vendor/js/htmx.min.js"></script>

    <!-- Alpine.js -->
    <script src="/static/vendor/js/alpine.min.js" defer></script>

    <!-- Chart.js -->
    <script src="/static/vendor/js/chart.min.js"></script>

    <style>
        body { font-family: 'Source Sans 3', sans-serif; background-color: #2c2834; }
    </style>

    {% block head %}{% endblock %}
</head>
<body class="min-h-screen text-[#e2e8f0]" x-data="{ sidebarOpen: false }">
    <div class="flex min-h-screen">
        <!-- Admin Sidebar -->
        {% include "admin/components/sidebar.html" %}

        <!-- Main Content Area -->
        <div class="flex-1 flex flex-col min-h-screen lg:ml-0">
            <!-- Admin Topbar -->
            {% include "admin/components/topbar.html" %}

            <!-- Page Content -->
            <main class="flex-1 p-6 overflow-auto">
                {% block content %}{% endblock %}
            </main>
        </div>
    </div>

    <!-- Modal container (for HTMX modals) -->
    <div id="modal-container"></div>

    {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 4: Verify template renders**

Run: `.venv/Scripts/python.exe -c "from app.main import app; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add templates/admin/
git commit -m "feat: add admin base template with amber sidebar"
```

---

## Task 3: Admin Login Page

Create a standalone login page that replaces the inline login form.

**Files:**
- Create: `templates/admin/login.html`

**Step 1: Create `templates/admin/login.html`**

Standalone page (no admin_base — user isn't authenticated yet):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - CPR Tracker</title>
    <link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="/static/vendor/css/tailwind.min.css" rel="stylesheet">
    <script src="/static/vendor/js/alpine.min.js" defer></script>
    <style>body { font-family: 'Source Sans 3', sans-serif; background-color: #2c2834; }</style>
</head>
<body class="min-h-screen flex items-center justify-center text-[#e2e8f0]">
    <div class="w-full max-w-md" x-data="{ username: '', password: '', error: '', loading: false }">
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-lg p-8 shadow-xl">
            <!-- Header -->
            <div class="text-center mb-8">
                <div class="w-16 h-16 bg-[#f59e0b] rounded-xl flex items-center justify-center mx-auto mb-4">
                    <svg class="w-9 h-9 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                    </svg>
                </div>
                <h1 class="text-2xl font-bold">Admin Console</h1>
                <p class="text-[#94a3b8] text-sm mt-1">CPR Performance Tracker</p>
            </div>

            <!-- Login Form -->
            <form @submit.prevent="
                loading = true; error = '';
                fetch('/admin/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username, password})
                })
                .then(r => r.json())
                .then(d => {
                    if (d.success) { window.location.href = d.redirect; }
                    else { error = d.error || 'Login failed'; loading = false; }
                })
                .catch(() => { error = 'Connection error'; loading = false; });
            ">
                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-medium text-[#94a3b8] mb-1">Username</label>
                        <input type="text" x-model="username" required autofocus
                               class="w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#e2e8f0] focus:border-[#f59e0b] focus:outline-none">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-[#94a3b8] mb-1">Password</label>
                        <input type="password" x-model="password" required
                               class="w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#e2e8f0] focus:border-[#f59e0b] focus:outline-none">
                    </div>
                </div>

                <!-- Error message -->
                <div x-show="error" x-text="error" class="mt-3 text-sm text-red-400"></div>

                <!-- Submit -->
                <button type="submit" :disabled="loading"
                        class="w-full mt-6 px-4 py-2.5 bg-[#f59e0b] text-white font-medium rounded-lg hover:bg-[#d97706] disabled:opacity-50 transition-colors">
                    <span x-show="!loading">Sign In</span>
                    <span x-show="loading">Signing in...</span>
                </button>
            </form>

            <!-- Back link -->
            <div class="mt-6 text-center">
                <a href="/landing" class="text-sm text-[#94a3b8] hover:text-[#f59e0b] transition-colors">
                    &larr; Back to Services
                </a>
            </div>
        </div>
    </div>
</body>
</html>
```

**Step 2: Verify login flow works**

Start dev server: `.venv/Scripts/activate && uvicorn app.main:app --reload`
Navigate to `http://127.0.0.1:8000/admin` — should redirect to `/admin/login`
Login with Admin / Local302! — should redirect to `/admin`

**Step 3: Update landing page admin button**

In `templates/pages/landing.html`, update the admin button href from opening the current admin page to `/admin` (this should already work since it links to `/admin`).

**Step 4: Commit**

```bash
git add templates/admin/login.html
git commit -m "feat: add standalone admin login page"
```

---

## Task 4: Admin Dashboard Overview Page

Create the admin dashboard home page with overview cards.

**Files:**
- Create: `templates/admin/dashboard.html`
- Modify: `app/routers/admin.py` (already has route from Task 1)

**Step 1: Create `templates/admin/dashboard.html`**

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="space-y-6">
    <!-- Overview Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Total Services -->
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Total Services</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">{{ services_data | length }}</div>
        </div>

        <!-- Total Sessions -->
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Total Sessions</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">
                {{ services_data | map(attribute='total_sessions') | sum }}
            </div>
        </div>

        <!-- Active Services (has activity in last 30 days) -->
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Total Providers</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">
                {{ services_data | map(attribute='active_providers') | sum }}
            </div>
        </div>

        <!-- Avg ROSC Rate -->
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Avg ROSC Rate</div>
            {% set total_rosc = services_data | map(attribute='rosc_count') | sum %}
            {% set total_no_rosc = services_data | map(attribute='no_rosc_count') | sum %}
            {% set total_calls = total_rosc + total_no_rosc %}
            <div class="text-3xl font-bold text-[#e2e8f0]">
                {{ ((total_rosc / total_calls * 100) | round(1)) if total_calls > 0 else 'N/A' }}{% if total_calls > 0 %}%{% endif %}
            </div>
        </div>
    </div>

    <!-- Quick Service List -->
    <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
        <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-[#e2e8f0]">Services</h2>
            <a href="/admin/services" class="text-sm text-[#f59e0b] hover:text-[#d97706]">View All &rarr;</a>
        </div>

        {% if services_data %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="text-left text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
                        <th class="pb-2 font-medium">Service</th>
                        <th class="pb-2 font-medium">Providers</th>
                        <th class="pb-2 font-medium">Sessions</th>
                        <th class="pb-2 font-medium">Real Calls</th>
                        <th class="pb-2 font-medium">ROSC Rate</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-[rgba(255,255,255,0.04)]">
                    {% for svc in services_data %}
                    <tr class="hover:bg-[rgba(255,255,255,0.02)]">
                        <td class="py-2.5">
                            <a href="/admin/services/{{ svc.slug }}" class="text-[#f59e0b] hover:text-[#d97706] font-medium">
                                {{ svc.name }}
                            </a>
                        </td>
                        <td class="py-2.5 text-[#94a3b8]">{{ svc.active_providers }}</td>
                        <td class="py-2.5 text-[#94a3b8]">{{ svc.total_sessions }}</td>
                        <td class="py-2.5 text-[#94a3b8]">{{ svc.real_calls }}</td>
                        <td class="py-2.5 text-[#94a3b8]">{{ svc.rosc_rate }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-[#64748b] text-sm">No services configured yet.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

**Step 2: Verify page renders**

Start dev server, login as admin, verify `/admin` shows overview cards and service table.

**Step 3: Commit**

```bash
git add templates/admin/dashboard.html
git commit -m "feat: add admin dashboard overview page with service summary"
```

---

## Task 5: Activity Tracking Service

Create the activity logging infrastructure that records events per service.

**Files:**
- Create: `app/services/activity_service.py`
- Create: `tests/test_activity_service.py`

**Step 1: Write the failing test**

```python
# tests/test_activity_service.py
"""Tests for the activity tracking service."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from app.services.activity_service import log_activity, get_activity_log, get_last_active


def _make_temp_service_dir():
    """Create a temp directory simulating a service dir."""
    d = tempfile.mkdtemp()
    return Path(d)


@patch("app.services.activity_service._get_service_dir")
def test_log_activity_creates_file(mock_dir):
    svc_dir = _make_temp_service_dir()
    mock_dir.return_value = svc_dir

    log_activity("test-service", "login")

    activity_file = svc_dir / "activity.json"
    assert activity_file.exists()
    data = json.loads(activity_file.read_text())
    assert len(data) == 1
    assert data[0]["type"] == "login"
    assert "timestamp" in data[0]


@patch("app.services.activity_service._get_service_dir")
def test_log_activity_appends(mock_dir):
    svc_dir = _make_temp_service_dir()
    mock_dir.return_value = svc_dir

    log_activity("test-service", "login")
    log_activity("test-service", "session_import", {"session_id": "abc"})

    data = json.loads((svc_dir / "activity.json").read_text())
    assert len(data) == 2
    assert data[1]["type"] == "session_import"
    assert data[1]["detail"]["session_id"] == "abc"


@patch("app.services.activity_service._get_service_dir")
def test_get_activity_log_returns_recent_first(mock_dir):
    svc_dir = _make_temp_service_dir()
    mock_dir.return_value = svc_dir

    log_activity("test-service", "login")
    log_activity("test-service", "export")

    log = get_activity_log("test-service", limit=10)
    assert len(log) == 2
    assert log[0]["type"] == "export"  # Most recent first


@patch("app.services.activity_service._get_service_dir")
def test_get_last_active(mock_dir):
    svc_dir = _make_temp_service_dir()
    mock_dir.return_value = svc_dir

    log_activity("test-service", "login")
    ts = get_last_active("test-service")
    assert ts is not None


@patch("app.services.activity_service._get_service_dir")
def test_get_last_active_no_activity(mock_dir):
    svc_dir = _make_temp_service_dir()
    mock_dir.return_value = svc_dir

    ts = get_last_active("test-service")
    assert ts is None
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_activity_service.py -v`
Expected: FAIL (module not found)

**Step 3: Write the implementation**

```python
# app/services/activity_service.py
"""
Activity tracking for per-service usage logging.
Each service gets an activity.json file in its data directory.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.desktop_config import get_service_dir as _get_service_dir

logger = logging.getLogger(__name__)

# Maximum entries to keep per service (prevent unbounded growth)
MAX_ACTIVITY_ENTRIES = 5000


def _get_activity_file(service_slug: str) -> Path:
    """Get the path to a service's activity.json."""
    return _get_service_dir(service_slug) / "activity.json"


def _load_activity(service_slug: str) -> List[Dict]:
    """Load the activity log for a service."""
    f = _get_activity_file(service_slug)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_activity(service_slug: str, entries: List[Dict]) -> None:
    """Save the activity log, truncating if too large."""
    if len(entries) > MAX_ACTIVITY_ENTRIES:
        entries = entries[-MAX_ACTIVITY_ENTRIES:]
    f = _get_activity_file(service_slug)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def log_activity(
    service_slug: str,
    event_type: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an activity event for a service.

    Event types: login, session_import, provider_added,
    provider_csv_upload, export, settings_changed
    """
    entries = _load_activity(service_slug)
    entries.append({
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    })
    _save_activity(service_slug, entries)


def get_activity_log(
    service_slug: str,
    limit: int = 50,
    event_type: Optional[str] = None,
) -> List[Dict]:
    """Get recent activity for a service, newest first."""
    entries = _load_activity(service_slug)
    if event_type:
        entries = [e for e in entries if e.get("type") == event_type]
    return list(reversed(entries[-limit:]))


def get_last_active(service_slug: str) -> Optional[str]:
    """Get the timestamp of the most recent activity for a service."""
    entries = _load_activity(service_slug)
    if not entries:
        return None
    return entries[-1].get("timestamp")
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_activity_service.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add app/services/activity_service.py tests/test_activity_service.py
git commit -m "feat: add activity tracking service with tests"
```

---

## Task 6: Wire Activity Logging Into Existing Flows

Add `log_activity()` calls to existing code paths so data starts accumulating.

**Files:**
- Modify: `app/routers/api.py` (login, provider creation, session import, export)
- Modify: `app/service_context.py` (service login)

**Step 1: Log activity on service login**

In `app/service_context.py`, after `set_active_service()` sets the slug, add:

```python
# At the end of set_active_service(), after logger.info():
from app.services.activity_service import log_activity
log_activity(slug, "login")
```

**Step 2: Log activity on session import**

In `app/routers/api.py`, in the session creation endpoints (`POST /sessions/real-call` and `POST /sessions/simulated`), after a successful session creation, add:

```python
from app.services.activity_service import log_activity
from app.service_context import get_active_service
slug = get_active_service()
if slug:
    log_activity(slug, "session_import", {"session_id": session.id, "type": session.session_type.value})
```

**Step 3: Log activity on provider creation**

In `app/routers/api.py`, in `create_provider()`, after successful provider creation, add:

```python
from app.services.activity_service import log_activity
from app.service_context import get_active_service
slug = get_active_service()
if slug:
    log_activity(slug, "provider_added", {"name": name})
```

**Step 4: Log activity on export**

In `app/routers/api.py`, in the CanROC export endpoints, after successful export, add:

```python
from app.services.activity_service import log_activity
from app.service_context import get_active_service
slug = get_active_service()
if slug:
    log_activity(slug, "export", {"format": "canroc_master"})  # or "canroc_pco"
```

**Step 5: Verify app still loads**

Run: `.venv/Scripts/python.exe -c "from app.main import app; print('OK')"`
Expected: `OK`

**Step 6: Commit**

```bash
git add app/routers/api.py app/service_context.py
git commit -m "feat: wire activity logging into login, import, provider, and export flows"
```

---

## Task 7: Services List Page

Create the `/admin/services` page showing all registered services.

**Files:**
- Create: `templates/admin/services.html`
- Modify: `app/routers/admin.py` (add route)
- Modify: `app/services/admin_service.py` (add last_active to service data)

**Step 1: Add `last_active` to service data in `admin_service.py`**

In `get_all_services_data()`, after building the result dict for each service, add:

```python
from app.services.activity_service import get_last_active
# ... inside the loop, add to the result dict:
"last_active": get_last_active(slug),
```

**Step 2: Add the services page route to `app/routers/admin.py`**

```python
@router.get("/services", response_class=HTMLResponse)
async def admin_services(request: Request):
    """Service registry — list all services."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    services_data = get_all_services_data()
    return request.app.state.templates.TemplateResponse(
        "admin/services.html",
        {"request": request, "page_title": "Services", "services_data": services_data}
    )
```

**Step 3: Create `templates/admin/services.html`**

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <div>
            <h2 class="text-xl font-bold text-[#e2e8f0]">Service Registry</h2>
            <p class="text-sm text-[#64748b]">{{ services_data | length }} service{{ 's' if services_data | length != 1 }} registered</p>
        </div>
    </div>

    <!-- Services Table -->
    <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md overflow-hidden">
        {% if services_data %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="text-left text-[#64748b] border-b border-[rgba(255,255,255,0.08)]">
                        <th class="px-5 py-3 font-medium">Service</th>
                        <th class="px-5 py-3 font-medium">Status</th>
                        <th class="px-5 py-3 font-medium">Providers</th>
                        <th class="px-5 py-3 font-medium">Sessions</th>
                        <th class="px-5 py-3 font-medium">Real Calls</th>
                        <th class="px-5 py-3 font-medium">ROSC Rate</th>
                        <th class="px-5 py-3 font-medium">Last Active</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-[rgba(255,255,255,0.04)]">
                    {% for svc in services_data %}
                    <tr class="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                        <td class="px-5 py-3">
                            <a href="/admin/services/{{ svc.slug }}" class="text-[#f59e0b] hover:text-[#d97706] font-medium">
                                {{ svc.name }}
                            </a>
                        </td>
                        <td class="px-5 py-3">
                            {% if svc.last_active %}
                            <span class="inline-flex items-center gap-1.5 text-xs">
                                <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                                Active
                            </span>
                            {% else %}
                            <span class="inline-flex items-center gap-1.5 text-xs text-[#64748b]">
                                <span class="w-2 h-2 rounded-full bg-[#64748b]"></span>
                                New
                            </span>
                            {% endif %}
                        </td>
                        <td class="px-5 py-3 text-[#94a3b8]">{{ svc.active_providers }}</td>
                        <td class="px-5 py-3 text-[#94a3b8]">{{ svc.total_sessions }}</td>
                        <td class="px-5 py-3 text-[#94a3b8]">{{ svc.real_calls }}</td>
                        <td class="px-5 py-3 text-[#94a3b8]">{{ svc.rosc_rate }}%</td>
                        <td class="px-5 py-3 text-[#64748b] text-xs">
                            {% if svc.last_active %}
                            {{ svc.last_active[:16] | replace('T', ' ') }}
                            {% else %}
                            —
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="px-5 py-8 text-center text-[#64748b]">
            <p>No services configured yet.</p>
            <p class="text-sm mt-1">Services are created from the landing page.</p>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

**Step 4: Verify page renders**

Navigate to `/admin/services` after admin login.

**Step 5: Commit**

```bash
git add templates/admin/services.html app/routers/admin.py app/services/admin_service.py
git commit -m "feat: add admin services list page with status and last active"
```

---

## Task 8: Service Detail Page

Create the `/admin/services/{slug}` drill-in page.

**Files:**
- Create: `templates/admin/service_detail.html`
- Modify: `app/routers/admin.py` (add route)

**Step 1: Add the route to `app/routers/admin.py`**

```python
@router.get("/services/{slug}", response_class=HTMLResponse)
async def admin_service_detail(request: Request, slug: str):
    """Service detail — drill into a single service."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    services_data = get_all_services_data()
    service = next((s for s in services_data if s["slug"] == slug), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    from app.services.activity_service import get_activity_log
    activity = get_activity_log(slug, limit=20)

    return request.app.state.templates.TemplateResponse(
        "admin/service_detail.html",
        {"request": request, "page_title": service["name"], "service": service, "activity": activity}
    )
```

**Step 2: Create `templates/admin/service_detail.html`**

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="space-y-6">
    <!-- Breadcrumb -->
    <div class="flex items-center gap-2 text-sm text-[#64748b]">
        <a href="/admin/services" class="hover:text-[#f59e0b]">Services</a>
        <span>/</span>
        <span class="text-[#e2e8f0]">{{ service.name }}</span>
    </div>

    <!-- Summary Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Providers</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">{{ service.active_providers }}</div>
        </div>
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Total Sessions</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">{{ service.total_sessions }}</div>
            <div class="text-xs text-[#64748b] mt-1">{{ service.real_calls }} real / {{ service.simulated }} sim</div>
        </div>
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">ROSC Rate</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">{{ service.rosc_rate }}%</div>
        </div>
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <div class="text-sm text-[#94a3b8] mb-1">Avg CCF</div>
            <div class="text-3xl font-bold text-[#e2e8f0]">{{ service.avg_ccf }}%</div>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Provider Roster Snapshot -->
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <h3 class="text-base font-semibold text-[#e2e8f0] mb-3">Providers ({{ service.active_providers }})</h3>
            {% if service.providers %}
            <div class="space-y-1 max-h-64 overflow-y-auto">
                {% for p in service.providers if p.status == 'active' %}
                <div class="flex items-center justify-between py-1.5 px-2 rounded hover:bg-[rgba(255,255,255,0.02)]">
                    <span class="text-sm text-[#e2e8f0]">{{ p.name }}</span>
                    <span class="text-xs text-[#64748b] bg-[#46424e] px-2 py-0.5 rounded">{{ p.certification }}</span>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-sm text-[#64748b]">No providers yet.</p>
            {% endif %}
        </div>

        <!-- Recent Activity -->
        <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
            <h3 class="text-base font-semibold text-[#e2e8f0] mb-3">Recent Activity</h3>
            {% if activity %}
            <div class="space-y-2 max-h-64 overflow-y-auto">
                {% for event in activity %}
                <div class="flex items-start gap-3 py-1.5">
                    <div class="w-2 h-2 rounded-full mt-1.5
                        {% if event.type == 'login' %}bg-emerald-400
                        {% elif event.type == 'session_import' %}bg-blue-400
                        {% elif event.type == 'provider_added' %}bg-purple-400
                        {% elif event.type == 'export' %}bg-amber-400
                        {% else %}bg-[#64748b]{% endif %}">
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="text-sm text-[#e2e8f0]">{{ event.type | replace('_', ' ') | title }}</div>
                        <div class="text-xs text-[#64748b]">{{ event.timestamp[:16] | replace('T', ' ') }}</div>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="text-sm text-[#64748b]">No activity recorded yet.</p>
            {% endif %}
        </div>
    </div>

    <!-- Recent Sessions -->
    <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5">
        <h3 class="text-base font-semibold text-[#e2e8f0] mb-3">Recent Sessions</h3>
        {% set recent = service.sessions[-20:] | reverse | list %}
        {% if recent %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="text-left text-[#64748b] border-b border-[rgba(255,255,255,0.06)]">
                        <th class="pb-2 font-medium">Date</th>
                        <th class="pb-2 font-medium">Type</th>
                        <th class="pb-2 font-medium">Status</th>
                        <th class="pb-2 font-medium">Outcome</th>
                        <th class="pb-2 font-medium">Rate</th>
                        <th class="pb-2 font-medium">Depth</th>
                        <th class="pb-2 font-medium">CCF</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-[rgba(255,255,255,0.04)]">
                    {% for s in recent %}
                    <tr>
                        <td class="py-2 text-[#e2e8f0]">{{ s.date }}</td>
                        <td class="py-2 text-[#94a3b8]">{{ s.session_type | replace('_', ' ') | title }}</td>
                        <td class="py-2">
                            <span class="text-xs px-2 py-0.5 rounded
                                {% if s.status == 'complete' %}bg-emerald-900/50 text-emerald-400
                                {% elif s.status == 'importing' %}bg-amber-900/50 text-amber-400
                                {% else %}bg-red-900/50 text-red-400{% endif %}">
                                {{ s.status }}
                            </span>
                        </td>
                        <td class="py-2 text-[#94a3b8]">{{ s.outcome or '—' }}</td>
                        <td class="py-2 text-[#94a3b8]">{{ s.metrics.compression_rate if s.metrics else '—' }}</td>
                        <td class="py-2 text-[#94a3b8]">{{ s.metrics.compression_depth if s.metrics else '—' }}</td>
                        <td class="py-2 text-[#94a3b8]">{{ s.metrics.compression_fraction if s.metrics else '—' }}{% if s.metrics and s.metrics.compression_fraction %}%{% endif %}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <p class="text-sm text-[#64748b]">No sessions imported yet.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
```

**Step 3: Verify page renders**

Navigate to `/admin/services/{slug}` for an existing service.

**Step 4: Commit**

```bash
git add templates/admin/service_detail.html app/routers/admin.py
git commit -m "feat: add admin service detail page with activity log"
```

---

## Task 9: Tickets Page (GitHub Issues Viewer)

Create the ticket system backed by GitHub Issues.

**Files:**
- Create: `app/services/ticket_service.py`
- Create: `tests/test_ticket_service.py`
- Create: `templates/admin/tickets.html`
- Modify: `app/routers/admin.py` (add route)

**Step 1: Write the failing test**

```python
# tests/test_ticket_service.py
"""Tests for the ticket service (GitHub Issues integration)."""
from unittest.mock import patch, MagicMock
from app.services.ticket_service import parse_github_issues


def test_parse_github_issues_extracts_fields():
    """Test that raw GitHub API response is parsed correctly."""
    raw_issues = [
        {
            "number": 42,
            "title": "Button doesn't work on mobile",
            "body": "The submit button is unresponsive on iPhone.\n\nService: Spruce Grove Fire",
            "labels": [{"name": "bug"}],
            "state": "open",
            "created_at": "2026-02-10T14:30:00Z",
            "closed_at": None,
            "milestone": None,
        },
        {
            "number": 43,
            "title": "Add dark mode toggle",
            "body": "It would be nice to have a light mode option.\n\nService: Edmonton Fire",
            "labels": [{"name": "suggestion"}],
            "state": "closed",
            "created_at": "2026-02-08T09:00:00Z",
            "closed_at": "2026-02-15T11:00:00Z",
            "milestone": {"title": "v1.1.0"},
        },
    ]

    tickets = parse_github_issues(raw_issues)
    assert len(tickets) == 2

    assert tickets[0]["number"] == 42
    assert tickets[0]["type"] == "bug"
    assert tickets[0]["status"] == "open"
    assert tickets[0]["service"] == "Spruce Grove Fire"

    assert tickets[1]["number"] == 43
    assert tickets[1]["type"] == "suggestion"
    assert tickets[1]["status"] == "closed"
    assert tickets[1]["resolved_in"] == "v1.1.0"
    assert tickets[1]["service"] == "Edmonton Fire"
```

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ticket_service.py -v`
Expected: FAIL (module not found)

**Step 3: Write the implementation**

```python
# app/services/ticket_service.py
"""
Ticket service — fetches and parses GitHub Issues for the admin dashboard.
Source of truth is GitHub; this service is read-only.
"""
import re
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

import requests

from app.desktop_config import get_appdata_dir

logger = logging.getLogger(__name__)

# Default GitHub repo (same as update_service)
DEFAULT_REPO = "baseballbinder/CPR-Tracker"


def _get_repo() -> str:
    """Get the configured GitHub repo."""
    return DEFAULT_REPO


def fetch_github_issues(
    state: str = "all",
    labels: Optional[str] = None,
) -> List[Dict]:
    """Fetch issues from GitHub API. Returns raw issue dicts."""
    repo = _get_repo()
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": state, "per_page": 100, "sort": "created", "direction": "desc"}
    if labels:
        params["labels"] = labels

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        # Filter out pull requests (GitHub API returns PRs in issues endpoint)
        return [i for i in resp.json() if "pull_request" not in i]
    except Exception as e:
        logger.error(f"Failed to fetch GitHub issues: {e}")
        return []


def parse_github_issues(raw_issues: List[Dict]) -> List[Dict]:
    """Parse raw GitHub API issues into ticket dicts for display."""
    tickets = []
    for issue in raw_issues:
        labels = [l["name"] for l in issue.get("labels", [])]

        # Determine type from labels
        ticket_type = "bug" if "bug" in labels else "suggestion" if "suggestion" in labels else "other"

        # Extract service name from body (pattern: "Service: <name>")
        body = issue.get("body") or ""
        service_match = re.search(r"Service:\s*(.+?)(?:\n|$)", body)
        service_name = service_match.group(1).strip() if service_match else "Unknown"

        # Resolved-in version from milestone
        milestone = issue.get("milestone")
        resolved_in = milestone["title"] if milestone else None

        tickets.append({
            "number": issue["number"],
            "title": issue["title"],
            "type": ticket_type,
            "service": service_name,
            "status": issue["state"],
            "created_at": issue["created_at"],
            "closed_at": issue.get("closed_at"),
            "resolved_in": resolved_in,
            "labels": labels,
            "url": issue.get("html_url", ""),
        })

    return tickets


def get_tickets(state: str = "all") -> List[Dict]:
    """Fetch and parse tickets. Main entry point."""
    raw = fetch_github_issues(state=state)
    return parse_github_issues(raw)
```

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_ticket_service.py -v`
Expected: PASS

**Step 5: Add the route to `app/routers/admin.py`**

```python
@router.get("/tickets", response_class=HTMLResponse)
async def admin_tickets(request: Request):
    """Ticket tracker — bugs and suggestions from GitHub Issues."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    from app.services.ticket_service import get_tickets
    tickets = get_tickets()

    return request.app.state.templates.TemplateResponse(
        "admin/tickets.html",
        {"request": request, "page_title": "Tickets", "tickets": tickets}
    )
```

**Step 6: Create `templates/admin/tickets.html`**

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="space-y-6">
    <div class="flex items-center justify-between">
        <div>
            <h2 class="text-xl font-bold text-[#e2e8f0]">Tickets</h2>
            <p class="text-sm text-[#64748b]">Bug reports and suggestions from GitHub Issues</p>
        </div>
        <div class="flex gap-2 text-sm" x-data="{ filter: 'all' }">
            <button @click="filter='all'; document.querySelectorAll('[data-ticket]').forEach(el => el.style.display='')"
                    :class="filter==='all' ? 'bg-[#f59e0b] text-white' : 'bg-[#46424e] text-[#94a3b8]'"
                    class="px-3 py-1.5 rounded-md transition-colors">All</button>
            <button @click="filter='open'; document.querySelectorAll('[data-ticket]').forEach(el => el.style.display = el.dataset.status==='open' ? '' : 'none')"
                    :class="filter==='open' ? 'bg-[#f59e0b] text-white' : 'bg-[#46424e] text-[#94a3b8]'"
                    class="px-3 py-1.5 rounded-md transition-colors">Open</button>
            <button @click="filter='closed'; document.querySelectorAll('[data-ticket]').forEach(el => el.style.display = el.dataset.status==='closed' ? '' : 'none')"
                    :class="filter==='closed' ? 'bg-[#f59e0b] text-white' : 'bg-[#46424e] text-[#94a3b8]'"
                    class="px-3 py-1.5 rounded-md transition-colors">Closed</button>
        </div>
    </div>

    <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md overflow-hidden">
        {% if tickets %}
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="text-left text-[#64748b] border-b border-[rgba(255,255,255,0.08)]">
                        <th class="px-5 py-3 font-medium">#</th>
                        <th class="px-5 py-3 font-medium">Type</th>
                        <th class="px-5 py-3 font-medium">Title</th>
                        <th class="px-5 py-3 font-medium">Service</th>
                        <th class="px-5 py-3 font-medium">Date</th>
                        <th class="px-5 py-3 font-medium">Status</th>
                        <th class="px-5 py-3 font-medium">Resolved In</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-[rgba(255,255,255,0.04)]">
                    {% for t in tickets %}
                    <tr data-ticket data-status="{{ t.status }}" class="hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                        <td class="px-5 py-3 text-[#64748b]">{{ t.number }}</td>
                        <td class="px-5 py-3">
                            <span class="text-xs px-2 py-0.5 rounded
                                {% if t.type == 'bug' %}bg-red-900/50 text-red-400
                                {% elif t.type == 'suggestion' %}bg-blue-900/50 text-blue-400
                                {% else %}bg-[#46424e] text-[#94a3b8]{% endif %}">
                                {{ t.type | title }}
                            </span>
                        </td>
                        <td class="px-5 py-3">
                            {% if t.url %}
                            <a href="{{ t.url }}" target="_blank" class="text-[#e2e8f0] hover:text-[#f59e0b]">
                                {{ t.title }}
                            </a>
                            {% else %}
                            <span class="text-[#e2e8f0]">{{ t.title }}</span>
                            {% endif %}
                        </td>
                        <td class="px-5 py-3 text-[#94a3b8]">{{ t.service }}</td>
                        <td class="px-5 py-3 text-[#64748b] text-xs">{{ t.created_at[:10] }}</td>
                        <td class="px-5 py-3">
                            <span class="inline-flex items-center gap-1.5 text-xs">
                                <span class="w-2 h-2 rounded-full {% if t.status == 'open' %}bg-emerald-400{% else %}bg-[#64748b]{% endif %}"></span>
                                {{ t.status | title }}
                            </span>
                        </td>
                        <td class="px-5 py-3 text-[#64748b] text-xs">{{ t.resolved_in or '—' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="px-5 py-8 text-center text-[#64748b]">
            <p>No tickets found.</p>
            <p class="text-sm mt-1">Issues will appear here when submitted via the Help page or created on GitHub.</p>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

**Step 7: Commit**

```bash
git add app/services/ticket_service.py tests/test_ticket_service.py templates/admin/tickets.html app/routers/admin.py
git commit -m "feat: add tickets page backed by GitHub Issues"
```

---

## Task 10: Analytics Page

Move the current admin dashboard charts into a dedicated analytics page.

**Files:**
- Create: `templates/admin/analytics.html`
- Modify: `app/routers/admin.py` (add route)

**Step 1: Add the route to `app/routers/admin.py`**

```python
@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(request: Request):
    """Cross-service analytics and comparison charts."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    services_data = get_all_services_data()
    annotations = load_annotations()

    return request.app.state.templates.TemplateResponse(
        "admin/analytics.html",
        {
            "request": request,
            "page_title": "Analytics",
            "services_data": services_data,
            "annotations": annotations,
        }
    )
```

**Step 2: Create `templates/admin/analytics.html`**

This should migrate the chart logic from the current `templates/pages/admin_dashboard.html` (the authenticated section with Chart.js charts) into the new template extending `admin_base.html`. Key sections:

- Overview cards (total sessions, avg ROSC, avg JcLS, most active service)
- Sessions per service bar chart
- Monthly trends line chart (overlaid per service)
- Avg JcLS / ROSC rate comparison bar charts
- Annotations management
- Date range and service multi-select filters

The chart JavaScript from the current admin_dashboard.html should be moved here with the Alpine.js `adminDashboard()` component adapted to work within the new template structure.

**Important:** Reference the current `templates/pages/admin_dashboard.html` lines 200-800+ for the exact Chart.js configuration, Alpine.js data component, and annotation management code. Copy and adapt rather than rewriting.

**Step 3: Move annotation API endpoints to admin router**

Ensure these endpoints exist in `app/routers/admin.py` (from Task 1 migration):
- `GET /admin/api/annotations`
- `POST /admin/api/annotations`
- `DELETE /admin/api/annotations/{annotation_id}`

**Step 4: Verify charts render**

Navigate to `/admin/analytics`, verify all charts appear with data.

**Step 5: Commit**

```bash
git add templates/admin/analytics.html app/routers/admin.py
git commit -m "feat: add admin analytics page with cross-service charts"
```

---

## Task 11: Data Tools Page (CSV Provider Upload)

Create the CSV upload page for seeding provider rosters.

**Files:**
- Create: `app/services/csv_import_service.py`
- Create: `tests/test_csv_import.py`
- Create: `templates/admin/data_tools.html`
- Modify: `app/routers/admin.py` (add routes)

**Step 1: Write the failing test**

```python
# tests/test_csv_import.py
"""Tests for CSV provider import."""
from app.services.csv_import_service import parse_provider_csv, validate_provider_csv


def test_parse_valid_csv():
    csv_text = "Name,Certification\nJohn Smith,ACP\nJane Doe,PCP\n"
    rows = parse_provider_csv(csv_text)
    assert len(rows) == 2
    assert rows[0] == {"name": "John Smith", "certification": "ACP"}
    assert rows[1] == {"name": "Jane Doe", "certification": "PCP"}


def test_parse_csv_case_insensitive_headers():
    csv_text = "name,CERTIFICATION\nAlice,ACP\n"
    rows = parse_provider_csv(csv_text)
    assert len(rows) == 1
    assert rows[0]["name"] == "Alice"


def test_parse_csv_strips_whitespace():
    csv_text = "Name , Certification \n  Bob  ,  PCP  \n"
    rows = parse_provider_csv(csv_text)
    assert rows[0] == {"name": "Bob", "certification": "PCP"}


def test_validate_missing_headers():
    csv_text = "FirstName,LastName\nJohn,Smith\n"
    errors = validate_provider_csv(csv_text)
    assert len(errors) > 0
    assert "Name" in errors[0]


def test_validate_empty_csv():
    csv_text = ""
    errors = validate_provider_csv(csv_text)
    assert len(errors) > 0


def test_parse_csv_skips_empty_rows():
    csv_text = "Name,Certification\nJohn,ACP\n\n\nJane,PCP\n"
    rows = parse_provider_csv(csv_text)
    assert len(rows) == 2
```

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_csv_import.py -v`
Expected: FAIL

**Step 3: Write the implementation**

```python
# app/services/csv_import_service.py
"""
CSV provider import service.
Parses CSV files with provider roster data and imports into a service.
"""
import csv
import io
import json
import logging
from typing import List, Dict, Tuple
from pathlib import Path

from app.desktop_config import get_service_dir

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = {"name", "certification"}


def validate_provider_csv(csv_text: str) -> List[str]:
    """Validate CSV text has required headers. Returns list of errors."""
    errors = []
    if not csv_text.strip():
        errors.append("CSV file is empty")
        return errors

    reader = csv.reader(io.StringIO(csv_text.strip()))
    try:
        headers = [h.strip().lower() for h in next(reader)]
    except StopIteration:
        errors.append("CSV file has no header row")
        return errors

    missing = REQUIRED_HEADERS - set(headers)
    if missing:
        errors.append(f"Missing required columns: {', '.join(h.title() for h in sorted(missing))}")

    return errors


def parse_provider_csv(csv_text: str) -> List[Dict[str, str]]:
    """Parse CSV text into list of provider dicts."""
    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    # Normalize headers to lowercase
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames] if reader.fieldnames else []

    rows = []
    for row in reader:
        name = row.get("name", "").strip()
        cert = row.get("certification", "").strip()
        if name:  # Skip empty rows
            rows.append({"name": name, "certification": cert})
    return rows


def import_providers_to_service(
    service_slug: str,
    providers: List[Dict[str, str]],
) -> Dict[str, int]:
    """Import parsed providers into a service's providers.json.

    Returns counts: {"added": N, "skipped": N, "errors": N}
    """
    providers_file = get_service_dir(service_slug) / "data" / "providers.json"

    # Load existing providers
    existing = []
    if providers_file.exists():
        try:
            raw = json.loads(providers_file.read_text(encoding="utf-8"))
            existing = raw.get("providers", [])
        except (json.JSONDecodeError, IOError):
            pass

    existing_names = {p.get("name", "").lower() for p in existing}

    added = 0
    skipped = 0
    for p in providers:
        if p["name"].lower() in existing_names:
            skipped += 1
            continue

        import uuid
        names = p["name"].split(maxsplit=1)
        first_name = names[0] if names else ""
        last_name = names[1] if len(names) > 1 else ""

        existing.append({
            "id": str(uuid.uuid4())[:8],
            "name": p["name"],
            "first_name": first_name,
            "last_name": last_name,
            "certification": p["certification"],
            "role": "Paramedic",
            "status": "active",
        })
        existing_names.add(p["name"].lower())
        added += 1

    # Save
    from datetime import datetime
    providers_file.write_text(
        json.dumps({"providers": existing, "last_updated": datetime.now().isoformat()}, indent=2),
        encoding="utf-8",
    )

    return {"added": added, "skipped": skipped, "errors": 0}
```

**Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_csv_import.py -v`
Expected: All PASS

**Step 5: Add routes to `app/routers/admin.py`**

```python
@router.get("/data-tools", response_class=HTMLResponse)
async def admin_data_tools(request: Request):
    """Data tools — CSV upload and seeding."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    from app.service_context import list_services
    services = list_services()

    return request.app.state.templates.TemplateResponse(
        "admin/data_tools.html",
        {"request": request, "page_title": "Data Tools", "services": services}
    )


@router.post("/api/csv-upload")
async def admin_csv_upload(
    request: Request,
    service_slug: str = Form(...),
    csv_file: UploadFile = File(...),
):
    """Upload CSV to seed providers for a service."""
    if not is_admin_authenticated():
        raise HTTPException(status_code=401)

    from app.services.csv_import_service import validate_provider_csv, parse_provider_csv, import_providers_to_service
    from app.services.activity_service import log_activity

    content = (await csv_file.read()).decode("utf-8")

    errors = validate_provider_csv(content)
    if errors:
        return JSONResponse({"success": False, "errors": errors}, status_code=400)

    providers = parse_provider_csv(content)
    if not providers:
        return JSONResponse({"success": False, "errors": ["No valid provider rows found"]}, status_code=400)

    result = import_providers_to_service(service_slug, providers)
    log_activity(service_slug, "provider_csv_upload", {
        "added": result["added"],
        "skipped": result["skipped"],
    })

    return {"success": True, "result": result}
```

**Step 6: Create `templates/admin/data_tools.html`**

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="space-y-6">
    <div>
        <h2 class="text-xl font-bold text-[#e2e8f0]">Data Tools</h2>
        <p class="text-sm text-[#64748b]">CSV upload and data seeding</p>
    </div>

    <!-- CSV Provider Upload -->
    <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5"
         x-data="{
            service: '',
            file: null,
            fileName: '',
            loading: false,
            result: null,
            errors: [],
            async upload() {
                if (!this.service || !this.file) return;
                this.loading = true;
                this.result = null;
                this.errors = [];
                const formData = new FormData();
                formData.append('service_slug', this.service);
                formData.append('csv_file', this.file);
                try {
                    const resp = await fetch('/admin/api/csv-upload', { method: 'POST', body: formData });
                    const data = await resp.json();
                    if (data.success) { this.result = data.result; }
                    else { this.errors = data.errors || ['Upload failed']; }
                } catch (e) { this.errors = ['Connection error']; }
                this.loading = false;
            }
         }">
        <h3 class="text-base font-semibold text-[#e2e8f0] mb-4">Upload Provider CSV</h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <!-- Service selector -->
            <div>
                <label class="block text-sm font-medium text-[#94a3b8] mb-1">Target Service</label>
                <select x-model="service"
                        class="w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#e2e8f0] focus:border-[#f59e0b] focus:outline-none">
                    <option value="">Select a service...</option>
                    {% for svc in services %}
                    <option value="{{ svc.slug }}">{{ svc.name }}</option>
                    {% endfor %}
                </select>
            </div>

            <!-- File input -->
            <div>
                <label class="block text-sm font-medium text-[#94a3b8] mb-1">CSV File</label>
                <label class="flex items-center gap-2 w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#94a3b8] cursor-pointer hover:border-[#f59e0b]">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"></path>
                    </svg>
                    <span x-text="fileName || 'Choose file...'"></span>
                    <input type="file" accept=".csv" class="hidden"
                           @change="file = $event.target.files[0]; fileName = file ? file.name : ''">
                </label>
            </div>
        </div>

        <!-- CSV Format hint -->
        <div class="mb-4 p-3 bg-[#46424e] rounded-md">
            <p class="text-xs text-[#94a3b8]">Required CSV format:</p>
            <code class="text-xs text-[#e2e8f0] block mt-1">Name,Certification<br>John Smith,ACP<br>Jane Doe,PCP</code>
        </div>

        <!-- Upload button -->
        <button @click="upload()" :disabled="loading || !service || !file"
                class="px-4 py-2 bg-[#f59e0b] text-white font-medium rounded-md hover:bg-[#d97706] disabled:opacity-50 transition-colors">
            <span x-show="!loading">Upload & Import</span>
            <span x-show="loading">Importing...</span>
        </button>

        <!-- Results -->
        <div x-show="result" class="mt-4 p-3 bg-emerald-900/30 border border-emerald-800 rounded-md">
            <p class="text-sm text-emerald-400">
                Import complete: <strong x-text="result?.added"></strong> added,
                <strong x-text="result?.skipped"></strong> skipped (duplicates)
            </p>
        </div>

        <!-- Errors -->
        <div x-show="errors.length > 0" class="mt-4 p-3 bg-red-900/30 border border-red-800 rounded-md">
            <template x-for="err in errors">
                <p class="text-sm text-red-400" x-text="err"></p>
            </template>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 7: Commit**

```bash
git add app/services/csv_import_service.py tests/test_csv_import.py templates/admin/data_tools.html app/routers/admin.py
git commit -m "feat: add data tools page with CSV provider upload"
```

---

## Task 12: Admin Settings Page

Create a basic admin settings page.

**Files:**
- Create: `templates/admin/settings.html`
- Modify: `app/routers/admin.py` (add route)

**Step 1: Add the route to `app/routers/admin.py`**

```python
@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Admin settings."""
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    return request.app.state.templates.TemplateResponse(
        "admin/settings.html",
        {"request": request, "page_title": "Settings"}
    )
```

**Step 2: Create `templates/admin/settings.html`**

```html
{% extends "admin/admin_base.html" %}

{% block content %}
<div class="space-y-6">
    <div>
        <h2 class="text-xl font-bold text-[#e2e8f0]">Admin Settings</h2>
        <p class="text-sm text-[#64748b]">Global configuration for the admin console</p>
    </div>

    <!-- Change Admin Password -->
    <div class="bg-[#3e3a46] border border-[rgba(255,255,255,0.10)] rounded-md p-5"
         x-data="{
            currentPassword: '',
            newPassword: '',
            confirmPassword: '',
            loading: false,
            message: '',
            messageType: '',
            async changePassword() {
                if (this.newPassword !== this.confirmPassword) {
                    this.message = 'Passwords do not match';
                    this.messageType = 'error';
                    return;
                }
                this.loading = true;
                try {
                    const resp = await fetch('/admin/api/change-password', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            current_password: this.currentPassword,
                            new_password: this.newPassword
                        })
                    });
                    const data = await resp.json();
                    this.message = data.success ? 'Password changed successfully' : (data.error || 'Failed');
                    this.messageType = data.success ? 'success' : 'error';
                    if (data.success) { this.currentPassword = ''; this.newPassword = ''; this.confirmPassword = ''; }
                } catch (e) { this.message = 'Connection error'; this.messageType = 'error'; }
                this.loading = false;
            }
         }">
        <h3 class="text-base font-semibold text-[#e2e8f0] mb-4">Change Admin Password</h3>

        <div class="space-y-3 max-w-md">
            <div>
                <label class="block text-sm text-[#94a3b8] mb-1">Current Password</label>
                <input type="password" x-model="currentPassword"
                       class="w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#e2e8f0] focus:border-[#f59e0b] focus:outline-none">
            </div>
            <div>
                <label class="block text-sm text-[#94a3b8] mb-1">New Password</label>
                <input type="password" x-model="newPassword"
                       class="w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#e2e8f0] focus:border-[#f59e0b] focus:outline-none">
            </div>
            <div>
                <label class="block text-sm text-[#94a3b8] mb-1">Confirm New Password</label>
                <input type="password" x-model="confirmPassword"
                       class="w-full px-4 py-2.5 bg-[#46424e] border border-[rgba(255,255,255,0.15)] rounded-lg text-[#e2e8f0] focus:border-[#f59e0b] focus:outline-none">
            </div>
            <button @click="changePassword()" :disabled="loading"
                    class="px-4 py-2 bg-[#f59e0b] text-white font-medium rounded-md hover:bg-[#d97706] disabled:opacity-50 transition-colors">
                <span x-show="!loading">Update Password</span>
                <span x-show="loading">Updating...</span>
            </button>
            <div x-show="message" :class="messageType==='success' ? 'text-emerald-400' : 'text-red-400'" class="text-sm mt-2" x-text="message"></div>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 3: Add change-password API endpoint to `app/routers/admin.py`**

```python
@router.post("/api/change-password")
async def admin_change_password(request: Request):
    """Change admin password."""
    if not is_admin_authenticated():
        raise HTTPException(status_code=401)

    data = await request.json()
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not check_admin_password("Admin", current_pw):
        return {"success": False, "error": "Current password is incorrect"}

    if len(new_pw) < 6:
        return {"success": False, "error": "New password must be at least 6 characters"}

    from app.services.auth_service import hash_password
    import json
    admin_file = get_admin_file()
    admin_data = json.loads(admin_file.read_text(encoding="utf-8"))
    admin_data["password_hash"] = hash_password(new_pw)
    admin_file.write_text(json.dumps(admin_data, indent=2), encoding="utf-8")

    return {"success": True}
```

Also add this import at the top of admin.py:
```python
from app.services.admin_service import get_admin_file
```

**Step 4: Verify page renders**

Navigate to `/admin/settings` after admin login.

**Step 5: Commit**

```bash
git add templates/admin/settings.html app/routers/admin.py
git commit -m "feat: add admin settings page with password change"
```

---

## Task 13: Clean Up Old Admin Dashboard

Remove or redirect the old admin dashboard template now that all functionality has moved.

**Files:**
- Modify or delete: `templates/pages/admin_dashboard.html`
- Modify: `templates/pages/landing.html` (update admin button if needed)

**Step 1: Remove old admin template**

Delete `templates/pages/admin_dashboard.html` (all its functionality now lives in `templates/admin/dashboard.html` and `templates/admin/analytics.html`).

**Step 2: Verify landing page admin button points to `/admin`**

Check `templates/pages/landing.html` — the admin access button should link to `/admin`, which will redirect to `/admin/login` if not authenticated.

**Step 3: Run the full app and test all routes**

Navigate through all admin pages:
- `/admin` — Dashboard
- `/admin/services` — Service list
- `/admin/services/{slug}` — Service detail
- `/admin/tickets` — Tickets
- `/admin/analytics` — Charts
- `/admin/data-tools` — CSV upload
- `/admin/settings` — Settings
- Logout should return to `/landing`

**Step 4: Run all existing tests**

Run: `.venv/Scripts/python.exe -m pytest tests/ -v`
Expected: All tests PASS (no regressions)

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old admin dashboard, complete admin console migration"
```

---

## Summary of New Files

```
app/routers/admin.py                    # All admin routes (pages + API)
app/services/activity_service.py        # Activity tracking per service
app/services/ticket_service.py          # GitHub Issues integration
app/services/csv_import_service.py      # CSV provider import
templates/admin/admin_base.html         # Admin layout shell
templates/admin/components/sidebar.html # Admin sidebar (amber accent)
templates/admin/components/topbar.html  # Admin topbar
templates/admin/login.html              # Admin login page
templates/admin/dashboard.html          # Admin overview
templates/admin/services.html           # Service registry
templates/admin/service_detail.html     # Service drill-in
templates/admin/tickets.html            # GitHub Issues viewer
templates/admin/analytics.html          # Cross-service charts
templates/admin/data_tools.html         # CSV upload
templates/admin/settings.html           # Admin settings
tests/test_activity_service.py          # Activity service tests
tests/test_ticket_service.py            # Ticket parsing tests
tests/test_csv_import.py                # CSV import tests
```

## Modified Files

```
app/main.py                             # Register admin router
app/middleware/auth.py                   # Allow /admin/* prefix
app/routers/api.py                      # Remove migrated admin endpoints
app/routers/pages.py                    # Remove admin page route
app/services/admin_service.py           # Add last_active to service data
app/service_context.py                  # Log activity on service login
```
