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
