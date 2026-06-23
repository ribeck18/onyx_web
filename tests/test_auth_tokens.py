from __future__ import annotations

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.models.api_token import ApiToken
from app.models.user import User


async def current_test_user(session: AsyncSession) -> User:
    """Return the default non-admin user seeded by the authenticated client."""
    user = await session.scalar(select(User).where(User.email == "tester@onyx.test"))
    assert user is not None
    return user


async def make_api_token_row(
    session: AsyncSession,
    user: User,
    name: str = "manual",
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> str:
    """Persist an ApiToken with explicit metadata and return its raw secret."""
    raw_token = auth_service.generate_token()
    now = datetime.now(timezone.utc)
    row = ApiToken(
        token_hash=auth_service.hash_token(raw_token),
        name=name,
        user_id=user.id,
        created_at=now,
        expires_at=expires_at or now + auth_service.API_TOKEN_LIFETIME,
        revoked_at=revoked_at,
    )
    session.add(row)
    await session.flush()
    return raw_token


# --- service primitives --------------------------------------------------


async def test_mint_api_token_stores_hash_and_sets_90_day_expiry(
    session: AsyncSession,
) -> None:
    """Minting a PAT stores only the hash and applies the 90-day hard expiry."""
    user = User(entra_oid="oid-pat", email="pat@onyx.test", is_active=True)
    session.add(user)
    await session.flush()

    secret, api_token = await auth_service.mint_api_token(session, user, "MCP")

    assert api_token.token_hash == auth_service.hash_token(secret)
    assert api_token.token_hash != secret
    lifetime = auth_service._as_utc(api_token.expires_at) - auth_service._as_utc(
        api_token.created_at
    )
    assert abs(lifetime - auth_service.API_TOKEN_LIFETIME) < timedelta(seconds=5)


async def test_resolve_api_token_updates_last_used(session: AsyncSession) -> None:
    """A valid PAT resolves to its active user and records when it was used."""
    user = User(entra_oid="oid-use", email="use@onyx.test", is_active=True)
    session.add(user)
    await session.flush()
    secret, api_token = await auth_service.mint_api_token(session, user, "MCP")

    resolved = await auth_service.resolve_api_token_user(session, secret)

    assert resolved is not None
    assert resolved.id == user.id
    assert api_token.last_used_at is not None


async def test_resolve_api_token_rejects_expired_revoked_and_deactivated(
    session: AsyncSession,
) -> None:
    """Expired, revoked, and deactivated-owner PATs do not authenticate."""
    user = User(entra_oid="oid-dead", email="dead@onyx.test", is_active=True)
    session.add(user)
    await session.flush()
    now = datetime.now(timezone.utc)
    expired = await make_api_token_row(
        session,
        user,
        name="expired",
        expires_at=now - timedelta(seconds=1),
    )
    revoked = await make_api_token_row(
        session,
        user,
        name="revoked",
        revoked_at=now,
    )
    active = await make_api_token_row(session, user, name="active")

    assert await auth_service.resolve_api_token_user(session, expired) is None
    assert await auth_service.resolve_api_token_user(session, revoked) is None

    user.is_active = False
    await session.flush()
    assert await auth_service.resolve_api_token_user(session, active) is None


# --- bearer gate ---------------------------------------------------------


async def test_valid_bearer_token_authenticates_api_request(
    anonymous_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A valid Authorization bearer PAT admits the request as its owning user."""
    user = User(entra_oid="oid-bearer", email="bearer@onyx.test", is_active=True)
    session.add(user)
    await session.flush()
    secret, _ = await auth_service.mint_api_token(session, user, "MCP")

    response = await anonymous_client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 200
    api_token = await session.scalar(
        select(ApiToken).where(ApiToken.user_id == user.id)
    )
    assert api_token.last_used_at is not None


async def test_invalid_bearer_token_is_401_not_redirect(
    anonymous_client: AsyncClient,
) -> None:
    """A bad bearer credential is machine-readable 401, never a login redirect."""
    response = await anonymous_client.get(
        "/",
        headers={"Authorization": "Bearer not-real"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


async def test_revoked_bearer_token_is_rejected(
    anonymous_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A revoked PAT immediately stops authenticating."""
    user = User(entra_oid="oid-revoked", email="revoked@onyx.test", is_active=True)
    session.add(user)
    await session.flush()
    secret = await make_api_token_row(
        session,
        user,
        revoked_at=datetime.now(timezone.utc),
    )

    response = await anonymous_client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 401


# --- token endpoints -----------------------------------------------------


async def test_create_token_returns_secret_once_and_list_hides_it(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Create returns the raw secret, while list returns metadata only."""
    created = await client.post("/api/tokens", json={"name": "MCP laptop"})

    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "MCP laptop"
    assert body["secret"]

    user = await current_test_user(session)
    api_token = await session.scalar(
        select(ApiToken).where(
            ApiToken.user_id == user.id,
            ApiToken.name == "MCP laptop",
        )
    )
    assert api_token is not None
    assert api_token.token_hash == auth_service.hash_token(body["secret"])
    assert api_token.token_hash != body["secret"]

    listing = await client.get("/api/tokens")
    assert listing.status_code == 200
    assert body["secret"] not in listing.text
    assert "secret" not in listing.json()[0]


async def test_user_can_hold_multiple_tokens_and_revoke_one(
    client: AsyncClient,
    anonymous_client: AsyncClient,
) -> None:
    """Revoking one PAT does not invalidate another token owned by the same user."""
    first = (await client.post("/api/tokens", json={"name": "first"})).json()
    second = (await client.post("/api/tokens", json={"name": "second"})).json()

    revoked = await client.post(f"/api/tokens/{first['id']}/revoke")
    assert revoked.status_code == 200
    assert revoked.json()["is_revoked"] is True

    first_use = await anonymous_client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {first['secret']}"},
    )
    second_use = await anonymous_client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {second['secret']}"},
    )

    assert first_use.status_code == 401
    assert second_use.status_code == 200


async def test_deactivating_user_invalidates_their_bearer_tokens(
    admin_client: AsyncClient,
    anonymous_client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A PAT stops working immediately when its owning user is deactivated."""
    created = await admin_client.post("/api/users", json={"email": "mcp@onyx.test"})
    user_id = created.json()["id"]
    user = await session.get(User, user_id)
    user.entra_oid = "oid-mcp"
    secret, _ = await auth_service.mint_api_token(session, user, "MCP")
    await session.commit()

    before = await anonymous_client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert before.status_code == 200

    deactivated = await admin_client.post(f"/api/users/{user_id}/deactivate")
    assert deactivated.status_code == 200

    after = await anonymous_client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert after.status_code == 401


async def test_tokens_page_renders_expiry_warning(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """The token screen shows expiry warnings and renders in both themes."""
    user = await current_test_user(session)
    await make_api_token_row(
        session,
        user,
        name="soon",
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )

    response = await client.get("/tokens")
    client.cookies.set("theme", "light")
    light_response = await client.get("/tokens")

    assert response.status_code == 200
    assert "API Tokens" in response.text
    assert "Expires soon" in response.text
    assert "soon" in response.text
    assert light_response.status_code == 200
    assert '<html lang="en" data-theme="light">' in light_response.text
