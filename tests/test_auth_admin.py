from __future__ import annotations

from datetime import datetime, timezone

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


# --- provisioning + first login -----------------------------------------


async def test_provision_lets_user_complete_first_login(
    admin_client: AsyncClient,
    anonymous_client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An admin provisions by email; that person then signs in and binds their oid."""
    created = await admin_client.post("/api/users", json={"email": "newhire@onyx.test"})
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "newhire@onyx.test"
    assert body["is_active"] is True
    assert body["has_logged_in"] is False

    patch_claims(
        monkeypatch, oid="oid-newhire", email="newhire@onyx.test", name="New Hire"
    )
    callback = await anonymous_client.get("/auth/callback", follow_redirects=False)

    assert callback.status_code == 302
    bound = await session.scalar(
        select(User).where(User.email == "newhire@onyx.test")
    )
    assert bound.entra_oid == "oid-newhire"


async def test_provision_duplicate_email_is_409(
    admin_client: AsyncClient,
) -> None:
    """Provisioning an email that already exists is a 409, case-insensitive."""
    await admin_client.post("/api/users", json={"email": "dupe@onyx.test"})

    again = await admin_client.post("/api/users", json={"email": "DUPE@onyx.test"})

    assert again.status_code == 409


# --- listing + status ----------------------------------------------------


async def test_list_reports_active_admin_and_login_status(
    admin_client: AsyncClient,
) -> None:
    """The list exposes active / admin / has-logged-in for each user."""
    await admin_client.post(
        "/api/users", json={"email": "pending@onyx.test"}
    )

    listing = await admin_client.get("/api/users")

    assert listing.status_code == 200
    by_email = {row["email"]: row for row in listing.json()}
    # The admin running the request has logged in (the fixture minted a session
    # for an already-bound user); the freshly provisioned user has not.
    assert by_email["admin@onyx.test"]["is_admin"] is True
    pending = by_email["pending@onyx.test"]
    assert pending["is_active"] is True
    assert pending["is_admin"] is False
    assert pending["has_logged_in"] is False


# --- deactivation revokes sessions immediately ---------------------------


async def test_deactivation_immediately_bounces_active_session(
    admin_client: AsyncClient,
    anonymous_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Deactivating a user invalidates their live session on the next request."""
    provisioned = await admin_client.post(
        "/api/users", json={"email": "active@onyx.test"}
    )
    user_id = provisioned.json()["id"]
    # Bind + mint a live session for that user, the way a real login would.
    user = await session.get(User, user_id)
    user.entra_oid = "oid-active"
    raw_token, _ = await auth_service.mint_session(session, user)
    await session.commit()

    anonymous_client.cookies.set(auth_service.SESSION_COOKIE_NAME, raw_token)
    assert (await anonymous_client.get("/api/projects")).status_code == 200

    deactivate = await admin_client.post(f"/api/users/{user_id}/deactivate")
    assert deactivate.status_code == 200

    bounced = await anonymous_client.get("/api/projects", follow_redirects=False)
    assert bounced.status_code == 401
    remaining = await session.scalar(
        select(func.count())
        .select_from(Session)
        .where(Session.user_id == user_id)
    )
    assert remaining == 0


async def test_reactivate_restores_access(
    admin_client: AsyncClient,
) -> None:
    """A deactivated user can be reactivated."""
    created = await admin_client.post(
        "/api/users", json={"email": "back@onyx.test"}
    )
    user_id = created.json()["id"]
    await admin_client.post(f"/api/users/{user_id}/deactivate")

    reactivate = await admin_client.post(f"/api/users/{user_id}/reactivate")

    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True


# --- promote / demote ----------------------------------------------------


async def test_promote_then_demote(
    admin_client: AsyncClient,
) -> None:
    """An admin can grant and revoke another user's admin rights."""
    created = await admin_client.post("/api/users", json={"email": "lead@onyx.test"})
    user_id = created.json()["id"]

    promoted = await admin_client.post(f"/api/users/{user_id}/promote")
    assert promoted.status_code == 200
    assert promoted.json()["is_admin"] is True

    demoted = await admin_client.post(f"/api/users/{user_id}/demote")
    assert demoted.status_code == 200
    assert demoted.json()["is_admin"] is False


async def test_break_glass_admin_cannot_be_demoted(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A .env break-glass admin is refused demotion from the UI."""
    monkeypatch.setattr(config, "admin_emails", {"root@onyx.test"})
    created = await admin_client.post("/api/users", json={"email": "root@onyx.test"})
    user_id = created.json()["id"]

    demote = await admin_client.post(f"/api/users/{user_id}/demote")

    assert demote.status_code == 409


# --- hard delete ---------------------------------------------------------


async def test_delete_never_logged_in_user(
    admin_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A mistyped, never-logged-in account can be hard-deleted."""
    created = await admin_client.post(
        "/api/users", json={"email": "typo@onyx.test"}
    )
    user_id = created.json()["id"]

    deleted = await admin_client.delete(f"/api/users/{user_id}")

    assert deleted.status_code == 204
    assert await session.get(User, user_id) is None


async def test_delete_logged_in_user_is_refused(
    admin_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A user who has logged in cannot be deleted — only deactivated."""
    created = await admin_client.post("/api/users", json={"email": "real@onyx.test"})
    user_id = created.json()["id"]
    user = await session.get(User, user_id)
    user.last_login_at = datetime.now(timezone.utc)  # mark as having logged in
    await session.commit()

    deleted = await admin_client.delete(f"/api/users/{user_id}")

    assert deleted.status_code == 409
    assert await session.get(User, user_id) is not None


# --- non-admin is forbidden everywhere -----------------------------------


async def test_every_admin_endpoint_rejects_non_admin(
    client: AsyncClient,
) -> None:
    """A non-admin authenticated user gets 403 on every account-management route."""
    calls = [
        client.get("/api/users"),
        client.post("/api/users", json={"email": "x@onyx.test"}),
        client.post("/api/users/1/deactivate"),
        client.post("/api/users/1/reactivate"),
        client.post("/api/users/1/promote"),
        client.post("/api/users/1/demote"),
        client.delete("/api/users/1"),
    ]
    for call in calls:
        response = await call
        assert response.status_code == 403


async def test_admin_page_renders_for_admin_and_is_denied_for_non_admin(
    admin_client: AsyncClient,
    client: AsyncClient,
) -> None:
    """The users screen renders for an admin and shows the denied page otherwise."""
    allowed = await admin_client.get("/admin/users")
    assert allowed.status_code == 200
    assert "Users" in allowed.text

    denied = await client.get("/admin/users")
    assert denied.status_code == 403
