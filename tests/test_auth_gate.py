from __future__ import annotations

from httpx import AsyncClient

from app.auth import service as auth_service


async def test_anonymous_page_request_redirects_to_login(
    anonymous_client: AsyncClient,
) -> None:
    """A protected page without a session 302s to /login carrying the next path."""
    response = await anonymous_client.get("/", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("/login?next=")


async def test_anonymous_page_request_preserves_path_and_query_in_next(
    anonymous_client: AsyncClient,
) -> None:
    """The original path (with query) is URL-encoded into ?next so login can return."""
    response = await anonymous_client.get(
        "/projects/7?tab=open", follow_redirects=False
    )

    assert response.status_code == 302
    # The whole original target is encoded as a single opaque next value.
    assert "next=%2Fprojects%2F7%3Ftab%3Dopen" in response.headers["location"]


async def test_anonymous_api_request_returns_401_not_redirect(
    anonymous_client: AsyncClient,
) -> None:
    """An unauthenticated /api request is a machine-readable 401, never a redirect."""
    response = await anonymous_client.get("/api/projects", follow_redirects=False)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_public_paths_reachable_without_session(
    anonymous_client: AsyncClient,
) -> None:
    """/login, /logout, /healthz and static are served without a session."""
    assert (await anonymous_client.get("/login")).status_code == 200
    assert (await anonymous_client.get("/healthz")).status_code == 200
    # /logout clears nothing here but must not be gated.
    logout = await anonymous_client.get("/logout", follow_redirects=False)
    assert logout.status_code == 302


async def test_healthz_payload(anonymous_client: AsyncClient) -> None:
    """The public liveness probe returns a simple ok body."""
    response = await anonymous_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_authenticated_client_reaches_protected_pages(
    client: AsyncClient,
) -> None:
    """The authenticated-by-default client passes the gate on a protected page."""
    response = await client.get("/")

    assert response.status_code == 200


async def test_invalid_session_cookie_is_rejected(
    anonymous_client: AsyncClient,
) -> None:
    """A cookie that matches no session row is treated as unauthenticated."""
    anonymous_client.cookies.set(auth_service.SESSION_COOKIE_NAME, "not-a-real-token")
    response = await anonymous_client.get("/api/projects", follow_redirects=False)

    assert response.status_code == 401
