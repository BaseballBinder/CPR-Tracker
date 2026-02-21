"""
CPR Tracking System - FastAPI Entry Point
Run with: uvicorn app.main:app --reload
"""
import logging

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.desktop_config import get_bundle_dir
from app.version import __version__
from app.routers import pages, partials, api, admin
from app.services.export_service import ensure_templates
from app.services.schema_service import get_schema_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get base directory (works in both dev and PyInstaller frozen mode)
BASE_DIR = get_bundle_dir()

# Create FastAPI app
app = FastAPI(
    title="CPR Tracking System",
    description="High-efficiency CPR performance tracking for fire departments",
    version=__version__
)

# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Auth middleware — redirects to /landing if no service is active
from app.middleware.auth import AuthMiddleware
app.add_middleware(AuthMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Add service name helper as a Jinja2 global so topbar can show it
from app.service_context import get_active_service_name
templates.env.globals["get_service_name"] = get_active_service_name

# Store templates in app state for access in routes
app.state.templates = templates

# Health check endpoint
@app.get("/__health", response_class=PlainTextResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return "OK"


# Ensure CanROC templates exist on startup
ensure_templates()

# Ensure admin credentials exist on startup
from app.services.admin_service import ensure_admin_credentials
ensure_admin_credentials()

# Validate CanROC schemas against Excel templates on startup
def validate_schemas_on_startup():
    """Validate all CanROC schemas against their Excel templates."""
    logger.info("Validating CanROC schemas against Excel templates...")
    schema_service = get_schema_service()
    results = schema_service.validate_all_schemas()

    has_critical_errors = False
    for template_id, warnings in results.items():
        if warnings:
            for warning in warnings:
                if "CRITICAL" in warning or "MISSING" in warning:
                    logger.error(f"[Schema:{template_id}] {warning}")
                    has_critical_errors = True
                else:
                    logger.warning(f"[Schema:{template_id}] {warning}")
        else:
            logger.info(f"[Schema:{template_id}] Validation passed")

    if has_critical_errors:
        logger.error("Critical schema validation errors detected. Some wizard fields may not export correctly.")
    else:
        logger.info("All CanROC schemas validated successfully")

validate_schemas_on_startup()

# Include routers
app.include_router(pages.router)
app.include_router(partials.router)
app.include_router(api.router)
app.include_router(admin.router)
