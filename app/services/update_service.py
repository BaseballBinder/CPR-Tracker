"""
Auto-update service via GitHub Releases.
Checks for new versions and provides download URLs.
"""
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# This should be set to the actual GitHub repo once created
UPDATE_REPO_OWNER = ""
UPDATE_REPO_NAME = ""
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

    url = f"{GITHUB_API}/repos/{owner}/{name}/releases/latest"

    try:
        resp = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
        if resp.status_code == 404:
            return {
                "available": False,
                "current_version": current_version,
                "error": "No releases found",
            }
        if resp.status_code != 200:
            return {
                "available": False,
                "current_version": current_version,
                "error": f"GitHub API returned {resp.status_code}",
            }

        release = resp.json()
        latest_version = release.get("tag_name", "").lstrip("v")

        # Compare versions
        current_tuple = _parse_semver(current_version)
        latest_tuple = _parse_semver(latest_version)

        update_available = latest_tuple > current_tuple

        # Find .exe download URL
        download_url = ""
        for asset in release.get("assets", []):
            if asset["name"].lower().endswith(".exe"):
                download_url = asset["browser_download_url"]
                break

        return {
            "available": update_available,
            "current_version": current_version,
            "latest_version": latest_version,
            "download_url": download_url,
            "release_notes": release.get("body", ""),
            "release_url": release.get("html_url", ""),
        }
    except requests.RequestException as e:
        logger.warning(f"Update check failed: {e}")
        return {
            "available": False,
            "current_version": current_version,
            "error": str(e),
        }
