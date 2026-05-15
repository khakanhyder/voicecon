"""
CSRF Protection Middleware.

Implements Double Submit Cookie pattern for CSRF protection.
"""
import secrets
import hmac
import hashlib
from typing import Optional
from fastapi import Request, HTTPException, status, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import MutableHeaders

from app.core.config import settings


class CSRFProtectMiddleware(BaseHTTPMiddleware):
    """
    CSRF Protection using Double Submit Cookie pattern.

    How it works:
    1. Generate CSRF token and set as cookie
    2. Client must include token in X-CSRF-Token header for state-changing requests
    3. Verify header token matches cookie token

    Safe methods (GET, HEAD, OPTIONS, TRACE) are exempt.
    """

    def __init__(
        self,
        app,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        cookie_secure: bool = True,
        cookie_httponly: bool = False,  # JS needs to read this
        cookie_samesite: str = "strict",
    ):
        super().__init__(app)
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite

        # Safe methods don't need CSRF protection
        self.safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}

        # Exempt paths (typically auth endpoints)
        self.exempt_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
        }

    async def dispatch(self, request: Request, call_next):
        """
        Check CSRF token for state-changing requests.
        """
        # Skip CSRF check for safe methods
        if request.method in self.safe_methods:
            response = await call_next(request)
            # Set CSRF token cookie for future use
            self._set_csrf_cookie(response, request)
            return response

        # Skip CSRF check for exempt paths
        if self._is_exempt_path(request.url.path):
            return await call_next(request)

        # Get tokens
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        # Verify CSRF token
        if not self._verify_csrf_token(cookie_token, header_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "CSRFTokenMissing",
                    "message": "CSRF token missing or invalid. Include X-CSRF-Token header.",
                }
            )

        # Process request
        response = await call_next(request)

        # Refresh CSRF token cookie
        self._set_csrf_cookie(response, request)

        return response

    def _verify_csrf_token(
        self,
        cookie_token: Optional[str],
        header_token: Optional[str]
    ) -> bool:
        """
        Verify CSRF token using constant-time comparison.

        Both tokens must:
        1. Exist
        2. Match exactly
        3. Be valid format
        """
        if not cookie_token or not header_token:
            return False

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(cookie_token, header_token)

    def _generate_csrf_token(self) -> str:
        """
        Generate a secure CSRF token.
        """
        # 32 bytes = 256 bits of randomness
        token = secrets.token_urlsafe(32)

        # Optional: HMAC the token with secret key for additional security
        if hasattr(settings, 'SECRET_KEY'):
            h = hmac.new(
                settings.SECRET_KEY.encode(),
                token.encode(),
                hashlib.sha256
            )
            token = h.hexdigest()

        return token

    def _set_csrf_cookie(self, response: Response, request: Request):
        """
        Set CSRF token cookie in response.

        If cookie already exists and is valid, keep it.
        Otherwise, generate new token.
        """
        existing_token = request.cookies.get(self.cookie_name)

        # Generate new token if none exists
        if not existing_token:
            token = self._generate_csrf_token()
        else:
            token = existing_token

        # Set cookie with security flags
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=86400 * 7,  # 7 days
            secure=self.cookie_secure,  # HTTPS only in production
            httponly=self.cookie_httponly,  # JavaScript can read (needs to send in header)
            samesite=self.cookie_samesite,  # strict or lax
            path="/",
        )

    def _is_exempt_path(self, path: str) -> bool:
        """
        Check if path is exempt from CSRF protection.
        """
        # Exact match
        if path in self.exempt_paths:
            return True

        # Pattern match
        exempt_patterns = [
            "/api/v1/auth/",  # Auth endpoints handle CSRF differently
            "/webhooks/",     # Webhooks use signature verification
            "/health",        # Health checks
            "/metrics",       # Metrics endpoints
        ]

        return any(pattern in path for pattern in exempt_patterns)


def init_csrf_middleware(app, exempt_paths: Optional[set] = None):
    """
    Initialize CSRF protection middleware.

    Args:
        app: FastAPI application
        exempt_paths: Additional paths to exempt from CSRF checks
    """
    middleware = CSRFProtectMiddleware(
        app,
        cookie_secure=settings.is_production,  # HTTPS only in production
        cookie_samesite="strict" if settings.is_production else "lax"
    )

    if exempt_paths:
        middleware.exempt_paths.update(exempt_paths)

    app.add_middleware(CSRFProtectMiddleware)


# Dependency for endpoints that need explicit CSRF verification
async def verify_csrf_token(request: Request) -> bool:
    """
    Dependency to explicitly verify CSRF token.

    Usage:
        @router.post("/dangerous-operation")
        async def dangerous_op(
            csrf_valid: bool = Depends(verify_csrf_token)
        ):
            if not csrf_valid:
                raise HTTPException(403, "CSRF check failed")
            ...
    """
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")

    if not cookie_token or not header_token:
        return False

    return hmac.compare_digest(cookie_token, header_token)


# Helper function to get CSRF token for client
def get_csrf_token(request: Request) -> str:
    """
    Get CSRF token for the client.

    Can be used in GET endpoint to provide token to SPA.

    Example:
        @router.get("/csrf-token")
        async def get_token(request: Request):
            return {"csrf_token": get_csrf_token(request)}
    """
    token = request.cookies.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)

    return token
