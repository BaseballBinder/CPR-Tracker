"""
Admin router - consolidated admin area routes.
Handles admin authentication, dashboard, cross-service data,
test data management, and chart annotations.
"""
from fastapi import APIRouter, Request
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
    from app.services.admin_service import is_admin_authenticated, get_all_services_data, ensure_admin_credentials, load_annotations
    ensure_admin_credentials()

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


# ============================================================================
# Admin Auth API
# ============================================================================

@router.post("/api/login")
async def admin_login(request: Request):
    """Authenticate as admin."""
    from app.services.admin_service import check_admin_password, set_admin_authenticated

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
