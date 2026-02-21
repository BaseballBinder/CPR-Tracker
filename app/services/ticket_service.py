"""
Ticket service — fetches and parses GitHub Issues for the admin dashboard.
Source of truth is GitHub; this service is read-only.
"""
import re
import logging
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_REPO = "JCHanratty/CPR-Tracker"


def _get_repo() -> str:
    return DEFAULT_REPO


def fetch_github_issues(state: str = "all", labels: Optional[str] = None) -> List[Dict]:
    repo = _get_repo()
    url = f"https://api.github.com/repos/{repo}/issues"
    params = {"state": state, "per_page": 100, "sort": "created", "direction": "desc"}
    if labels:
        params["labels"] = labels
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return [i for i in resp.json() if "pull_request" not in i]
    except Exception as e:
        logger.error(f"Failed to fetch GitHub issues: {e}")
        return []


def parse_github_issues(raw_issues: List[Dict]) -> List[Dict]:
    tickets = []
    for issue in raw_issues:
        labels = [l["name"] for l in issue.get("labels", [])]
        ticket_type = "bug" if "bug" in labels else "suggestion" if "suggestion" in labels else "other"
        body = issue.get("body") or ""
        service_match = re.search(r"Service:\s*(.+?)(?:\n|$)", body)
        service_name = service_match.group(1).strip() if service_match else "Unknown"
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
    raw = fetch_github_issues(state=state)
    return parse_github_issues(raw)
