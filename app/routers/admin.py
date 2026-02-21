"""
Admin router - consolidated admin area routes.
Handles admin authentication, dashboard, cross-service data,
test data management, and chart annotations.
"""
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter(prefix="/admin")


def _require_admin():
    """Check admin authentication. Returns error response if not authenticated, else None."""
    from app.services.admin_service import is_admin_authenticated
    if not is_admin_authenticated():
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    return None


# ============================================================================
# Admin Pages
# ============================================================================

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page."""
    return request.app.state.templates.TemplateResponse(
        "admin/login.html",
        {
            "request": request,
            "page_title": "Admin Login",
        }
    )


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard - cross-service comparison."""
    from app.services.admin_service import is_admin_authenticated, get_all_services_data, admin_needs_setup, load_annotations

    # If admin credentials not yet created, redirect to setup
    if admin_needs_setup():
        return RedirectResponse(url="/admin/login", status_code=302)

    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    services_data = get_all_services_data()
    annotations = load_annotations()
    return request.app.state.templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "page_title": "Admin Dashboard",
            "authenticated": True,
            "services_data": services_data,
            "annotations": annotations,
        }
    )


@router.get("/services", response_class=HTMLResponse)
async def admin_services(request: Request):
    """Service registry — list all services."""
    from app.services.admin_service import is_admin_authenticated, get_all_services_data
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)
    services_data = get_all_services_data()
    return request.app.state.templates.TemplateResponse(
        "admin/services.html",
        {"request": request, "page_title": "Services", "services_data": services_data}
    )


@router.get("/services/{slug}", response_class=HTMLResponse)
async def admin_service_detail(request: Request, slug: str):
    """Service detail — drill into a single service."""
    from app.services.admin_service import is_admin_authenticated, get_all_services_data
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)

    services_data = get_all_services_data()
    service = next((s for s in services_data if s["slug"] == slug), None)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    from app.services.activity_service import get_activity_log
    activity = get_activity_log(slug, limit=20)

    return request.app.state.templates.TemplateResponse(
        "admin/service_detail.html",
        {"request": request, "page_title": service["name"], "service": service, "activity": activity}
    )


@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(request: Request):
    """Cross-service analytics and comparison charts."""
    from app.services.admin_service import is_admin_authenticated, get_all_services_data, load_annotations
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)
    services_data = get_all_services_data()
    annotations = load_annotations()
    return request.app.state.templates.TemplateResponse(
        "admin/analytics.html",
        {"request": request, "page_title": "Analytics", "services_data": services_data, "annotations": annotations}
    )


@router.get("/tickets", response_class=HTMLResponse)
async def admin_tickets(request: Request):
    """Tickets page — GitHub Issues viewer."""
    from app.services.admin_service import is_admin_authenticated
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)
    from app.services.ticket_service import get_tickets
    tickets = get_tickets()
    return request.app.state.templates.TemplateResponse(
        "admin/tickets.html",
        {"request": request, "page_title": "Tickets", "tickets": tickets}
    )


@router.get("/data-tools", response_class=HTMLResponse)
async def admin_data_tools(request: Request):
    """Data Tools page - CSV provider upload."""
    from app.services.admin_service import is_admin_authenticated
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)
    from app.service_context import list_services
    services = list_services()
    return request.app.state.templates.TemplateResponse(
        "admin/data_tools.html",
        {"request": request, "page_title": "Data Tools", "services": services}
    )


@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Admin settings page."""
    from app.services.admin_service import is_admin_authenticated
    if not is_admin_authenticated():
        return RedirectResponse(url="/admin/login", status_code=302)
    return request.app.state.templates.TemplateResponse(
        "admin/settings.html",
        {"request": request, "page_title": "Settings"}
    )


# ============================================================================
# Admin Auth API
# ============================================================================

@router.post("/api/setup")
async def admin_setup(request: Request):
    """First-run admin password setup."""
    from app.services.admin_service import admin_needs_setup, setup_admin_credentials, set_admin_authenticated

    if not admin_needs_setup():
        return {"success": False, "error": "Admin already configured. Use login instead."}

    data = await request.json()
    password = str(data.get("password", ""))

    if len(password) < 8:
        return {"success": False, "error": "Password must be at least 8 characters"}

    if setup_admin_credentials(password):
        set_admin_authenticated(True)
        return {"success": True, "redirect": "/admin"}
    return {"success": False, "error": "Failed to create admin credentials"}


@router.get("/api/needs-setup")
async def admin_needs_setup_check():
    """Check if admin needs first-run setup."""
    from app.services.admin_service import admin_needs_setup
    return {"needs_setup": admin_needs_setup()}


@router.post("/api/login")
async def admin_login(request: Request):
    """Authenticate as admin."""
    import time
    from collections import defaultdict
    from app.services.admin_service import check_admin_password, set_admin_authenticated

    # Simple rate limiting for admin login
    if not hasattr(admin_login, '_attempts'):
        admin_login._attempts = []
    now = time.time()
    admin_login._attempts = [t for t in admin_login._attempts if now - t < 300]
    if len(admin_login._attempts) >= 10:
        return {"success": False, "error": "Too many login attempts. Please wait a few minutes."}
    admin_login._attempts.append(now)

    # Accept both JSON and form data
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        username = str(data.get("username", ""))
        password = str(data.get("password", ""))
    else:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))

    if check_admin_password(username, password):
        set_admin_authenticated(True)
        return {"success": True, "redirect": "/admin"}
    return {"success": False, "error": "Invalid admin credentials"}


@router.post("/api/logout")
async def admin_logout():
    """Log out admin."""
    from app.services.admin_service import set_admin_authenticated
    set_admin_authenticated(False)
    return {"success": True, "redirect": "/landing"}


@router.post("/api/change-password")
async def admin_change_password(request: Request):
    """Change admin password."""
    from app.services.admin_service import is_admin_authenticated, check_admin_password, get_admin_file
    if not is_admin_authenticated():
        raise HTTPException(status_code=401)

    data = await request.json()
    current_pw = data.get("current_password", "")
    new_pw = data.get("new_password", "")

    if not check_admin_password("Admin", current_pw):
        return {"success": False, "error": "Current password is incorrect"}
    if len(new_pw) < 8:
        return {"success": False, "error": "New password must be at least 8 characters"}

    from app.services.auth_service import hash_password
    import json
    admin_file = get_admin_file()
    admin_data = json.loads(admin_file.read_text(encoding="utf-8"))
    admin_data["password_hash"] = hash_password(new_pw)
    admin_file.write_text(json.dumps(admin_data, indent=2), encoding="utf-8")
    return {"success": True}


# ============================================================================
# Admin Services Data API
# ============================================================================

@router.get("/api/services-data")
async def admin_services_data():
    """Get cross-service data for admin dashboard."""
    err = _require_admin()
    if err:
        return err
    from app.services.admin_service import get_all_services_data
    data = get_all_services_data()
    return JSONResponse(content={"services": data})


# ============================================================================
# Test Data Endpoints
# ============================================================================

@router.post("/api/test-data/generate")
async def generate_test_data_endpoint():
    """Generate test fire department data."""
    err = _require_admin()
    if err:
        return err
    from app.services.test_data_service import generate_test_data
    result = generate_test_data()
    if result.get("success"):
        return JSONResponse(result)
    return JSONResponse(result, status_code=400)


@router.delete("/api/test-data/delete")
async def delete_test_data_endpoint():
    """Delete test fire department data."""
    err = _require_admin()
    if err:
        return err
    from app.services.test_data_service import delete_test_data
    result = delete_test_data()
    if result.get("success"):
        return JSONResponse(result)
    return JSONResponse(result, status_code=400)


# ============================================================================
# Annotation Endpoints (Event Markers for Trend Charts)
# ============================================================================

@router.get("/api/annotations")
async def list_annotations():
    """Get all event annotations."""
    err = _require_admin()
    if err:
        return err
    from app.services.admin_service import load_annotations
    return JSONResponse(content={"annotations": load_annotations()})


@router.post("/api/annotations")
async def create_annotation(request: Request):
    """Create an event annotation."""
    err = _require_admin()
    if err:
        return err
    from app.services.admin_service import add_annotation
    data = await request.json()
    month = str(data.get("month", "")).strip()
    label = str(data.get("label", "")).strip()
    description = str(data.get("description", "")).strip()
    color = str(data.get("color", "#dc2626")).strip()
    if not month or not label:
        return JSONResponse({"error": "Month and label are required"}, status_code=400)
    entry = add_annotation(month, label, description, color)
    return JSONResponse(content={"success": True, "annotation": entry})


@router.delete("/api/annotations/{annotation_id}")
async def remove_annotation(annotation_id: str):
    """Delete an event annotation."""
    err = _require_admin()
    if err:
        return err
    from app.services.admin_service import delete_annotation
    if delete_annotation(annotation_id):
        return JSONResponse(content={"success": True})
    return JSONResponse({"error": "Annotation not found"}, status_code=404)


# ============================================================================
# CSV Provider Upload
# ============================================================================

@router.post("/api/csv-upload")
async def admin_csv_upload(
    request: Request,
    service_slug: str = Form(...),
    csv_file: UploadFile = File(...),
):
    """Upload a CSV file of providers for a service."""
    err = _require_admin()
    if err:
        return err
    from app.services.csv_import_service import validate_provider_csv, parse_provider_csv, import_providers_to_service
    from app.services.activity_service import log_activity
    # Validate file extension
    if csv_file.filename and not csv_file.filename.lower().endswith(('.csv', '.txt')):
        return JSONResponse({"success": False, "errors": ["Only .csv and .txt files are accepted"]}, status_code=400)
    raw = await csv_file.read()
    if len(raw) > 5 * 1024 * 1024:  # 5MB limit
        return JSONResponse({"success": False, "errors": ["CSV file exceeds 5MB size limit"]}, status_code=400)
    content = raw.decode("utf-8")
    errors = validate_provider_csv(content)
    if errors:
        return JSONResponse({"success": False, "errors": errors}, status_code=400)
    providers = parse_provider_csv(content)
    if not providers:
        return JSONResponse({"success": False, "errors": ["No valid provider rows found"]}, status_code=400)
    result = import_providers_to_service(service_slug, providers)
    log_activity(service_slug, "provider_csv_upload", {"added": result["added"], "skipped": result["skipped"]})
    return {"success": True, "result": result}
