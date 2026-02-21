# Fix Auto-Update Flow

**Date:** 2026-02-21
**Status:** Approved

## Problem

The auto-update flow is broken: the app downloads the update but never applies it or shuts down. Two root causes:

### Bug 1: Auth middleware blocks update action endpoints
The landing page (where updates are shown) has no service logged in. The security hardening in v1.6.0 correctly removed `/api/updates/` from `PUBLIC_PREFIXES` but only added `/api/updates/check` to `PUBLIC_PATHS`. The three action endpoints (`download-stream`, `apply`, `shutdown`) get 302-redirected to `/landing` and silently fail.

### Bug 2: `sys.exit(0)` doesn't terminate pywebview
The shutdown endpoint calls `sys.exit(0)` from a daemon thread. In pywebview, the main thread is blocked in `webview.start()` — `sys.exit()` from a non-main thread only raises `SystemExit` in that thread, not the main process. The app never closes, so the update `.bat` script waits forever for the PID to exit.

## Solution

1. Add `/api/updates/download-stream`, `/api/updates/apply`, `/api/updates/shutdown` to `PUBLIC_PATHS` in auth middleware. These endpoints are already protected by URL whitelisting (C1 fix) and path validation (C2 fix).

2. Use `os._exit(0)` specifically in the shutdown-for-update endpoint. This is the one case where hard-kill is correct — we need to terminate the entire process immediately so the update script can swap the executable. Keep `sys.exit(0)` everywhere else.

## Files Changed
- `app/middleware/auth.py` — add 3 paths to `PUBLIC_PATHS`
- `app/routers/api.py` — change `sys.exit(0)` to `os._exit(0)` in shutdown endpoint only
