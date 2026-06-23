from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.models.session import Session


async def test_logout_redirects_to_login_and_clears_cookie(
    browser_client: AsyncClient,
) -> None:
    """Logout 302s to /login and expires the session cookie."""
    response = await browser_client.get("/logout", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    set_cookie = response.headers["set-cookie"].lower()
    assert auth_service.SESSION_COOKIE_NAME in set_cookie
    # An expiring cookie carries a past/zeroed lifetime.
    assert "expires=" in set_cookie or "max-age=0" in set_cookie


async def test_logout_deletes_the_session_row(
    browser_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Logout removes the server-side session, so the cookie can't be reused."""
    assert await session.scalar(select(func.count()).select_from(Session)) == 1

    await browser_client.get("/logout", follow_redirects=False)

    assert await session.scalar(select(func.count()).select_from(Session)) == 0


async def test_after_logout_protected_pages_require_login(
    browser_client: AsyncClient,
) -> None:
    """Once logged out, the same client is anonymous again at the gate."""
    await browser_client.get("/logout", follow_redirects=False)

    response = await browser_client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")
