"""
Session service for managing CPR sessions.
Handles session creation, status updates, artifact storage, and retry logic.
"""
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from app.config import get_settings
from app.models import SessionType, SessionStatus, SessionArtifact
from app.mock_data import (
    SESSIONS,
    create_session,
    get_session_by_id,
    update_session,
    update_session_status,
    get_failed_sessions,
    get_provider_by_id,
)


class SessionService:
    """Service for managing CPR session lifecycle."""

    def __init__(self):
        self.settings = get_settings()

    def create_real_call_session(
        self,
        date: str,
        time: Optional[str] = None,
        outcome: Optional[str] = None,
        shocks_delivered: Optional[int] = None,
        primary_provider_id: Optional[str] = None,
        participant_ids: Optional[List[str]] = None,
        uploaded_file_path: Optional[str] = None,
        original_filename: Optional[str] = None,
        zoll_data_available: bool = True,
        resuscitation_attempted: Optional[str] = None,
        zoll_missing_reason: Optional[str] = None,
        platoon: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new Real Call session.
        Session is created with status='importing' if Zoll data is available,
        or 'complete' if no Zoll data (with appropriate flags set).
        """
        # Store artifact if file was uploaded
        artifact = None
        if uploaded_file_path and original_filename:
            artifact = self._store_artifact(uploaded_file_path, original_filename)

        session = create_session(
            session_type=SessionType.REAL_CALL,
            date=date,
            time=time,
            event_type="Cardiac Arrest",
            outcome=outcome,
            shocks_delivered=shocks_delivered,
            primary_provider_id=primary_provider_id,
            participant_ids=participant_ids,
            artifact=artifact,
            zoll_data_available=zoll_data_available,
            resuscitation_attempted=resuscitation_attempted,
            zoll_missing_reason=zoll_missing_reason,
            platoon=platoon,
        )

        return session

    def create_simulated_session(
        self,
        date: str,
        time: Optional[str] = None,
        primary_provider_id: Optional[str] = None,
        participant_ids: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        csv_file_path: Optional[str] = None,
        original_filename: Optional[str] = None,
        paste_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new Simulated session.
        For simulated sessions, metrics may be provided directly or parsed from CSV/paste.
        """
        # Store artifact if file was uploaded
        artifact = None
        if csv_file_path and original_filename:
            artifact = self._store_artifact(csv_file_path, original_filename, content_type="text/csv")
        elif paste_text:
            # Store paste text as a temporary file
            artifact = self._store_paste_text(paste_text)

        session = create_session(
            session_type=SessionType.SIMULATED,
            date=date,
            time=time,
            event_type="Simulated",
            primary_provider_id=primary_provider_id,
            participant_ids=participant_ids,
            artifact=artifact,
        )

        # If metrics are already provided (parsed), update session immediately
        if metrics:
            update_session_status(
                session_id=session["id"],
                status=SessionStatus.COMPLETE,
                metrics=metrics,
            )

        return session

    def _store_artifact(
        self,
        source_path: str,
        original_filename: str,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store an uploaded file in the uploads directory.
        Returns artifact metadata including file hash.
        """
        import hashlib

        # Generate unique filename
        ext = Path(original_filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        dest_path = self.settings.upload_tmp_dir / unique_filename

        # Copy file to uploads directory
        shutil.copy2(source_path, dest_path)

        # Compute SHA-256 hash of the file
        sha256 = hashlib.sha256()
        with open(dest_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        file_hash = sha256.hexdigest()

        # Determine content type if not provided
        if not content_type:
            if ext.lower() == ".zip":
                content_type = "application/zip"
            elif ext.lower() == ".csv":
                content_type = "text/csv"
            else:
                content_type = "application/octet-stream"

        return {
            "filename": unique_filename,
            "original_filename": original_filename,
            "file_path": str(dest_path),
            "content_type": content_type,
            "hash": file_hash,
            "uploaded_at": datetime.now().isoformat(),
        }

    def _store_paste_text(self, paste_text: str) -> Dict[str, Any]:
        """
        Store pasted text as a file in the uploads directory.
        Returns artifact metadata.
        """
        unique_filename = f"{uuid.uuid4().hex}.txt"
        dest_path = self.settings.upload_tmp_dir / unique_filename

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(paste_text)

        return {
            "filename": unique_filename,
            "original_filename": "pasted_data.txt",
            "file_path": str(dest_path),
            "content_type": "text/plain",
            "uploaded_at": datetime.now().isoformat(),
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        return get_session_by_id(session_id)

    def get_all_sessions(
        self,
        status_filter: Optional[SessionStatus] = None,
        session_type_filter: Optional[SessionType] = None,
    ) -> List[Dict[str, Any]]:
        """Get all sessions, optionally filtered by status and/or type."""
        sessions = SESSIONS.copy()

        if status_filter:
            status_value = status_filter.value if isinstance(status_filter, SessionStatus) else status_filter
            sessions = [s for s in sessions if s.get("status") == status_value]

        if session_type_filter:
            type_value = session_type_filter.value if isinstance(session_type_filter, SessionType) else session_type_filter
            sessions = [s for s in sessions if s.get("session_type") == type_value]

        return sessions

    def mark_session_complete(
        self,
        session_id: str,
        metrics: Dict[str, Any],
        canroc_master_payload: Optional[Dict[str, Any]] = None,
        canroc_pco_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark a session as successfully imported."""
        return update_session_status(
            session_id=session_id,
            status=SessionStatus.COMPLETE,
            metrics=metrics,
            canroc_master_payload=canroc_master_payload,
            canroc_pco_payload=canroc_pco_payload,
            error_message=None,  # Clear any previous error
        )

    def mark_session_failed(
        self,
        session_id: str,
        error_message: str,
    ) -> Optional[Dict[str, Any]]:
        """Mark a session as failed import."""
        return update_session_status(
            session_id=session_id,
            status=SessionStatus.FAILED,
            error_message=error_message,
        )

    def get_failed_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions with failed status."""
        return get_failed_sessions()

    def can_retry_session(self, session_id: str) -> Tuple[bool, str]:
        """
        Check if a session can be retried.
        Returns (can_retry, reason).
        """
        session = get_session_by_id(session_id)

        if not session:
            return False, "Session not found"

        if session.get("status") != SessionStatus.FAILED.value:
            return False, f"Session status is '{session.get('status')}', not 'failed'"

        if not session.get("artifact"):
            return False, "No artifact stored for retry"

        artifact_path = session["artifact"].get("file_path")
        if not artifact_path or not Path(artifact_path).exists():
            return False, "Artifact file no longer exists"

        return True, "Session can be retried"

    def retry_session(self, session_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Retry a failed session import.
        Returns (success, message, session).

        Note: The actual re-import logic will be implemented in Patch 2.
        This method just resets the status to 'importing' and returns the session
        with artifact info for the ingestion service to process.
        """
        can_retry, reason = self.can_retry_session(session_id)
        if not can_retry:
            return False, reason, None

        # Reset status to importing
        session = update_session_status(
            session_id=session_id,
            status=SessionStatus.IMPORTING,
            error_message=None,  # Clear previous error
        )

        return True, "Session queued for retry", session

    def get_artifact_path(self, session_id: str) -> Optional[Path]:
        """Get the path to a session's stored artifact."""
        session = get_session_by_id(session_id)
        if not session or not session.get("artifact"):
            return None

        artifact_path = session["artifact"].get("file_path")
        if artifact_path and Path(artifact_path).exists():
            return Path(artifact_path)

        return None

    def delete_artifact(self, session_id: str) -> bool:
        """Delete a session's stored artifact file."""
        artifact_path = self.get_artifact_path(session_id)
        if artifact_path and artifact_path.exists():
            artifact_path.unlink()
            return True
        return False

    def update_session_participants(
        self,
        session_id: str,
        primary_provider_id: Optional[str] = None,
        participant_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update session participants."""
        session = get_session_by_id(session_id)
        if not session:
            return None

        participants = []

        if primary_provider_id:
            primary_provider = get_provider_by_id(primary_provider_id)
            if primary_provider:
                participants.append({
                    "provider_id": primary_provider_id,
                    "provider_name": primary_provider["name"],
                    "is_primary": True,
                })

        if participant_ids:
            for pid in participant_ids:
                if pid != primary_provider_id:
                    provider = get_provider_by_id(pid)
                    if provider:
                        participants.append({
                            "provider_id": pid,
                            "provider_name": provider["name"],
                            "is_primary": False,
                        })

        # Update session
        updates = {"participants": participants}
        if primary_provider_id:
            primary_provider = get_provider_by_id(primary_provider_id)
            if primary_provider:
                updates["provider_id"] = primary_provider_id
                updates["provider_name"] = primary_provider["name"]

        return update_session(session_id, updates)


# Singleton instance
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """Get the singleton session service instance."""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service
