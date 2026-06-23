"""The single global, fail-closed authentication gate (ADR 0009).

Every request passes through here. A small public allowlist is served without a
session; everything else requires either a valid bearer PAT or an Onyx session
cookie, resolved once onto ``request.state.user``. Unauthenticated callers split
by client type: an ``/api`` or bearer request gets a machine-readable 401, an
HTML page request gets a 302 to ``/login?next=…``.

This is the deliberate exception to "no DB sessions outside the route layer":
the middleware opens a session (reusing the app's ``get_session`` seam, so tests
exercise the gate against their in-memory database) purely for the read-only
auth lookup plus a throttled ``last_seen`` touch.
"""

from __future__ import annotations

from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.auth import service as auth_service
from app.database import get_session

# Exact paths reachable without a session. Adding to this list serves that path
# unauthenticated, so it must change deliberately (ADR 0009).
PUBLIC_PATHS = frozenset(
    {"/login", "/auth/login", "/auth/callback", "/logout", "/healthz"}
)
# Prefixes reachable without a session (static assets).
PUBLIC_PREFIXES = ("/static",)


def _is_public(path: str) -> bool:
    """True when a path is served without requiring a session."""
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


def _bearer_token(request: Request) -> str | None:
    """Return the bearer token from Authorization, if the request presents one."""
    authorization = request.headers.get("authorization", "")
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


async def _resolve_user(request: Request):
    """Resolve bearer or session-cookie auth via the overridable session seam.

    Invoking ``get_session`` (or its test override) means the middleware reads
    the same database the routes do, so the in-memory test client exercises the
    real gate without a second wiring path.
    """
    bearer_token = _bearer_token(request)
    raw_token = request.cookies.get(auth_service.SESSION_COOKIE_NAME)
    if bearer_token is None and not raw_token:
        return None
    provider = request.app.dependency_overrides.get(get_session, get_session)
    session_gen = provider()
    session = await session_gen.__anext__()
    try:
        if bearer_token is not None:
            return await auth_service.resolve_api_token_user(session, bearer_token)
        return await auth_service.resolve_session_user(session, raw_token)
    finally:
        await session_gen.aclose()


class AuthMiddleware(BaseHTTPMiddleware):
    """Fail-closed gate: secure by default, public only by explicit allowlist."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path
        if _is_public(path):
            return await call_next(request)

        user = await _resolve_user(request)
        if user is None:
            return self._reject(request)

        request.state.user = user
        return await call_next(request)

    def _reject(self, request: Request) -> Response:
        """Reject anonymous access: 401 JSON for the API, 302 to login for pages."""
        if request.url.path.startswith("/api") or _bearer_token(request) is not None:
            return JSONResponse(
                {"detail": "Not authenticated"}, status_code=401
            )
        next_target = request.url.path
        if request.url.query:
            next_target = f"{next_target}?{request.url.query}"
        return RedirectResponse(
            f"/login?next={quote(next_target, safe='')}", status_code=302
        )
