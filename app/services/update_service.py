"""
Auto-update service via GitHub Releases.
Checks for new versions and provides download URLs.
"""
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# This should be set to the actual GitHub repo once created
UPDATE_REPO_OWNER = "JCHanratty"
UPDATE_REPO_NAME = "CPR-Tracker"
GITHUB_API = "https://api.github.com"


def _parse_semver(version: str) -> tuple:
    """Parse a semver string like '1.2.3' into a tuple of ints."""
    version = version.lstrip("v")
    parts = version.split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return tuple(result[:3])


def check_for_update(current_version: str, repo_owner: str = "", repo_name: str = "") -> dict:
    """Check GitHub Releases for a newer version.

    Fetches all recent releases and finds the highest semver version,
    rather than relying on GitHub's /releases/latest endpoint which
    can return stale results.

    Returns:
        dict with keys:
            available (bool): Whether an update is available
            current_version (str): The current version
            latest_version (str): The latest version on GitHub (if found)
            download_url (str): URL to download the .exe (if available)
            release_notes (str): Release notes markdown (if available)
            error (str): Error message if check failed
    """
    owner = repo_owner or UPDATE_REPO_OWNER
    name = repo_name or UPDATE_REPO_NAME

    if not owner or not name:
        return {
            "available": False,
            "current_version": current_version,
            "error": "Update repository not configured",
        }

    url = f"{GITHUB_API}/repos/{owner}/{name}/releases?per_page=20"

    try:
        resp = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
        if resp.status_code != 200:
            return {
                "available": False,
                "current_version": current_version,
                "error": f"GitHub API returned {resp.status_code}",
            }

        releases = resp.json()
        if not releases:
            return {
                "available": False,
                "current_version": current_version,
                "error": "No releases found",
            }

        # Find the highest version release that isn't a draft or prerelease
        current_tuple = _parse_semver(current_version)
        best_version = current_tuple
        best_release = None

        for release in releases:
            if release.get("draft") or release.get("prerelease"):
                continue
            tag = release.get("tag_name", "")
            ver = _parse_semver(tag)
            if ver > best_version:
                best_version = ver
                best_release = release

        if best_release is None:
            return {
                "available": False,
                "current_version": current_version,
                "latest_version": current_version,
            }

        latest_version = best_release["tag_name"].lstrip("v")

        # Find .exe download URL
        download_url = ""
        for asset in best_release.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                download_url = asset["browser_download_url"]
                break

        return {
            "available": True,
            "current_version": current_version,
            "latest_version": latest_version,
            "download_url": download_url,
            "release_notes": best_release.get("body", ""),
            "release_url": best_release.get("html_url", ""),
        }
    except requests.RequestException as e:
        logger.warning(f"Update check failed: {e}")
        return {
            "available": False,
            "current_version": current_version,
            "error": str(e),
        }
