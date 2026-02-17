import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.services.activity_service import log_activity, get_activity_log, get_last_active


def _make_temp_service_dir():
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
    assert log[0]["type"] == "export"


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
