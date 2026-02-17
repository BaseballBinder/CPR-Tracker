# GitHub Repository + .exe Packaging — Design Document

**Date:** 2026-02-16
**Status:** Approved

## Overview

Set up a private GitHub repository for the CPR Tracker project with GitHub Actions CI/CD to automatically build and release the .exe when a version tag is pushed. Distribution is manual — the developer downloads the built .exe from GitHub Releases and shares it directly.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Repo visibility | Private | Source code stays internal |
| Repo name | `CPR-Tracker` | Matches .exe output name |
| Build method | GitHub Actions CI/CD | Push tag → auto-build → Release created |
| Distribution | Manual sharing | Developer downloads .exe, shares via email/USB/drive |
| Update checker | Best-effort (dev only) | Private repo requires auth; end users won't see update prompts |

## Architecture

### Release Flow

```
Developer: bump app/version.py → commit → git tag v1.x.0 → git push --tags
GitHub Actions: checkout → Python 3.12 → pip install → PyInstaller → create Release with .exe
Developer: download .exe from GitHub Releases → share manually
```

### Repository Structure (new files)

- `.gitignore` — Python/PyInstaller/venv exclusions
- `.github/workflows/build.yml` — CI/CD pipeline
- `update_service.py` — configure repo owner/name (read from existing skeleton)

### GitHub Actions Workflow

**Trigger:** Push tag matching `v*`

**Steps:**
1. Checkout code
2. Set up Python 3.12
3. Install dependencies from `requirements.txt`
4. Run PyInstaller with `cpr_tracker.spec`
5. Create GitHub Release with the tag name
6. Upload `dist/CPR-Tracker.exe` as release asset

### Update Service

- Populate `UPDATE_REPO_OWNER` and `UPDATE_REPO_NAME` with actual values
- For private repos, the unauthenticated GitHub API call will return 404
- The update checker gracefully handles this (already returns None on errors)
- Future enhancement: optional token support for private repo update checking

## Out of Scope

- Auto-update download/install within the app
- Public release pages
- Code signing certificates
- Token-based update checking for end users
