from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.auth import entra
from app.auth import service as auth_service
from app.models.session import Session
from app.models.user import User


def patch_claims(monkeypatch: pytest.MonkeyPatch, **claims: str) -> None:
    """Make the identity seam return fixed validated claims (no Microsoft call)."""

    async def fake_exchange(request) -> dict[str, str]:
        return {"oid": "", "email": "", "name": "", **claims}

    monkeypatch.setattr(entra, "exchange_code_for_claims", fake_exchange)


async def provision(session: AsyncSession, email: str) -> User:
    """Provision a User by email with no Entra binding yet (the pre-login state)."""
    user = User(entra_oid=None, email=email, is_active=True)
    session.add(user)
    await session.flush()
    return user


async def test_provisioned_user_signs_in_and_binds_oid(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provisioned identity completes the callback, gets a session, binds its oid."""
    user = await provision(session, "alice@onyx.test")
    patch_claims(monkeypatch, oid="oid-alice", email="alice@onyx.test", name="Alice")

    response = await anonymous_client.get("/auth/callback", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert auth_service.SESSION_COOKIE_NAME in response.cookies
    assert user.entra_oid == "oid-alice"  # bound on first login
    assert user.last_login_at is not None
    session_count = await session.scalar(select(func.count()).select_from(Session))
    assert session_count == 1


async def test_bound_oid_is_reused_on_second_login(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A returning user matches by oid even if their email later changes."""
    await provision(session, "bob@onyx.test")
    patch_claims(monkeypatch, oid="oid-bob", email="bob@onyx.test", name="Bob")
    await anonymous_client.get("/auth/callback", follow_redirects=False)

    # Same oid, different email — must match the existing row, not refuse it.
    patch_claims(monkeypatch, oid="oid-bob", email="bob.renamed@onyx.test", name="Bob")
    response = await anonymous_client.get("/auth/callback", follow_redirects=False)

    assert response.status_code == 302
    user_count = await session.scalar(select(func.count()).select_from(User))
    assert user_count == 1


async def test_unprovisioned_identity_is_refused(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An authenticated identity with no provisioned row gets the denied page, no session."""
    patch_claims(
        monkeypatch, oid="oid-stranger", email="stranger@outside.test", name="Stranger"
    )

    response = await anonymous_client.get("/auth/callback", follow_redirects=False)

    assert response.status_code == 403
    assert "don't have an Onyx account" in response.text
    assert auth_service.SESSION_COOKIE_NAME not in response.cookies
    session_count = await session.scalar(select(func.count()).select_from(Session))
    assert session_count == 0


async def test_break_glass_email_signs_in_as_admin_with_no_row(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ONYX_ADMIN_EMAILS address is admitted as admin even when no row exists."""
    monkeypatch.setattr(config, "admin_emails", {"boss@onyx.test"})
    patch_claims(monkeypatch, oid="oid-boss", email="boss@onyx.test", name="Boss")

    response = await anonymous_client.get("/auth/callback", follow_redirects=False)

    assert response.status_code == 302
    created = await session.scalar(
        select(User).where(User.email == "boss@onyx.test")
    )
    assert created is not None
    assert created.is_admin is True
    assert created.is_active is True
    assert created.entra_oid == "oid-boss"


async def test_callback_cookie_is_httponly_and_lax(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The minted session cookie is httponly and samesite=lax."""
    await provision(session, "carol@onyx.test")
    patch_claims(monkeypatch, oid="oid-carol", email="carol@onyx.test", name="Carol")

    response = await anonymous_client.get("/auth/callback", follow_redirects=False)

    set_cookie = response.headers["set-cookie"].lower()
    assert auth_service.SESSION_COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    # secure is off by default (local http dev) so the cookie works without TLS.
    assert "secure" not in set_cookie


async def test_callback_cookie_is_secure_when_configured(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With COOKIE_SECURE on, the session cookie is marked Secure."""
    monkeypatch.setattr(config, "cookie_secure", True)
    await provision(session, "dave@onyx.test")
    patch_claims(monkeypatch, oid="oid-dave", email="dave@onyx.test", name="Dave")

    response = await anonymous_client.get("/auth/callback", follow_redirects=False)

    assert "secure" in response.headers["set-cookie"].lower()


async def test_only_token_hash_is_stored_never_the_raw_token(
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stored session row holds the hash of the cookie value, not the value."""
    await provision(session, "erin@onyx.test")
    patch_claims(monkeypatch, oid="oid-erin", email="erin@onyx.test", name="Erin")

    response = await anonymous_client.get("/auth/callback", follow_redirects=False)
    raw_token = response.cookies[auth_service.SESSION_COOKIE_NAME]

    row = await session.scalar(select(Session))
    assert row.token_hash != raw_token
    assert row.token_hash == auth_service.hash_token(raw_token)
