"""
UI page routes - full page renders.
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.mock_data import (
    PROVIDERS, TEAMS, SESSIONS, DATE_RANGE_PRESETS,
    get_provider_by_id, get_team_by_id, get_sessions_by_provider,
    get_dashboard_kpis, get_top_performers, get_provider_stats, get_ranked_providers,
    get_real_call_teams, get_ranked_providers_by_type
)


def serialize_for_json(obj: Any) -> Any:
    """Recursively convert datetime objects to ISO format strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj

router = APIRouter()


@router.get("/landing", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page - service selector and password entry."""
    from app.service_context import list_services
    from app.version import __version__
    services = list_services()
    return request.app.state.templates.TemplateResponse(
        "pages/landing.html",
        {
            "request": request,
            "page_title": "Welcome",
            "services": services,
            "version": __version__,
        }
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page - KPIs, trends, recent sessions."""
    return request.app.state.templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "page_title": "Dashboard",
            "kpis": get_dashboard_kpis(),
            "recent_sessions": sorted(SESSIONS, key=lambda x: x["date"], reverse=True)[:5],
            "top_performers": get_top_performers(3),
            "top_performers_real": get_ranked_providers_by_type("real_call")[:3],
            "top_performers_simulated": get_ranked_providers_by_type("simulated")[:3],
            "date_presets": DATE_RANGE_PRESETS,
        }
    )


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request):
    """Sessions list page."""
    # Sort sessions by date descending (most recent first)
    sorted_sessions = sorted(SESSIONS, key=lambda s: s.get("date", ""), reverse=True)

    return request.app.state.templates.TemplateResponse(
        "pages/sessions.html",
        {
            "request": request,
            "page_title": "Sessions",
            "sessions": sorted_sessions,
            "teams": TEAMS,
            "providers": PROVIDERS,
            "date_presets": DATE_RANGE_PRESETS,
        }
    )


@router.get("/providers", response_class=HTMLResponse)
async def providers_list(request: Request):
    """Providers list page."""
    # Enrich providers with their stats
    providers_with_stats = []
    for provider in PROVIDERS:
        stats = get_provider_stats(provider["id"])
        sessions = get_sessions_by_provider(provider["id"])
        last_session = max(sessions, key=lambda s: s["date"]) if sessions else None
        providers_with_stats.append({
            **provider,
            "stats": stats,
            "last_session_date": last_session["date"] if last_session else None,
        })

    # Sort providers alphabetically by name
    providers_with_stats.sort(key=lambda p: p.get("name", "").lower())

    return request.app.state.templates.TemplateResponse(
        "pages/providers.html",
        {
            "request": request,
            "page_title": "Providers",
            "providers": providers_with_stats,
            "teams": TEAMS,
            "date_presets": DATE_RANGE_PRESETS,
        }
    )


@router.get("/providers/{provider_id}", response_class=HTMLResponse)
async def provider_detail(request: Request, provider_id: str):
    """Provider detail page."""
    provider = get_provider_by_id(provider_id)
    if not provider:
        # Return 404 page or redirect
        return request.app.state.templates.TemplateResponse(
            "pages/providers.html",
            {
                "request": request,
                "page_title": "Provider Not Found",
                "providers": PROVIDERS,
                "teams": TEAMS,
                "error": "Provider not found",
                "date_presets": DATE_RANGE_PRESETS,
            }
        )

    from app.mock_data import get_provider_stats_detailed

    team = get_team_by_id(provider["team_id"])
    sessions = get_sessions_by_provider(provider_id)
    stats = get_provider_stats(provider_id)  # Keep for backward compatibility
    detailed_stats = get_provider_stats_detailed(provider_id)

    # Sort sessions by date descending
    sessions = sorted(sessions, key=lambda s: s.get("date", ""), reverse=True)

    return request.app.state.templates.TemplateResponse(
        "pages/provider_detail.html",
        {
            "request": request,
            "page_title": provider["name"],
            "provider": provider,
            "team": team,
            "sessions": sessions,
            "stats": stats,
            "detailed_stats": detailed_stats,
            "date_presets": DATE_RANGE_PRESETS,
        }
    )


@router.get("/rankings", response_class=HTMLResponse)
async def rankings(request: Request):
    """Rankings page - provider and team rankings."""
    return request.app.state.templates.TemplateResponse(
        "pages/rankings.html",
        {
            "request": request,
            "page_title": "Rankings",
            "ranked_providers": get_ranked_providers(),
            "ranked_providers_simulated": get_ranked_providers_by_type("simulated"),
            "ranked_providers_real": get_ranked_providers_by_type("real_call"),
            "real_call_teams": get_real_call_teams(),
            "date_presets": DATE_RANGE_PRESETS,
        }
    )


@router.get("/teams", response_class=HTMLResponse)
async def team_analysis(request: Request, sort_by: str = "jcls_score"):
    """Team analysis page - shows ranked team instances from real calls."""
    # Get ranked team instances (each real call = one team)
    team_instances = get_real_call_teams(sort_by=sort_by)

    # Calculate summary stats
    total_teams = len(team_instances)
    avg_jcls = 0
    avg_ccf = 0
    best_team = None
    max_compressions = 0
    top_compressions_team = None

    if team_instances:
        jcls_scores = [t["jcls_score"] for t in team_instances if t.get("jcls_score")]
        ccf_scores = [t["ccf"] for t in team_instances if t["ccf"]]
        avg_jcls = round(sum(jcls_scores) / len(jcls_scores), 1) if jcls_scores else 0
        avg_ccf = round(sum(ccf_scores) / len(ccf_scores), 1) if ccf_scores else 0

        # Get best team by jcls_score (regardless of current sort)
        best_team_list = get_real_call_teams(sort_by="jcls_score")
        best_team = best_team_list[0] if best_team_list else None

        # Find team with most compressions (fun stat)
        for t in team_instances:
            if t["total_compressions"] and t["total_compressions"] > max_compressions:
                max_compressions = t["total_compressions"]
                top_compressions_team = t

    # Prepare trend data sorted by date (oldest to newest)
    trend_data = get_real_call_teams(sort_by="date")
    # Sort chronologically (oldest first for proper chart display)
    trend_data_sorted = sorted(trend_data, key=lambda t: t.get("date", ""))

    # Build chart data
    chart_labels = [t.get("date", "") for t in trend_data_sorted]
    chart_ccf = [t.get("ccf", 0) for t in trend_data_sorted]
    chart_jcls = [t.get("jcls_score") or 0 for t in trend_data_sorted]
    chart_depth = [t.get("depth_compliance", 0) for t in trend_data_sorted]
    chart_rate = [t.get("rate_compliance", 0) for t in trend_data_sorted]

    return request.app.state.templates.TemplateResponse(
        "pages/team_analysis.html",
        {
            "request": request,
            "page_title": "Team Analysis",
            "team_instances": team_instances,
            "total_teams": total_teams,
            "avg_jcls": avg_jcls,
            "avg_ccf": avg_ccf,
            "best_team": best_team,
            "max_compressions": max_compressions,
            "top_compressions_team": top_compressions_team,
            "current_sort": sort_by,
            "date_presets": DATE_RANGE_PRESETS,
            # Trend chart data
            "chart_labels": chart_labels,
            "chart_ccf": chart_ccf,
            "chart_jcls": chart_jcls,
            "chart_depth": chart_depth,
            "chart_rate": chart_rate,
        }
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    """CPR Reports page."""
    # Get real call sessions for team report selection
    real_call_sessions = [s for s in SESSIONS if s.get("session_type") == "real_call"]
    # Sort by date descending (most recent first)
    real_call_sessions = sorted(real_call_sessions, key=lambda s: s.get("date", ""), reverse=True)

    # Serialize datetime objects to ISO strings for JSON serialization in template
    real_call_sessions_serialized = serialize_for_json(real_call_sessions)

    return request.app.state.templates.TemplateResponse(
        "pages/reports.html",
        {
            "request": request,
            "page_title": "CPR Reports",
            "providers": PROVIDERS,
            "teams": TEAMS,
            "date_presets": DATE_RANGE_PRESETS,
            "real_call_sessions": real_call_sessions_serialized,
        }
    )


@router.get("/import-export", response_class=HTMLResponse)
async def import_export(request: Request):
    """Import/Export page."""
    return request.app.state.templates.TemplateResponse(
        "pages/import_export.html",
        {
            "request": request,
            "page_title": "Import / Export",
            "date_presets": DATE_RANGE_PRESETS,
        }
    )


@router.get("/canroc", response_class=HTMLResponse)
async def canroc(request: Request):
    """CanROC data management page - view and export PCO/Master data."""
    from app.services.export_service import get_export_service
    from app.services.wizard_service import get_wizard_service
    from app.models import CanrocWizardState, WizardCompletionStatus

    export_service = get_export_service()
    wizard_service = get_wizard_service()

    # Get template availability
    templates_status = export_service.get_available_templates()

    # Get sessions that have CanROC data (real_call sessions with complete status)
    canroc_sessions = [
        s for s in SESSIONS
        if s.get("session_type") == "real_call" and s.get("status") == "complete"
    ]

    # Enrich sessions with wizard status
    for session in canroc_sessions:
        # PCO wizard status
        pco_wizard_dict = session.get("canroc_wizard_pco")
        if pco_wizard_dict:
            pco_wizard = CanrocWizardState(**pco_wizard_dict)
            pco_summary = wizard_service.get_wizard_summary(pco_wizard)
            session["pco_wizard_status"] = pco_wizard.status.value
            session["pco_wizard_percent"] = pco_summary["completion_percent"]
            session["pco_wizard_complete"] = pco_wizard.status == WizardCompletionStatus.COMPLETE
        else:
            session["pco_wizard_status"] = "not_started"
            session["pco_wizard_percent"] = 0
            session["pco_wizard_complete"] = False

        # Master wizard status
        master_wizard_dict = session.get("canroc_wizard_master")
        if master_wizard_dict:
            master_wizard = CanrocWizardState(**master_wizard_dict)
            master_summary = wizard_service.get_wizard_summary(master_wizard)
            session["master_wizard_status"] = master_wizard.status.value
            session["master_wizard_percent"] = master_summary["completion_percent"]
            session["master_wizard_complete"] = master_wizard.status == WizardCompletionStatus.COMPLETE
        else:
            session["master_wizard_status"] = "not_started"
            session["master_wizard_percent"] = 0
            session["master_wizard_complete"] = False

    # Sort by date descending
    canroc_sessions = sorted(canroc_sessions, key=lambda s: s.get("date", ""), reverse=True)

    # Get list of existing exports from exports directory
    exports_dir = export_service.settings.export_output_dir
    existing_exports = []
    if exports_dir.exists():
        for f in exports_dir.glob("CanROC_*.xlsx"):
            existing_exports.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
                "type": "PCO" if "_PCO_" in f.name else "Master",
            })
    # Sort by modified time descending (most recent first)
    existing_exports = sorted(existing_exports, key=lambda x: x["modified"], reverse=True)

    # Count sessions for bulk export
    total_sessions = len(canroc_sessions)
    pco_complete = sum(1 for s in canroc_sessions if s.get("pco_wizard_complete"))
    master_complete = sum(1 for s in canroc_sessions if s.get("master_wizard_complete"))

    return request.app.state.templates.TemplateResponse(
        "pages/canroc.html",
        {
            "request": request,
            "page_title": "CanROC Export",
            "templates_status": templates_status,
            "canroc_sessions": canroc_sessions,
            "existing_exports": existing_exports,
            "date_presets": DATE_RANGE_PRESETS,
            "total_sessions": total_sessions,
            "pco_complete_count": pco_complete,
            "master_complete_count": master_complete,
        }
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Settings page."""
    from app.services.settings_service import load_settings
    current_settings = load_settings()
    return request.app.state.templates.TemplateResponse(
        "pages/settings.html",
        {
            "request": request,
            "page_title": "Settings",
            "teams": TEAMS,
            "providers": PROVIDERS,
            "settings": current_settings,
        }
    )


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Help / How-To page."""
    return request.app.state.templates.TemplateResponse(
        "pages/help.html",
        {
            "request": request,
            "page_title": "Help & How-To",
        }
    )
