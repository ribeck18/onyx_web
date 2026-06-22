from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.auth import service as auth_service
from app.models.session import Session
from app.models.user import User


async def make_user(
    session: AsyncSession,
    email: str = "user@onyx.test",
    entra_oid: str | None = "oid-user",
    is_active: bool = True,
    is_admin: bool = False,
) -> User:
    """Persist a User row for service-level tests."""
    user = User(
        entra_oid=entra_oid,
        email=email,
        is_active=is_active,
        is_admin=is_admin,
    )
    session.add(user)
    await session.flush()
    return user


async def make_session_row(
    session: AsyncSession,
    user: User,
    last_seen_at: datetime,
    expires_at: datetime,
) -> str:
    """Persist a Session with explicit timing and return its raw cookie token."""
    raw_token = auth_service.generate_token()
    row = Session(
        token_hash=auth_service.hash_token(raw_token),
        user_id=user.id,
        created_at=last_seen_at,
        expires_at=expires_at,
        last_seen_at=last_seen_at,
    )
    session.add(row)
    await session.flush()
    return raw_token


# --- token hashing & minting --------------------------------------------


def test_hash_token_is_deterministic_and_not_the_raw_value() -> None:
    """The same token always hashes the same way, and never to itself."""
    token = auth_service.generate_token()
    assert auth_service.hash_token(token) == auth_service.hash_token(token)
    assert auth_service.hash_token(token) != token


async def test_mint_session_stores_hash_and_caps_lifetime(
    session: AsyncSession,
) -> None:
    """Minting stores only the hash and sets a 7-day absolute cap."""
    user = await make_user(session)

    raw_token, row = await auth_service.mint_session(session, user)

    assert row.token_hash == auth_service.hash_token(raw_token)
    assert row.token_hash != raw_token
    lifetime = auth_service._as_utc(row.expires_at) - auth_service._as_utc(row.created_at)
    assert abs(lifetime - auth_service.SESSION_ABSOLUTE_CAP) < timedelta(seconds=5)


# --- session resolution & expiry ----------------------------------------


async def test_resolve_session_user_returns_active_user(
    session: AsyncSession,
) -> None:
    """A fresh, valid session resolves to its owning user."""
    user = await make_user(session)
    raw_token, _ = await auth_service.mint_session(session, user)

    resolved = await auth_service.resolve_session_user(session, raw_token)

    assert resolved is not None
    assert resolved.id == user.id


async def test_idle_session_expires_and_is_deleted(session: AsyncSession) -> None:
    """A session idle past the 8h window is rejected and removed."""
    user = await make_user(session)
    now = datetime.now(timezone.utc)
    raw_token = await make_session_row(
        session,
        user,
        last_seen_at=now - timedelta(hours=9),
        expires_at=now + timedelta(days=6),
    )

    resolved = await auth_service.resolve_session_user(session, raw_token)

    assert resolved is None
    remaining = await session.scalar(select(func.count()).select_from(Session))
    assert remaining == 0


async def test_session_past_absolute_cap_expires(session: AsyncSession) -> None:
    """A session past its 7-day absolute cap is rejected even if recently active."""
    user = await make_user(session)
    now = datetime.now(timezone.utc)
    raw_token = await make_session_row(
        session,
        user,
        last_seen_at=now - timedelta(minutes=1),
        expires_at=now - timedelta(seconds=1),
    )

    resolved = await auth_service.resolve_session_user(session, raw_token)

    assert resolved is None


async def test_active_session_slides_last_seen(session: AsyncSession) -> None:
    """Resolving an active-but-stale session refreshes last_seen (sliding idle)."""
    user = await make_user(session)
    now = datetime.now(timezone.utc)
    raw_token = await make_session_row(
        session,
        user,
        last_seen_at=now - timedelta(hours=2),
        expires_at=now + timedelta(days=6),
    )

    await auth_service.resolve_session_user(session, raw_token)

    row = await session.scalar(select(Session))
    assert auth_service._as_utc(row.last_seen_at) > now - timedelta(minutes=1)


async def test_deactivated_user_session_is_invalid(session: AsyncSession) -> None:
    """Deactivating a user immediately invalidates their existing session."""
    user = await make_user(session)
    raw_token, _ = await auth_service.mint_session(session, user)

    user.is_active = False
    await session.flush()

    assert await auth_service.resolve_session_user(session, raw_token) is None


async def test_delete_session_revokes_the_cookie(session: AsyncSession) -> None:
    """delete_session removes the row so the cookie no longer resolves."""
    user = await make_user(session)
    raw_token, _ = await auth_service.mint_session(session, user)

    await auth_service.delete_session(session, raw_token)

    assert await auth_service.resolve_session_user(session, raw_token) is None


# --- allowlist / provisioning / break-glass -----------------------------


async def test_resolve_login_binds_oid_on_first_login(session: AsyncSession) -> None:
    """A provisioned (email-only) row binds the Entra oid on first login."""
    await make_user(session, email="new@onyx.test", entra_oid=None)

    user = await auth_service.resolve_login(
        session, {"oid": "oid-new", "email": "new@onyx.test", "name": "New"}
    )

    assert user is not None
    assert user.entra_oid == "oid-new"


async def test_resolve_login_refuses_unprovisioned(session: AsyncSession) -> None:
    """An identity with no provisioned row and no break-glass is refused."""
    user = await auth_service.resolve_login(
        session, {"oid": "oid-x", "email": "stranger@nope.test", "name": "X"}
    )

    assert user is None


async def test_resolve_login_does_not_inherit_reassigned_email(
    session: AsyncSession,
) -> None:
    """An email already bound to one identity is never inherited by another."""
    await make_user(session, email="shared@onyx.test", entra_oid="oid-original")

    user = await auth_service.resolve_login(
        session, {"oid": "oid-different", "email": "shared@onyx.test", "name": "New Hire"}
    )

    assert user is None


async def test_resolve_login_break_glass_upserts_admin(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A break-glass email is created as an active admin when absent."""
    monkeypatch.setattr(config, "admin_emails", {"root@onyx.test"})

    user = await auth_service.resolve_login(
        session, {"oid": "oid-root", "email": "root@onyx.test", "name": "Root"}
    )

    assert user is not None
    assert user.is_admin is True
    assert user.is_active is True


async def test_resolve_login_break_glass_overrides_deactivation(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A break-glass admin can never be locked out, even if their row is inactive."""
    monkeypatch.setattr(config, "admin_emails", {"root@onyx.test"})
    await make_user(
        session, email="root@onyx.test", entra_oid="oid-root", is_active=False
    )

    user = await auth_service.resolve_login(
        session, {"oid": "oid-root", "email": "root@onyx.test", "name": "Root"}
    )

    assert user is not None
    assert user.is_active is True
    assert user.is_admin is True


async def test_resolve_login_refuses_deactivated_normal_user(
    session: AsyncSession,
) -> None:
    """A provisioned but deactivated user (not break-glass) is refused login."""
    await make_user(
        session, email="gone@onyx.test", entra_oid="oid-gone", is_active=False
    )

    user = await auth_service.resolve_login(
        session, {"oid": "oid-gone", "email": "gone@onyx.test", "name": "Gone"}
    )

    assert user is None
