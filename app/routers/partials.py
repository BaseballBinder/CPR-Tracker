"""
HTMX partial endpoints - return HTML fragments for dynamic updates.
"""
import logging
import os
import re

logger = logging.getLogger(__name__)
import shutil
import tempfile
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse

from app.mock_data import (
    PROVIDERS, TEAMS, SESSIONS,
    get_provider_by_id, get_sessions_by_provider, get_sessions_by_team,
    get_dashboard_kpis, add_provider, get_ranked_providers, get_provider_stats,
    create_session, update_session_status,
)
from app.models import SessionType, SessionStatus
from app.services.session_service import get_session_service
from app.services.ingestion_service import process_session_import, parse_simulated_csv

router = APIRouter(prefix="/partials")


def extract_date_from_zip_filename(filename: str) -> Optional[str]:
    """
    Extract date from ZOLL CPR Report ZIP filename.
    Expected format: 2025-12-30 15_00_00CprReport.zip or similar
    Returns date in YYYY-MM-DD format or None if not found.
    """
    if not filename:
        return None

    # Pattern: YYYY-MM-DD at the start of filename
    pattern = r'(\d{4}-\d{2}-\d{2})'
    match = re.search(pattern, filename)

    if match:
        date_str = match.group(1)
        # Validate it's a real date
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            return None

    return None


def match_provider_name(provider_name: str, providers: List[dict]) -> Optional[dict]:
    """
    Try to match a provider name to an existing provider.
    Returns the matched provider dict or None if no match.
    """
    if not provider_name:
        return None

    provider_name_lower = provider_name.lower().strip()
    for provider in providers:
        if provider.get("status") == "active":
            prov_name = provider.get("name", "")
            prov_name_lower = prov_name.lower()
            # Case-insensitive partial match
            if provider_name_lower in prov_name_lower or prov_name_lower in provider_name_lower:
                return provider
    return None


def parse_and_match_simulated_csv(content: str, providers: List[dict]) -> List[dict]:
    """
    Parse simulated CSV and match provider names to existing providers.
    Returns list of parsed rows with matching info for preview.
    """
    parsed_rows = parse_simulated_csv(content)
    preview_rows = []

    for i, row in enumerate(parsed_rows):
        provider_name = row.get("provider_name", "")
        matched_provider = match_provider_name(provider_name, providers)

        preview_row = {
            "row_index": i,
            "date": row.get("date", ""),
            "provider_name_original": provider_name,
            "matched_provider_id": matched_provider["id"] if matched_provider else None,
            "matched_provider_name": matched_provider["name"] if matched_provider else None,
            "is_matched": matched_provider is not None,
            "duration": row.get("duration"),
            "compression_rate": row.get("compression_rate"),
            "compression_depth": row.get("compression_depth"),
            "correct_depth_percent": row.get("correct_depth_percent"),
            "correct_rate_percent": row.get("correct_rate_percent"),
            "notes": row.get("notes", ""),
        }
        preview_rows.append(preview_row)

    return preview_rows


# Report Issue modal
@router.get("/report-issue", response_class=HTMLResponse)
async def report_issue_modal(request: Request):
    """Report issue modal partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/report_issue.html",
        {"request": request}
    )


# Dashboard partials
@router.get("/dashboard/kpis", response_class=HTMLResponse)
async def dashboard_kpis(request: Request):
    """Dashboard KPI cards partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/dashboard/kpis.html",
        {"request": request, "kpis": get_dashboard_kpis()}
    )


@router.get("/dashboard/recent-sessions", response_class=HTMLResponse)
async def dashboard_recent_sessions(request: Request):
    """Dashboard recent sessions table partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/dashboard/recent_sessions.html",
        {"request": request, "sessions": SESSIONS[:5]}
    )


@router.get("/dashboard/trend-chart", response_class=HTMLResponse)
async def dashboard_trend_chart(request: Request):
    """Dashboard trend chart partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/dashboard/trend_chart.html",
        {"request": request}
    )


# Sessions partials
@router.get("/sessions/table", response_class=HTMLResponse)
async def sessions_table(request: Request, team: str = None, outcome: str = None, event_type: str = None, status: str = None):
    """Sessions table partial with optional filters."""
    filtered = SESSIONS
    if team:
        filtered = [s for s in filtered if s["team_id"] == team]
    if outcome:
        filtered = [s for s in filtered if s["outcome"] == outcome]
    if event_type:
        filtered = [s for s in filtered if s["event_type"] == event_type]
    if status:
        filtered = [s for s in filtered if s.get("status") == status]

    return request.app.state.templates.TemplateResponse(
        "partials/sessions/table.html",
        {"request": request, "sessions": filtered}
    )


@router.post("/sessions/{session_id}/retry", response_class=HTMLResponse)
async def sessions_retry(request: Request, session_id: str):
    """Retry a failed session import and return updated sessions table."""
    from pathlib import Path

    service = get_session_service()

    can_retry, reason = service.can_retry_session(session_id)
    if can_retry:
        # Reset status to importing
        service.retry_session(session_id)

        # Get artifact path and run ingestion
        artifact_path = service.get_artifact_path(session_id)
        if artifact_path:
            process_session_import(session_id, artifact_path)

    # Sort sessions by date descending before returning
    sorted_sessions = sorted(SESSIONS, key=lambda s: s.get("date", ""), reverse=True)

    # Return the updated sessions table
    return request.app.state.templates.TemplateResponse(
        "partials/sessions/table.html",
        {"request": request, "sessions": sorted_sessions}
    )


@router.delete("/sessions/{session_id}", response_class=HTMLResponse)
async def delete_session_endpoint(request: Request, session_id: str):
    """Delete a session and return updated sessions table."""
    from app.mock_data import delete_session

    deleted = delete_session(session_id)

    # Sort sessions by date descending (most recent first) before returning
    sorted_sessions = sorted(SESSIONS, key=lambda s: s.get("date", ""), reverse=True)

    # Return the updated sessions table
    return request.app.state.templates.TemplateResponse(
        "partials/sessions/table.html",
        {"request": request, "sessions": sorted_sessions}
    )


@router.post("/sessions/{session_id}/toggle-completion", response_class=HTMLResponse)
async def toggle_session_completion(request: Request, session_id: str):
    """Toggle a completion field (report_sent, canroc_complete, ehs_report_complete) for a session."""
    from app.mock_data import get_session_by_id, update_session

    session = get_session_by_id(session_id)
    if not session:
        return HTMLResponse(status_code=404, content="Session not found")

    form_data = await request.form()
    field = form_data.get("field")

    # Validate field name
    valid_fields = ["report_sent", "canroc_complete", "ehs_report_complete"]
    if field not in valid_fields:
        return HTMLResponse(status_code=400, content="Invalid field")

    # Toggle the field value
    current_value = session.get(field, False)
    new_value = not current_value

    # Update the session
    update_session(session_id, {field: new_value})

    # Return empty response (checkbox state is managed client-side)
    return HTMLResponse(status_code=200, content="")


@router.get("/sessions/{session_id}/detail", response_class=HTMLResponse)
async def session_detail_modal(request: Request, session_id: str):
    """Session detail modal partial."""
    from app.mock_data import get_session_by_id

    session = get_session_by_id(session_id)
    if not session:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    # Get provider info
    provider = None
    if session.get("provider_id"):
        provider = get_provider_by_id(session["provider_id"])

    return request.app.state.templates.TemplateResponse(
        "partials/sessions/detail_modal.html",
        {
            "request": request,
            "session": session,
            "provider": provider,
        }
    )


@router.get("/sessions/{session_id}/edit", response_class=HTMLResponse)
async def session_edit_modal(request: Request, session_id: str):
    """Session edit modal partial."""
    from app.mock_data import get_session_by_id

    session = get_session_by_id(session_id)
    if not session:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    return request.app.state.templates.TemplateResponse(
        "partials/sessions/edit_modal.html",
        {
            "request": request,
            "session": session,
            "providers": PROVIDERS,
        }
    )


@router.post("/sessions/{session_id}/update", response_class=HTMLResponse)
async def session_update(request: Request, session_id: str):
    """Update session details and return success modal."""
    from app.mock_data import get_session_by_id, update_session

    session = get_session_by_id(session_id)
    if not session:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    form_data = await request.form()

    # Parse form data
    date = form_data.get("date", session.get("date"))
    outcome = form_data.get("outcome", "")
    shocks_delivered_str = form_data.get("shocks_delivered", "")
    primary_provider_id = form_data.get("primary_provider_id", "")
    participant_ids = form_data.getlist("participant_ids")

    # Parse shocks
    shocks_delivered = None
    if shocks_delivered_str:
        try:
            shocks_delivered = int(shocks_delivered_str)
        except ValueError:
            pass

    # Build participants list
    participants = []
    if primary_provider_id:
        primary_provider = get_provider_by_id(primary_provider_id)
        if primary_provider:
            participants.append({
                "provider_id": primary_provider_id,
                "provider_name": primary_provider["name"],
                "is_primary": True
            })

    for pid in participant_ids:
        if pid != primary_provider_id:
            provider = get_provider_by_id(pid)
            if provider:
                participants.append({
                    "provider_id": pid,
                    "provider_name": provider["name"],
                    "is_primary": False
                })

    # Get primary provider info
    primary_provider = get_provider_by_id(primary_provider_id) if primary_provider_id else None

    # Get platoon from form
    platoon = form_data.get("platoon", "")

    # Update session
    updates = {
        "date": date,
        "outcome": outcome if outcome else None,
        "shocks_delivered": shocks_delivered,
        "provider_id": primary_provider_id if primary_provider_id else None,
        "provider_name": primary_provider["name"] if primary_provider else None,
        "participants": participants,
        "platoon": platoon if platoon else None,
    }

    # If session was "pending" and now has a provider, update status
    if session.get("status") == "pending" and primary_provider_id:
        # Determine new status based on session type and Zoll data
        if session.get("session_type") == "real_call" and session.get("zoll_data_available"):
            updates["status"] = "importing"  # Will be processed for metrics
        else:
            updates["status"] = "complete"  # No metrics to process

    updated_session = update_session(session_id, updates)

    # Return success message modal
    return HTMLResponse(f"""
        <div class="fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4" onclick="if(event.target === this) {{ document.getElementById('modal-container').innerHTML = ''; window.location.reload(); }}">
            <div class="bg-white rounded-[6px] border border-slate-200 shadow-lg p-6 text-center max-w-sm">
                <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg class="w-6 h-6 text-[#16a34a]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                </div>
                <h3 class="text-lg font-semibold text-slate-800 mb-2">Session Updated</h3>
                <p class="text-sm text-slate-500 mb-4">Changes have been saved successfully.</p>
                <button onclick="document.getElementById('modal-container').innerHTML = ''; window.location.reload();"
                        class="px-4 py-2 bg-[#dc2626] text-white text-sm font-medium rounded-[6px] hover:bg-[#b91c1c] transition-colors">
                    Done
                </button>
            </div>
        </div>
    """)


# Rankings partials
@router.get("/rankings/providers", response_class=HTMLResponse)
async def rankings_providers(request: Request, metric: str = "jcls_score", event_type: str = None):
    """Provider rankings table partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/rankings/providers.html",
        {"request": request, "ranked_providers": get_ranked_providers(), "teams": TEAMS}
    )


@router.get("/rankings/teams", response_class=HTMLResponse)
async def rankings_teams(request: Request):
    """Team rankings table partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/rankings/teams.html",
        {"request": request, "teams": TEAMS}
    )


# Provider detail partials
@router.get("/provider/{provider_id}/sessions", response_class=HTMLResponse)
async def provider_sessions(request: Request, provider_id: str):
    """Provider sessions table partial."""
    sessions = get_sessions_by_provider(provider_id)
    return request.app.state.templates.TemplateResponse(
        "partials/provider/sessions.html",
        {"request": request, "sessions": sessions}
    )


@router.get("/provider/{provider_id}/chart", response_class=HTMLResponse)
async def provider_chart(request: Request, provider_id: str):
    """Provider performance chart partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/provider/chart.html",
        {"request": request, "provider_id": provider_id}
    )


# Team analysis partials
@router.get("/teams/table", response_class=HTMLResponse)
async def teams_table(request: Request, combo_size: str = None, event_type: str = None):
    """Team analysis table partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/teams/table.html",
        {"request": request, "teams": TEAMS, "sessions": SESSIONS}
    )


# Providers list partials
@router.get("/providers/table", response_class=HTMLResponse)
async def providers_table(request: Request, status: str = None, team: str = None, certification: str = None):
    """Providers table partial with optional filters."""
    filtered = PROVIDERS
    if status:
        filtered = [p for p in filtered if p["status"] == status]
    if team:
        filtered = [p for p in filtered if p["team_id"] == team]
    if certification:
        filtered = [p for p in filtered if p.get("certification") == certification]

    return request.app.state.templates.TemplateResponse(
        "partials/providers/table.html",
        {"request": request, "providers": filtered, "teams": TEAMS}
    )


@router.get("/providers/add-modal", response_class=HTMLResponse)
async def providers_add_modal(request: Request):
    """Add provider modal partial."""
    return request.app.state.templates.TemplateResponse(
        "partials/providers/add_modal.html",
        {"request": request}
    )


@router.get("/providers/{provider_id}/edit-modal", response_class=HTMLResponse)
async def providers_edit_modal(request: Request, provider_id: str):
    """Edit provider modal partial."""
    provider = get_provider_by_id(provider_id)
    if not provider:
        return HTMLResponse(content="<div>Provider not found</div>", status_code=404)

    return request.app.state.templates.TemplateResponse(
        "partials/providers/edit_modal.html",
        {"request": request, "provider": provider}
    )


@router.get("/providers/{provider_id}/delete-modal", response_class=HTMLResponse)
async def providers_delete_modal(request: Request, provider_id: str):
    """Delete provider confirmation modal."""
    provider = get_provider_by_id(provider_id)
    if not provider:
        return HTMLResponse(content="<div>Provider not found</div>", status_code=404)

    return request.app.state.templates.TemplateResponse(
        "partials/providers/delete_modal.html",
        {"request": request, "provider": provider}
    )


@router.post("/providers/{provider_id}/update", response_class=HTMLResponse)
async def providers_update(request: Request, provider_id: str):
    """Update provider details."""
    from app.persistence import load_providers, save_providers

    provider = get_provider_by_id(provider_id)
    if not provider:
        return HTMLResponse(content="<div>Provider not found</div>", status_code=404)

    form_data = await request.form()
    first_name = form_data.get("first_name", "").strip()
    last_name = form_data.get("last_name", "").strip()
    certification = form_data.get("certification", "").strip()
    status = form_data.get("status", "active")

    errors = {}
    if not first_name:
        errors["first_name"] = "First name is required"
    if not last_name:
        errors["last_name"] = "Last name is required"
    if not certification:
        errors["certification"] = "Certification is required"

    if errors:
        return request.app.state.templates.TemplateResponse(
            "partials/providers/edit_modal.html",
            {
                "request": request,
                "provider": provider,
                "errors": errors,
                "first_name": first_name,
                "last_name": last_name,
                "certification": certification,
                "status": status,
            }
        )

    # Update provider data
    provider["first_name"] = first_name
    provider["last_name"] = last_name
    provider["name"] = f"{first_name} {last_name}"
    provider["certification"] = certification
    provider["status"] = status

    # Save to disk
    user_providers = load_providers()
    # Find and update in user providers list
    found = False
    for i, p in enumerate(user_providers):
        if p["id"] == provider_id:
            user_providers[i] = provider
            found = True
            break

    # If not in user providers, add it (shouldn't happen but safe fallback)
    if not found:
        user_providers.append(provider)

    save_providers(user_providers)

    # Also update in PROVIDERS global list
    for i, p in enumerate(PROVIDERS):
        if p["id"] == provider_id:
            PROVIDERS[i] = provider
            break

    # Close modal and show success
    return HTMLResponse(content="""
        <script>
            document.getElementById('modal-container').innerHTML = '';
            window.location.reload();
        </script>
    """)


# ============================================================================
# Wizard modal steps - New Add Session Flow
# ============================================================================

@router.get("/session/wizard/step/{step}", response_class=HTMLResponse)
async def wizard_step(request: Request, step: int):
    """New session wizard step partial."""
    step = max(1, min(4, step))  # Clamp to 1-4 (new wizard has 4 steps)
    return request.app.state.templates.TemplateResponse(
        f"partials/wizard/step_{step}.html",
        {"request": request, "step": step, "teams": TEAMS, "providers": PROVIDERS}
    )


@router.post("/session/wizard/validate/{step}", response_class=HTMLResponse)
async def wizard_validate(request: Request, step: int):
    """Validate wizard step and return next step or errors."""
    form_data = await request.form()
    errors = {}

    # Step 1: Session Type + ZIP Upload (for Real Calls)
    if step == 1:
        session_type = form_data.get("session_type")
        service = get_session_service()
        artifact_filename = ""
        event_date = ""
        event_time = ""

        if not session_type:
            errors["session_type"] = "Please select a session type"

        # For Real Calls, expect ZIP file upload
        if session_type == "real_call":
            zip_file = form_data.get("zip_file")
            if zip_file and hasattr(zip_file, 'filename') and zip_file.filename:
                # Note: ZIP filename date is download date, not call date
                # Date will be entered manually in Step 2

                # Check for duplicates
                existing_sessions = [s for s in SESSIONS if s.get("artifact") and s.get("artifact", {}).get("original_filename") == zip_file.filename]
                if existing_sessions:
                    errors["zip_file"] = f"This file '{zip_file.filename}' has already been imported."
                else:
                    # Save file temporarily (with 50MB size limit)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        content = await zip_file.read()
                        if len(content) > 50 * 1024 * 1024:  # 50MB
                            errors["zip_file"] = "ZIP file exceeds 50MB size limit."
                        else:
                            tmp.write(content)
                        tmp_path = tmp.name
                        artifact_filename = zip_file.filename

                    # Store artifact
                    try:
                        artifact = service._store_artifact(tmp_path, zip_file.filename)
                        artifact_filename = artifact["filename"]
                    finally:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
            else:
                errors["zip_file"] = "Please upload a CPR Report ZIP file"

        if errors:
            return request.app.state.templates.TemplateResponse(
                "partials/wizard/step_1.html",
                {
                    "request": request,
                    "step": 1,
                    "teams": TEAMS,
                    "providers": PROVIDERS,
                    "errors": errors,
                    "session_type": session_type,
                }
            )

        # Success - go to step 2 with extracted data
        # Use appropriate Step 2 template based on session type
        step_2_template = "partials/wizard/step_2_real.html" if session_type == "real_call" else "partials/wizard/step_2_sim.html"
        return request.app.state.templates.TemplateResponse(
            step_2_template,
            {
                "request": request,
                "step": 2,
                "teams": TEAMS,
                "providers": PROVIDERS,
                "session_type": session_type,
                "event_date": event_date,
                "event_time": event_time,
                "artifact_filename": artifact_filename,
            }
        )

    # Step 2: Data Input (Team Lead & Details for Real Call, CSV/Paste for Simulated)
    elif step == 2:
        session_type = form_data.get("session_type")
        event_date = form_data.get("event_date")
        event_time = form_data.get("event_time", "")
        primary_provider_id = form_data.get("primary_provider_id", "")
        outcome = form_data.get("outcome", "")  # ROSC outcome for real calls
        shocks_delivered = form_data.get("shocks_delivered", "")  # Number of shocks
        platoon = form_data.get("platoon", "")  # Platoon assignment

        # For Real Calls, artifact_filename is passed from Step 1 (ZIP already uploaded)
        # For Simulated, we'll handle CSV upload here
        artifact_filename = form_data.get("artifact_filename", "")

        # Zoll data is always available for Real Calls (uploaded in Step 1)
        zoll_data_available = True if session_type == "real_call" else False

        # Collect participant IDs from checkboxes
        participant_ids = form_data.getlist("participant_ids")
        participant_ids_str = ",".join(participant_ids) if participant_ids else ""

        service = get_session_service()

        # Handle file uploads based on session type
        parse_error = None
        preview_metrics = None
        preview_rows = []
        unmatched_count = 0

        # Team Lead is now optional - sessions without provider will be marked as "pending"
        # No validation error if primary_provider_id is empty

        if session_type == "real_call":
            # ZIP file was uploaded in Step 1 - artifact_filename should be present
            if not artifact_filename:
                errors["artifact_filename"] = "ZIP file missing from Step 1. Please go back and upload the file."
        else:
            # Simulated - accept CSV file or paste text
            csv_file = form_data.get("csv_file")
            paste_text = form_data.get("paste_text", "")
            csv_content = ""

            if csv_file and hasattr(csv_file, 'filename') and csv_file.filename:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    content = await csv_file.read()
                    if len(content) > 5 * 1024 * 1024:  # 5MB
                        errors["paste_text"] = "CSV file exceeds 5MB size limit."
                    else:
                        tmp.write(content)
                    tmp_path = tmp.name
                    artifact_filename = csv_file.filename
                    csv_content = content.decode('utf-8-sig')  # Also keep content for preview

                try:
                    artifact = service._store_artifact(tmp_path, csv_file.filename, "text/csv")
                    artifact_filename = artifact["filename"]
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            elif paste_text.strip():
                artifact = service._store_paste_text(paste_text)
                artifact_filename = artifact["filename"]
                csv_content = paste_text.strip()
            else:
                errors["paste_text"] = "Please provide session data (paste or upload CSV)"

            # Parse CSV and match providers for preview (simulated sessions only)
            preview_rows = []
            unmatched_count = 0
            if csv_content and not errors:
                preview_rows = parse_and_match_simulated_csv(csv_content, PROVIDERS)
                unmatched_count = sum(1 for r in preview_rows if not r["is_matched"] and r["provider_name_original"])

        # Final validation: Ensure we have a date
        if not event_date:
            errors["event_date"] = "Call date is required. Please enter the date of the emergency call."

        if errors:
            # Return to appropriate step 2 template based on session type
            step_2_template = "partials/wizard/step_2_real.html" if session_type == "real_call" else "partials/wizard/step_2_sim.html"
            return request.app.state.templates.TemplateResponse(
                step_2_template,
                {
                    "request": request,
                    "step": 2,
                    "teams": TEAMS,
                    "providers": PROVIDERS,
                    "errors": errors,
                    "session_type": session_type,
                    "event_date": event_date,
                    "event_time": event_time,
                    "artifact_filename": artifact_filename,
                    # Preserve user's selections on error
                    "primary_provider_id": primary_provider_id,
                    "selected_participant_ids": participant_ids,
                    "outcome": outcome,
                    "shocks_delivered": shocks_delivered,
                    "platoon": platoon,
                }
            )

        # Get provider name for display
        primary_provider_name = None
        if primary_provider_id:
            provider = get_provider_by_id(primary_provider_id)
            if provider:
                primary_provider_name = provider["name"]

        # Build parse message based on session type
        if session_type == "simulated" and preview_rows:
            if unmatched_count > 0:
                parse_message = f"Parsed {len(preview_rows)} session(s). {unmatched_count} provider(s) need assignment."
            else:
                parse_message = f"Parsed {len(preview_rows)} session(s). All providers matched."
        elif session_type == "real_call":
            parse_message = "ZIP file uploaded successfully. Ready to save session."
        else:
            parse_message = "Data uploaded successfully. Ready to save."

        # Go to step 3 (Preview)
        return request.app.state.templates.TemplateResponse(
            "partials/wizard/step_3.html",
            {
                "request": request,
                "step": 3,
                "teams": TEAMS,
                "providers": PROVIDERS,
                "session_type": session_type,
                "event_date": event_date,
                "event_time": event_time,
                "primary_provider_id": primary_provider_id,
                "primary_provider_name": primary_provider_name,
                "participant_ids": participant_ids_str,
                "participant_count": len(participant_ids),
                "artifact_filename": artifact_filename,
                "parse_error": parse_error,
                "parse_message": parse_message,
                "preview_metrics": preview_metrics,
                # ROSC outcome and shocks (real calls only)
                "outcome": outcome if session_type == "real_call" else "",
                "shocks_delivered": shocks_delivered if session_type == "real_call" else "",
                "platoon": platoon,
                # Zoll data is always available for Real Calls (ZIP uploaded in Step 1)
                "zoll_data_available": zoll_data_available,
                # Simulated session preview data
                "preview_rows": preview_rows if session_type == "simulated" else [],
                "unmatched_count": unmatched_count if session_type == "simulated" else 0,
            }
        )

    # Step 3: Preview and Save
    elif step == 3:
        session_type = form_data.get("session_type")
        event_date = form_data.get("event_date")
        event_time = form_data.get("event_time", "")
        primary_provider_id = form_data.get("primary_provider_id", "")
        participant_ids_str = form_data.get("participant_ids", "")
        artifact_filename = form_data.get("artifact_filename", "")
        outcome = form_data.get("outcome", "")  # ROSC outcome
        shocks_delivered = form_data.get("shocks_delivered", "")  # Number of shocks
        platoon = form_data.get("platoon", "")  # Platoon assignment

        # Zoll data availability fields (real calls only)
        zoll_data_available_str = form_data.get("zoll_data_available", "true")
        zoll_data_available = zoll_data_available_str.lower() == "true"
        resuscitation_attempted = form_data.get("resuscitation_attempted", "")
        zoll_missing_reason = form_data.get("zoll_missing_reason", "")

        # Parse participant IDs
        participant_ids = [pid.strip() for pid in participant_ids_str.split(",") if pid.strip()]

        # Create the session
        service = get_session_service()

        # Build artifact info if we have one
        artifact = None
        if artifact_filename:
            artifact_path = service.settings.upload_tmp_dir / artifact_filename
            logger.debug(f"Looking for artifact: {artifact_filename}, exists: {artifact_path.exists()}")
            if artifact_path.exists():
                artifact = {
                    "filename": artifact_filename,
                    "original_filename": artifact_filename,
                    "file_path": str(artifact_path),
                    "content_type": "application/zip" if artifact_filename.endswith(".zip") else "text/csv",
                }
            else:
                logger.warning(f"Artifact file not found: {artifact_filename}")

        session_type_enum = SessionType.REAL_CALL if session_type == "real_call" else SessionType.SIMULATED
        error_message = None
        created_sessions = []

        if session_type == "real_call":
            # Parse shocks_delivered to int
            shocks_int = None
            if shocks_delivered:
                try:
                    shocks_int = int(shocks_delivered)
                except ValueError:
                    pass

            session = service.create_real_call_session(
                date=event_date,
                time=event_time or None,
                outcome=outcome or None,
                shocks_delivered=shocks_int,
                primary_provider_id=primary_provider_id or None,
                participant_ids=participant_ids,
                zoll_data_available=zoll_data_available,
                resuscitation_attempted=resuscitation_attempted or None,
                zoll_missing_reason=zoll_missing_reason or None,
                platoon=platoon or None,
            )
            # Store artifact reference in session
            if artifact:
                from app.mock_data import update_session
                update_session(session["id"], {"artifact": artifact})
                session["artifact"] = artifact

            # Run ingestion for real call sessions (only if Zoll data available)
            if artifact and zoll_data_available:
                from pathlib import Path
                artifact_path = Path(artifact["file_path"])
                logger.debug(f"Starting import for session {session['id']}")
                try:
                    success, message, parsed_metrics = process_session_import(session["id"], artifact_path)
                    if success:
                        session["status"] = SessionStatus.COMPLETE.value
                        session["metrics"] = parsed_metrics
                    else:
                        session["status"] = SessionStatus.FAILED.value
                        session["error_message"] = message
                        error_message = message
                        logger.warning(f"Import failed for session {session['id']}: {message}")
                except Exception as e:
                    logger.error(f"Exception during import for session {session['id']}: {e}", exc_info=True)
                    session["status"] = SessionStatus.FAILED.value
                    session["error_message"] = "Import failed due to an unexpected error"
                    error_message = "Import failed due to an unexpected error"
            else:
                logger.warning(f"No artifact found for session {session['id']}")

            created_sessions = [session]
        else:
            # For simulated sessions, parse the artifact file for data
            # and use provider assignments from the preview step

            created_sessions = []
            error_message = None

            if artifact_filename:
                artifact_path = service.settings.upload_tmp_dir / artifact_filename
                if artifact_path.exists():
                    try:
                        with open(artifact_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Parse CSV and get rows
                        parsed_rows = parse_simulated_csv(content)

                        if not parsed_rows:
                            error_message = "No valid data rows found in the input"
                        else:
                            # Collect provider assignments from form (provider_0, provider_1, etc.)
                            provider_assignments = {}
                            for key in form_data.keys():
                                if key.startswith("provider_"):
                                    try:
                                        row_idx = int(key.replace("provider_", ""))
                                        provider_assignments[row_idx] = form_data.get(key)
                                    except ValueError:
                                        pass

                            # Create sessions with assigned providers
                            for i, row in enumerate(parsed_rows):
                                # Get provider from form assignment or fallback
                                assigned_provider_id = provider_assignments.get(i, "")
                                if not assigned_provider_id:
                                    assigned_provider_id = primary_provider_id or None

                                # Determine date
                                date = row.get("date") or event_date
                                if not date:
                                    continue

                                # Create the session
                                session = create_session(
                                    session_type=SessionType.SIMULATED,
                                    date=date,
                                    time=None,
                                    event_type="Simulated",
                                    primary_provider_id=assigned_provider_id or None,
                                    participant_ids=[assigned_provider_id] if assigned_provider_id else [],
                                )

                                # Build metrics from parsed data
                                metrics = {
                                    "duration": row.get("duration", 0),
                                    "compression_rate": row.get("compression_rate", 0),
                                    "compression_depth": row.get("compression_depth", 0),
                                    "correct_depth_percent": row.get("correct_depth_percent", 0),
                                    "correct_rate_percent": row.get("correct_rate_percent", 0),
                                }

                                # Mark session complete with metrics
                                update_session_status(
                                    session_id=session["id"],
                                    status=SessionStatus.COMPLETE,
                                    metrics=metrics,
                                )
                                session["status"] = SessionStatus.COMPLETE.value
                                session["metrics"] = metrics

                                created_sessions.append(session)

                    except Exception as e:
                        error_message = f"Error reading file: {e}"

            # If no sessions created from parsing, create a single session as fallback
            if not created_sessions and not error_message:
                session = service.create_simulated_session(
                    date=event_date,
                    time=event_time or None,
                    primary_provider_id=primary_provider_id or None,
                    participant_ids=participant_ids,
                )
                update_session_status(
                    session_id=session["id"],
                    status=SessionStatus.COMPLETE,
                    metrics={
                        "duration": 0,
                        "compression_rate": 0,
                        "correct_depth_percent": 0,
                        "correct_rate_percent": 0,
                    },
                )
                session["status"] = SessionStatus.COMPLETE.value
                created_sessions = [session]

            # Use first session for display in step 4
            session = created_sessions[0] if created_sessions else None

        # Get provider name for display
        primary_provider_name = None
        if primary_provider_id:
            provider = get_provider_by_id(primary_provider_id)
            if provider:
                primary_provider_name = provider["name"]

        # Go to step 4 (Complete)
        return request.app.state.templates.TemplateResponse(
            "partials/wizard/step_4.html",
            {
                "request": request,
                "step": 4,
                "session_id": session["id"] if session else "",
                "session_type": session_type,
                "session_status": session.get("status", "") if session else "",
                "event_date": event_date,
                "primary_provider_name": primary_provider_name,
                "error_message": error_message or (session.get("error_message") if session else None),
                "sessions_created": len(created_sessions),
            }
        )

    # Default - return step 1
    return request.app.state.templates.TemplateResponse(
        "partials/wizard/step_1.html",
        {"request": request, "step": 1, "teams": TEAMS, "providers": PROVIDERS}
    )


@router.post("/session/wizard/back/{step}", response_class=HTMLResponse)
async def wizard_back(request: Request, step: int):
    """Go back to a previous wizard step, preserving form data."""
    form_data = await request.form()

    session_type = form_data.get("session_type", "")
    event_date = form_data.get("event_date", "")
    event_time = form_data.get("event_time", "")

    return request.app.state.templates.TemplateResponse(
        f"partials/wizard/step_{step}.html",
        {
            "request": request,
            "step": step,
            "teams": TEAMS,
            "providers": PROVIDERS,
            "session_type": session_type,
            "event_date": event_date,
            "event_time": event_time,
        }
    )


# ============================================================================
# Report Generation
# ============================================================================

@router.post("/reports/generate", response_class=HTMLResponse)
async def generate_report(
    request: Request,
    report_type: str = Form("provider"),
    provider_id: str = Form(""),
    team_id: str = Form(""),
    date_range: str = Form("30d"),
    event_type: str = Form(""),
    include_summary: bool = Form(True),
    include_trends: bool = Form(True),
    include_sessions: bool = Form(True),
    include_comparison: bool = Form(False),
):
    """Generate a report preview."""
    from datetime import datetime

    # Date range labels
    date_range_labels = {
        "7d": "Last 7 Days",
        "30d": "Last 30 Days",
        "90d": "Last 90 Days",
        "year": "This Year",
        "all": "All Time",
    }
    date_range_label = date_range_labels.get(date_range, "Last 30 Days")

    if report_type == "provider":
        if not provider_id:
            # Return error state
            return HTMLResponse(
                content="""
                <div class="p-12 text-center">
                    <div class="text-red-500 mb-2">
                        <svg class="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                        </svg>
                    </div>
                    <h3 class="text-lg font-semibold text-slate-800">No Provider Selected</h3>
                    <p class="text-sm text-slate-500 mt-1">Please select a provider to generate the report</p>
                </div>
                """
            )

        provider = get_provider_by_id(provider_id)
        if not provider:
            return HTMLResponse(
                content="""
                <div class="p-12 text-center">
                    <h3 class="text-lg font-semibold text-slate-800">Provider Not Found</h3>
                </div>
                """
            )

        stats = get_provider_stats(provider_id)
        sessions = get_sessions_by_provider(provider_id)

        # Filter by event type if specified
        if event_type:
            sessions = [s for s in sessions if s.get("event_type") == event_type]

        # Sort sessions by date descending
        sessions = sorted(sessions, key=lambda s: s["date"], reverse=True)

        # Calculate department average for comparison
        department_avg = None
        if include_comparison:
            kpis = get_dashboard_kpis()
            department_avg = {
                "avg_jcls_score": kpis.get("avg_jcls_score"),
                "depth_compliance": kpis["avg_depth_compliance"],
                "rate_compliance": kpis["avg_rate_compliance"],
            }

        return request.app.state.templates.TemplateResponse(
            "partials/reports/provider_report.html",
            {
                "request": request,
                "provider": provider,
                "stats": stats,
                "sessions": sessions if include_sessions else [],
                "date_range_label": date_range_label,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "show_comparison": include_comparison,
                "department_avg": department_avg,
            }
        )

    # Default - not implemented yet
    return HTMLResponse(
        content="""
        <div class="p-12 text-center">
            <h3 class="text-lg font-semibold text-slate-800">Report Type Not Available</h3>
            <p class="text-sm text-slate-500 mt-1">Team and Department reports coming soon</p>
        </div>
        """
    )


# ============================================================================
# CanROC Completion Wizard Partials
# ============================================================================

@router.get("/canroc/{session_id}/{template_id}/wizard", response_class=HTMLResponse)
async def canroc_wizard_modal(request: Request, session_id: str, template_id: str):
    """Render full CanROC completion wizard modal."""
    from app.mock_data import get_session_by_id, update_session
    from app.models import Session, CanrocWizardState
    from app.services.schema_service import get_schema_service
    from app.services.wizard_service import get_wizard_service

    session_dict = get_session_by_id(session_id)
    if not session_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    if template_id not in ["master", "pco"]:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Invalid template</div>")

    # Get or initialize wizard state
    wizard_state_dict = session_dict.get(f"canroc_wizard_{template_id}")

    wizard_service = get_wizard_service()
    schema_service = get_schema_service()

    if not wizard_state_dict:
        # Initialize wizard
        session = Session(**session_dict)
        wizard_state = wizard_service.initialize_wizard(session, template_id)
        update_session(session_id, {f"canroc_wizard_{template_id}": wizard_state.model_dump()})
    else:
        wizard_state = CanrocWizardState(**wizard_state_dict)

    # Get summary for display
    summary = wizard_service.get_wizard_summary(wizard_state)

    # Get schema for template name
    schema = schema_service.load_schema(template_id)

    return request.app.state.templates.TemplateResponse(
        "partials/canroc_wizard/wizard_modal.html",
        {
            "request": request,
            "session_id": session_id,
            "template_id": template_id,
            "template_name": schema.get("template_name", template_id.upper()),
            "wizard_summary": summary,
            "current_page": wizard_state.current_page,
            "total_pages": wizard_state.total_pages,
        }
    )


@router.get("/canroc/{session_id}/{template_id}/page/{page_id}", response_class=HTMLResponse)
async def canroc_wizard_page(request: Request, session_id: str, template_id: str, page_id: int):
    """Render single wizard page content."""
    from app.mock_data import get_session_by_id
    from app.models import CanrocWizardState
    from app.services.schema_service import get_schema_service
    from app.services.wizard_service import get_wizard_service

    session_dict = get_session_by_id(session_id)
    if not session_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    wizard_state_dict = session_dict.get(f"canroc_wizard_{template_id}")
    if not wizard_state_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Wizard not initialized</div>")

    wizard_state = CanrocWizardState(**wizard_state_dict)
    schema_service = get_schema_service()
    wizard_service = get_wizard_service()

    # Get page schema
    page = schema_service.get_page(template_id, page_id)
    if not page:
        return HTMLResponse(f"<div class='p-4 text-center text-slate-500'>Page {page_id} not found</div>")

    # Get current field values as dict for dependency evaluation
    current_values = {fid: fv.value for fid, fv in wizard_state.field_values.items()}

    # Prepare fields with current values and visibility
    fields_with_values = []
    for field in page.get("fields", []):
        field_id = field["field_id"]
        field_value = wizard_state.field_values.get(field_id)

        should_show, is_required = schema_service.evaluate_dependencies(
            template_id, field_id, current_values
        )

        fields_with_values.append({
            **field,
            "current_value": field_value.value if field_value else None,
            "current_state": field_value.state.value if field_value else "empty",
            "provenance": field_value.provenance.value if field_value else None,
            "is_cno": field_value.state.value == "cno" if field_value else False,
            "should_show": should_show,
            "is_required": is_required,
        })

    # Get summary for progress display
    summary = wizard_service.get_wizard_summary(wizard_state)

    return request.app.state.templates.TemplateResponse(
        "partials/canroc_wizard/wizard_page.html",
        {
            "request": request,
            "session_id": session_id,
            "template_id": template_id,
            "page": page,
            "page_id": page_id,
            "fields": fields_with_values,
            "wizard_summary": summary,
            "total_pages": wizard_state.total_pages,
        }
    )


@router.post("/canroc/{session_id}/{template_id}/page/{page_id}/save", response_class=HTMLResponse)
async def canroc_save_page(request: Request, session_id: str, template_id: str, page_id: int):
    """Save wizard page and return next page or validation errors."""
    from app.mock_data import get_session_by_id, update_session
    from app.models import CanrocWizardState
    from app.services.schema_service import get_schema_service
    from app.services.wizard_service import get_wizard_service

    session_dict = get_session_by_id(session_id)
    if not session_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    wizard_state_dict = session_dict.get(f"canroc_wizard_{template_id}")
    if not wizard_state_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Wizard not initialized</div>")

    wizard_state = CanrocWizardState(**wizard_state_dict)
    schema_service = get_schema_service()
    wizard_service = get_wizard_service()

    # Get form data
    form_data = await request.form()

    # Build field values dict from form
    field_values = {}
    cno_fields = set()

    for key, value in form_data.items():
        if key.startswith("cno_"):
            # CNO checkbox
            field_id = key[4:]  # Remove "cno_" prefix
            if value == "1" or value == "on":
                cno_fields.add(field_id)
        elif key.startswith("field_"):
            # Field value
            field_id = key[6:]  # Remove "field_" prefix
            field_values[field_id] = value if value else None

    # Process CNO fields
    for field_id in cno_fields:
        if schema_service.is_cno_allowed(template_id, field_id):
            wizard_service.mark_field_cno(wizard_state, field_id)
            # Remove from field_values if present
            field_values.pop(field_id, None)

    # Save page
    errors = wizard_service.save_page(wizard_state, page_id, field_values)

    # Update current page
    wizard_state.current_page = page_id

    # Save to session
    update_session(session_id, {f"canroc_wizard_{template_id}": wizard_state.model_dump()})

    # If errors, re-render current page with errors
    if errors:
        page = schema_service.get_page(template_id, page_id)
        current_values = {fid: fv.value for fid, fv in wizard_state.field_values.items()}

        fields_with_values = []
        for field in page.get("fields", []):
            field_id = field["field_id"]
            field_value = wizard_state.field_values.get(field_id)
            should_show, is_required = schema_service.evaluate_dependencies(
                template_id, field_id, current_values
            )
            fields_with_values.append({
                **field,
                "current_value": field_value.value if field_value else None,
                "current_state": field_value.state.value if field_value else "empty",
                "provenance": field_value.provenance.value if field_value else None,
                "is_cno": field_value.state.value == "cno" if field_value else False,
                "should_show": should_show,
                "is_required": is_required,
            })

        summary = wizard_service.get_wizard_summary(wizard_state)

        return request.app.state.templates.TemplateResponse(
            "partials/canroc_wizard/wizard_page.html",
            {
                "request": request,
                "session_id": session_id,
                "template_id": template_id,
                "page": page,
                "page_id": page_id,
                "fields": fields_with_values,
                "wizard_summary": summary,
                "total_pages": wizard_state.total_pages,
                "errors": errors,
            }
        )

    # Success - check if this was the last page
    next_page_id = page_id + 1
    if next_page_id > wizard_state.total_pages:
        # Show completion/review page
        summary = wizard_service.get_wizard_summary(wizard_state)
        return request.app.state.templates.TemplateResponse(
            "partials/canroc_wizard/wizard_complete.html",
            {
                "request": request,
                "session_id": session_id,
                "template_id": template_id,
                "wizard_summary": summary,
                "can_complete": summary["can_complete"],
                "missing_required": summary["missing_required"],
            }
        )

    # Go to next page
    return await canroc_wizard_page(request, session_id, template_id, next_page_id)


@router.post("/canroc/{session_id}/{template_id}/complete", response_class=HTMLResponse)
async def canroc_complete_wizard(request: Request, session_id: str, template_id: str):
    """Complete the wizard and show success message."""
    from app.mock_data import get_session_by_id, update_session
    from app.models import CanrocWizardState
    from app.services.wizard_service import get_wizard_service

    session_dict = get_session_by_id(session_id)
    if not session_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Session not found</div>")

    wizard_state_dict = session_dict.get(f"canroc_wizard_{template_id}")
    if not wizard_state_dict:
        return HTMLResponse("<div class='p-4 text-center text-slate-500'>Wizard not initialized</div>")

    wizard_state = CanrocWizardState(**wizard_state_dict)
    wizard_service = get_wizard_service()

    success, errors = wizard_service.complete_wizard(wizard_state)

    if not success:
        # Show errors
        summary = wizard_service.get_wizard_summary(wizard_state)
        return request.app.state.templates.TemplateResponse(
            "partials/canroc_wizard/wizard_complete.html",
            {
                "request": request,
                "session_id": session_id,
                "template_id": template_id,
                "wizard_summary": summary,
                "can_complete": False,
                "missing_required": summary["missing_required"],
                "errors": errors,
            }
        )

    # Export to payload
    payload = wizard_service.export_to_payload(wizard_state)

    # Save wizard state and update payloads
    update_data = {
        f"canroc_wizard_{template_id}": wizard_state.model_dump(),
        f"canroc_{template_id}_payload": payload,
        f"canroc_{template_id}_complete": True,
    }
    update_session(session_id, update_data)

    # Show success message
    return HTMLResponse(f"""
        <div class="p-8 text-center">
            <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg class="w-8 h-8 text-[#16a34a]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
            </div>
            <h3 class="text-xl font-semibold text-slate-800 mb-2">Wizard Completed!</h3>
            <p class="text-sm text-slate-500 mb-6">
                {template_id.upper()} template data has been saved.<br>
                {len(payload)} fields populated.
            </p>
            <button onclick="document.getElementById('modal-container').innerHTML = ''; window.location.reload();"
                    class="px-6 py-2 bg-[#dc2626] text-white text-sm font-medium rounded-[6px] hover:bg-[#b91c1c] transition-colors">
                Done
            </button>
        </div>
    """)
