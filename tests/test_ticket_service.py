from app.services.ticket_service import parse_github_issues


def test_parse_github_issues_extracts_fields():
    raw_issues = [
        {
            "number": 42,
            "title": "Button doesn't work on mobile",
            "body": "The submit button is unresponsive.\n\nService: Spruce Grove Fire",
            "labels": [{"name": "bug"}],
            "state": "open",
            "created_at": "2026-02-10T14:30:00Z",
            "closed_at": None,
            "milestone": None,
            "html_url": "https://github.com/test/repo/issues/42",
        },
        {
            "number": 43,
            "title": "Add dark mode toggle",
            "body": "Light mode option.\n\nService: Edmonton Fire",
            "labels": [{"name": "suggestion"}],
            "state": "closed",
            "created_at": "2026-02-08T09:00:00Z",
            "closed_at": "2026-02-15T11:00:00Z",
            "milestone": {"title": "v1.1.0"},
            "html_url": "https://github.com/test/repo/issues/43",
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
