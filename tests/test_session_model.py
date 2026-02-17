"""
Tests for Patch 1: Session model, status management, and retry logic.
"""
import pytest
import tempfile
import os
from pathlib import Path

from app.models import SessionType, SessionStatus, SessionMetrics, Session
from app.config import get_settings, Settings
from app.mock_data import (
    create_session,
    get_session_by_id,
    update_session,
    update_session_status,
    get_sessions_by_status,
    get_failed_sessions,
    SESSIONS,
)
from app.services.session_service import SessionService, get_session_service


class TestSessionModels:
    """Test Pydantic models."""

    def test_session_type_enum(self):
        """Test SessionType enum values."""
        assert SessionType.REAL_CALL.value == "real_call"
        assert SessionType.SIMULATED.value == "simulated"

    def test_session_status_enum(self):
        """Test SessionStatus enum values."""
        assert SessionStatus.IMPORTING.value == "importing"
        assert SessionStatus.COMPLETE.value == "complete"
        assert SessionStatus.FAILED.value == "failed"

    def test_session_metrics_model(self):
        """Test SessionMetrics model with PCO minute fields."""
        metrics = SessionMetrics(
            duration=120.5,
            compression_rate=110.0,
            compression_depth=5.5,
            correct_depth_percent=95.0,
            correct_rate_percent=88.0,
            cr_cmprt1=108.0,
            cr_cmprt2=112.0,
            cr_cdpth1=5.4,
            cr_cdpth2=5.6,
        )
        assert metrics.duration == 120.5
        assert metrics.cr_cmprt1 == 108.0
        assert metrics.cr_cdpth2 == 5.6


class TestConfig:
    """Test configuration settings."""

    def test_settings_defaults(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.upload_tmp_dir.name == "uploads"
        assert settings.export_output_dir.name == "exports"

    def test_directories_created(self):
        """Test that required directories are created."""
        settings = get_settings()
        assert settings.upload_tmp_dir.exists()
        assert settings.export_output_dir.exists()


class TestSessionCreation:
    """Test session creation functions."""

    def test_create_real_call_session(self):
        """Test creating a Real Call session."""
        initial_count = len(SESSIONS)

        session = create_session(
            session_type=SessionType.REAL_CALL,
            date="2025-12-30",
            time="14:30:00",
            event_type="Cardiac Arrest",
            primary_provider_id="EMP001",
            participant_ids=["EMP002", "EMP003"],
        )

        assert session["id"] is not None
        assert session["session_type"] == "real_call"
        assert session["status"] == "importing"
        assert session["date"] == "2025-12-30"
        assert session["time"] == "14:30:00"
        assert session["provider_id"] == "EMP001"
        assert len(session["participants"]) == 3  # primary + 2 participants
        assert len(SESSIONS) == initial_count + 1

    def test_create_simulated_session(self):
        """Test creating a Simulated session."""
        session = create_session(
            session_type=SessionType.SIMULATED,
            date="2025-12-30",
            primary_provider_id="EMP005",
        )

        assert session["session_type"] == "simulated"
        assert session["event_type"] == "Simulated"
        assert session["status"] == "importing"


class TestSessionStatusUpdates:
    """Test session status update functions."""

    def test_update_session_status_to_complete(self):
        """Test marking session as complete."""
        session = create_session(
            session_type=SessionType.REAL_CALL,
            date="2025-12-30",
        )

        metrics = {
            "duration": 300,
            "compression_rate": 110,
            "correct_depth_percent": 92,
            "correct_rate_percent": 88,
        }

        updated = update_session_status(
            session_id=session["id"],
            status=SessionStatus.COMPLETE,
            metrics=metrics,
        )

        assert updated["status"] == "complete"
        assert updated["metrics"]["duration"] == 300
        assert updated["error_message"] is None

    def test_update_session_status_to_failed(self):
        """Test marking session as failed."""
        session = create_session(
            session_type=SessionType.REAL_CALL,
            date="2025-12-30",
        )

        updated = update_session_status(
            session_id=session["id"],
            status=SessionStatus.FAILED,
            error_message="Missing required CSV file: CaseStatistics.csv",
        )

        assert updated["status"] == "failed"
        assert "Missing required CSV" in updated["error_message"]

    def test_get_failed_sessions(self):
        """Test retrieving failed sessions."""
        # Create a failed session
        session = create_session(
            session_type=SessionType.REAL_CALL,
            date="2025-12-30",
        )
        update_session_status(
            session_id=session["id"],
            status=SessionStatus.FAILED,
            error_message="Test error",
        )

        failed = get_failed_sessions()
        assert any(s["id"] == session["id"] for s in failed)


class TestSessionService:
    """Test SessionService class."""

    def test_create_real_call_with_artifact(self):
        """Test creating Real Call session with file artifact."""
        service = get_session_service()

        # Create a temp file to simulate upload
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(b"fake zip content")
            tmp_path = tmp.name

        try:
            session = service.create_real_call_session(
                date="2025-12-30",
                time="15:00:00",
                primary_provider_id="EMP001",
                uploaded_file_path=tmp_path,
                original_filename="2025-12-30 15_00_00CprReport.zip",
            )

            assert session["artifact"] is not None
            assert session["artifact"]["original_filename"] == "2025-12-30 15_00_00CprReport.zip"
            assert Path(session["artifact"]["file_path"]).exists()

            # Cleanup
            service.delete_artifact(session["id"])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_retry_failed_session(self):
        """Test retry mechanism for failed sessions."""
        service = get_session_service()

        # Create a temp file for the artifact
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp.write(b"fake zip content")
            tmp_path = tmp.name

        try:
            # Create session with artifact
            session = service.create_real_call_session(
                date="2025-12-30",
                uploaded_file_path=tmp_path,
                original_filename="test.zip",
            )

            # Mark as failed
            service.mark_session_failed(session["id"], "Import failed: test error")

            # Check can retry
            can_retry, reason = service.can_retry_session(session["id"])
            assert can_retry, f"Should be able to retry: {reason}"

            # Retry
            success, message, retried = service.retry_session(session["id"])
            assert success
            assert retried["status"] == "importing"
            assert retried["error_message"] is None

            # Cleanup
            service.delete_artifact(session["id"])
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_cannot_retry_complete_session(self):
        """Test that complete sessions cannot be retried."""
        service = get_session_service()

        session = service.create_simulated_session(
            date="2025-12-30",
            metrics={"duration": 120, "compression_rate": 110},
        )

        # Session should be complete since metrics were provided
        can_retry, reason = service.can_retry_session(session["id"])
        assert not can_retry
        assert "not 'failed'" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
