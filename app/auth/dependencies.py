"""Read-back dependency for the User the auth middleware already resolved.

The global middleware (ADR 0009) resolves the User once onto
``request.state.user``; this dependency hands it to a route so handlers stay
convention-shaped with no second database lookup.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.models.user import User


def current_user(request: Request) -> User:
    """Return the authenticated User, or 401 if the middleware set none.

    On a gated route the middleware has already rejected anonymous callers, so
    the 401 here is only a defensive backstop for a misconfigured public path.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


def current_admin(request: Request) -> User:
    """Return the authenticated User only if they are an admin, else 403.

    This is the gate on every account-management endpoint: a non-admin
    authenticated User is rejected with a machine-readable 403 (ADR 0007 — the
    admin role gates account management, not data).
    """
    user = current_user(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
        )
    return user
