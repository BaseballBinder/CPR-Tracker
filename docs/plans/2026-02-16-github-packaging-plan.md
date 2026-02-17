# GitHub Repository + .exe Packaging — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a private GitHub repository with CI/CD that auto-builds and releases the .exe when a version tag is pushed.

**Architecture:** Private GitHub repo (`CPR-Tracker`) with GitHub Actions workflow. Developer pushes a version tag → Actions builds .exe via PyInstaller → Release created with .exe attached. Manual distribution to end users.

**Tech Stack:** Git, GitHub CLI (`gh`), GitHub Actions, PyInstaller, Python 3.12

---

### Task 1: Install GitHub CLI

The `gh` CLI is not currently installed. It's needed to create the repo and manage releases.

**Step 1: Install gh via winget**

Run:
```bash
winget install --id GitHub.cli --accept-source-agreements --accept-package-agreements
```

**Step 2: Verify installation**

Open a NEW terminal (PATH won't update in current shell), then run:
```bash
gh --version
```
Expected: `gh version 2.x.x`

**Step 3: Authenticate with GitHub**

Run:
```bash
gh auth login
```

Follow the interactive prompts:
- Select `GitHub.com`
- Select `HTTPS`
- Authenticate via browser

**Step 4: Verify authentication**

Run:
```bash
gh auth status
```
Expected: Shows your GitHub username and authentication method.

---

### Task 2: Initialize Git Repository

The project directory is not yet a git repo.

**Files:**
- Modify: `.gitignore` (add a few more entries)

**Step 1: Update .gitignore to cover all artifacts**

Add these entries to the existing `.gitignore`:

```gitignore
# Environment / secrets
.env
*.pem
*.key

# PyInstaller working files
*.spec.bak
build/
dist/

# Test artifacts
.pytest_cache/
htmlcov/
.coverage

# Data files (user-specific, stored in AppData)
data/*.json
!data/schemas/
!data/schemas/*.json
```

Note: `dist/` and `build/` are already in the existing .gitignore. Just add the env/secrets and test lines.

**Step 2: Initialize git repo**

Run from the project root (`C:\Users\secre\Desktop\High Efficiency CPR\CPR Program`):
```bash
git init
```

**Step 3: Stage all files**

Run:
```bash
git add -A
```

**Step 4: Review staged files**

Run:
```bash
git status
```

Verify: No `venv/`, `dist/`, `build/`, `__pycache__/`, or data files are staged.

**Step 5: Create initial commit**

Run:
```bash
git commit -m "Initial commit: CPR Performance Tracker v1.0.0"
```

---

### Task 3: Create Private GitHub Repository and Push

**Step 1: Create the repo via gh CLI**

Run:
```bash
gh repo create CPR-Tracker --private --source=. --push --remote=origin
```

This creates the private repo, sets the remote, and pushes the initial commit in one command.

**Step 2: Verify the repo was created**

Run:
```bash
gh repo view --web
```

Expected: Opens the repo page in your browser. Should show all the project files.

---

### Task 4: Create GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/build.yml`

**Step 1: Create the workflow directory**

Run:
```bash
mkdir -p .github/workflows
```

**Step 2: Create the workflow file**

Create `.github/workflows/build.yml` with this content:

```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pyinstaller

      - name: Convert icon (if needed)
        run: |
          python -c "from PIL import Image; img = Image.open('static/images/logos/JcLS.png'); img.save('static/images/logos/JcLS.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
        continue-on-error: true

      - name: Build executable
        run: pyinstaller cpr_tracker.spec --clean --noconfirm

      - name: Verify build output
        run: |
          if (Test-Path "dist/CPR-Tracker.exe") {
            $size = (Get-Item "dist/CPR-Tracker.exe").Length
            Write-Host "Build successful! Size: $([math]::Round($size / 1MB, 2)) MB"
          } else {
            Write-Error "Build failed - CPR-Tracker.exe not found"
            exit 1
          }

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: dist/CPR-Tracker.exe
          generate_release_notes: true
          draft: false
          prerelease: false
```

**Step 3: Commit the workflow**

Run:
```bash
git add .github/workflows/build.yml
git commit -m "ci: add GitHub Actions build and release workflow"
git push
```

---

### Task 5: Configure Update Service

**Files:**
- Modify: `app/services/update_service.py` (lines 13-14)

**Step 1: Get your GitHub username**

Run:
```bash
gh api user --jq '.login'
```

Note the output (e.g., `your-username`).

**Step 2: Update the repo constants**

In `app/services/update_service.py`, replace lines 13-14:

```python
UPDATE_REPO_OWNER = ""
UPDATE_REPO_NAME = ""
```

With:
```python
UPDATE_REPO_OWNER = "<your-github-username>"
UPDATE_REPO_NAME = "CPR-Tracker"
```

Replace `<your-github-username>` with the actual username from Step 1.

**Step 3: Commit the update**

Run:
```bash
git add app/services/update_service.py
git commit -m "config: set GitHub repo for update checker"
git push
```

---

### Task 6: Test the Full Release Pipeline

**Step 1: Bump the version to trigger a release**

In `app/version.py`, change:
```python
__version__ = "1.0.0"
```
To:
```python
__version__ = "1.0.1"
```

**Step 2: Commit, tag, and push**

Run:
```bash
git add app/version.py
git commit -m "release: v1.0.1"
git tag v1.0.1
git push && git push --tags
```

**Step 3: Watch the build in GitHub Actions**

Run:
```bash
gh run watch
```

Or check in browser:
```bash
gh run list --web
```

Expected: The workflow runs, builds the .exe, and creates a Release at `v1.0.1` with `CPR-Tracker.exe` attached.

**Step 4: Verify the release**

Run:
```bash
gh release view v1.0.1
```

Expected: Shows the release with `CPR-Tracker.exe` as an asset.

**Step 5: Download the .exe to verify**

Run:
```bash
gh release download v1.0.1 --pattern "*.exe" --dir ./test-download
```

Expected: Downloads `CPR-Tracker.exe` to `./test-download/`.

**Step 6: Clean up test download**

Run:
```bash
rm -rf ./test-download
```

---

## Release Checklist (for future releases)

When you want to release a new version:

1. Update `app/version.py` with the new version number
2. Commit: `git commit -am "release: vX.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push && git push --tags`
5. GitHub Actions builds automatically
6. Download .exe from the Release page: `gh release download vX.Y.Z --pattern "*.exe"`
7. Share the .exe with users
