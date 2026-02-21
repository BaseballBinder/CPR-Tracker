"""
Authentication middleware for the desktop app.
Redirects unauthenticated requests to the landing page.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.service_context import get_active_service


# Routes that don't require authentication
PUBLIC_PATHS = {
    "/landing",
    "/__health",
    "/api/updates/check",
    "/api/updates/download-stream",
    "/api/updates/apply",
    "/api/updates/shutdown",
}

PUBLIC_PREFIXES = (
    "/static/",
    "/api/auth/",
    "/admin",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Allow public routes
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        # Check if a service is active (user has logged in)
        if get_active_service() is None:
            return RedirectResponse(url="/landing", status_code=302)

        return await call_next(request)
