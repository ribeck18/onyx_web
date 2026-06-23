"""Auth services: allowlist resolution, session lifecycle, and token hashing.

These operate on an injected ``AsyncSession`` like every other service. The one
deliberate deviation (ADR 0009) is that the auth *middleware* — not a route —
opens the session it hands to ``resolve_session_user``; transaction control for
real domain work still lives in the route layer.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.models.api_token import ApiToken
from app.models.session import Session
from app.models.user import User

# The opaque browser-session cookie. Its value is never stored; only its hash is.
SESSION_COOKIE_NAME = "onyx_session"

# Session lifetime (ADR 0007): 8h sliding idle window, 7d absolute cap.
SESSION_IDLE_TIMEOUT = timedelta(hours=8)
SESSION_ABSOLUTE_CAP = timedelta(days=7)

# Machine/API token lifetime (ADR 0008): 90-day hard expiry.
API_TOKEN_LIFETIME = timedelta(days=90)
API_TOKEN_EXPIRY_WARNING = timedelta(days=14)

# Only rewrite last_seen_at when it is older than this, so an active user does
# not trigger a write on every single request.
LAST_SEEN_THROTTLE = timedelta(seconds=60)


def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest stored in place of a raw session token.

    The tokens are 256-bit random strings, so a plain fast hash is sufficient —
    there is no low-entropy secret to protect with a slow KDF.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    """Return a fresh high-entropy opaque token for a new session."""
    return secrets.token_urlsafe(32)


def _as_utc(moment: datetime) -> datetime:
    """Normalize a stored datetime to timezone-aware UTC.

    SQLite hands back naive datetimes even for ``DateTime(timezone=True)``
    columns, so expiry math must assume UTC when tzinfo is missing rather than
    raise on an aware/naive comparison.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


async def _user_by_oid(session: AsyncSession, entra_oid: str) -> User | None:
    """Return the User canonically keyed on this Entra ``oid``, if any."""
    result = await session.execute(select(User).where(User.entra_oid == entra_oid))
    return result.scalar_one_or_none()


async def _user_by_email(session: AsyncSession, email: str) -> User | None:
    """Return a User by email (case-insensitive), if any."""
    result = await session.execute(
        select(User).where(User.email.ilike(email))
    )
    return result.scalar_one_or_none()


async def _bind_or_match_by_email(
    session: AsyncSession,
    entra_oid: str,
    email: str,
    allow_rebind: bool,
) -> User | None:
    """Resolve a provisioned row by email and bind the Entra ``oid`` to it.

    A provisioned row starts with an email and no ``oid``; first login binds it.
    A row already bound to a *different* identity is never inherited (an email
    can be reassigned to a new hire) — except for a break-glass email, where the
    operator-controlled ``.env`` outranks the stored binding.
    """
    if not email:
        return None
    candidate = await _user_by_email(session, email)
    if candidate is None:
        return None
    if candidate.entra_oid is None:
        candidate.entra_oid = entra_oid
        return candidate
    if candidate.entra_oid == entra_oid:
        return candidate
    if allow_rebind:
        candidate.entra_oid = entra_oid
        return candidate
    return None


async def resolve_login(session: AsyncSession, claims: dict[str, str]) -> User | None:
    """Resolve validated Entra claims to the User to sign in, or None to refuse.

    Returns None when the identity is authenticated but not allowed in (no
    provisioned row, an inherited email, or a deactivated account). Break-glass
    emails from ``ONYX_ADMIN_EMAILS`` are always admitted as active admins,
    creating the row if it does not exist.
    """
    entra_oid = claims["oid"]
    email = (claims.get("email") or "").strip()
    display_name = (claims.get("name") or "").strip() or None
    is_break_glass = bool(email) and email.lower() in config.admin_emails

    user = await _user_by_oid(session, entra_oid)
    if user is None:
        user = await _bind_or_match_by_email(
            session, entra_oid, email, allow_rebind=is_break_glass
        )

    if user is None:
        if not is_break_glass:
            return None
        user = User(
            entra_oid=entra_oid,
            email=email,
            display_name=display_name,
            is_admin=True,
            is_active=True,
        )
        session.add(user)

    # The .env-listed break-glass admin can never be locked out of Onyx.
    if is_break_glass:
        user.is_admin = True
        user.is_active = True

    if display_name:
        user.display_name = display_name
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()

    return user if user.is_active else None


async def mint_session(session: AsyncSession, user: User) -> tuple[str, Session]:
    """Create a server-side Session for the user and return its raw token.

    The raw token goes into the cookie and is shown to the browser once; only
    its hash is persisted.
    """
    raw_token = generate_token()
    now = datetime.now(timezone.utc)
    row = Session(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        created_at=now,
        expires_at=now + SESSION_ABSOLUTE_CAP,
        last_seen_at=now,
    )
    session.add(row)
    await session.flush()
    return raw_token, row


async def resolve_session_user(
    session: AsyncSession,
    raw_token: str,
) -> User | None:
    """Validate a session cookie token and return its active user, or None.

    Enforces both the absolute cap and the idle window, deletes a session that
    has lapsed on either, and refuses a deactivated user. A throttled
    ``last_seen_at`` touch keeps an active session sliding without writing on
    every request.
    """
    result = await session.execute(
        select(Session).where(Session.token_hash == hash_token(raw_token))
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    now = datetime.now(timezone.utc)
    expires_at = _as_utc(row.expires_at)
    last_seen_at = _as_utc(row.last_seen_at)
    # These auth-state writes commit here on purpose: the middleware (ADR 0009)
    # opens this session in plumbing and never reaches the route-layer commit, so
    # a flush alone would be rolled back when its session closes. The throttle
    # keeps these commits rare rather than once-per-request.
    if now >= expires_at or now - last_seen_at > SESSION_IDLE_TIMEOUT:
        await session.delete(row)
        await session.commit()
        return None

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None

    if now - last_seen_at > LAST_SEEN_THROTTLE:
        row.last_seen_at = now
        await session.commit()

    return user


async def delete_session(session: AsyncSession, raw_token: str) -> None:
    """Delete the session backing this cookie token (idempotent logout)."""
    result = await session.execute(
        select(Session).where(Session.token_hash == hash_token(raw_token))
    )
    row = result.scalar_one_or_none()
    if row is not None:
        await session.delete(row)
        await session.flush()


async def mint_api_token(
    session: AsyncSession,
    user: User,
    name: str,
) -> tuple[str, ApiToken]:
    """Create a per-user PAT and return the raw secret exactly once.

    The row stores only a hash. The raw value is returned to the caller for the
    creation response and cannot be recovered afterward.
    """
    raw_token = generate_token()
    now = datetime.now(timezone.utc)
    row = ApiToken(
        token_hash=hash_token(raw_token),
        name=name,
        user_id=user.id,
        created_at=now,
        expires_at=now + API_TOKEN_LIFETIME,
    )
    session.add(row)
    await session.flush()
    return raw_token, row


async def list_api_tokens(session: AsyncSession, user: User) -> list[ApiToken]:
    """Return the current user's PAT metadata, newest first."""
    result = await session.execute(
        select(ApiToken)
        .where(ApiToken.user_id == user.id)
        .order_by(ApiToken.created_at.desc())
    )
    return list(result.scalars().all())


async def get_api_token(
    session: AsyncSession,
    user: User,
    token_id: int,
) -> ApiToken | None:
    """Return one PAT owned by this user, or None if it does not exist."""
    result = await session.execute(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.user_id == user.id,
        )
    )
    return result.scalar_one_or_none()


async def revoke_api_token(session: AsyncSession, api_token: ApiToken) -> ApiToken:
    """Mark a PAT revoked so it stops authenticating immediately."""
    if api_token.revoked_at is None:
        api_token.revoked_at = datetime.now(timezone.utc)
        await session.flush()
    return api_token


async def resolve_api_token_user(
    session: AsyncSession,
    raw_token: str,
) -> User | None:
    """Validate a bearer PAT and return its active user, or None.

    Expired, revoked, missing, and deactivated-user tokens are rejected with no
    redirect. A successful use updates ``last_used_at`` immediately because the
    middleware owns this auth-state transaction.
    """
    result = await session.execute(
        select(ApiToken).where(ApiToken.token_hash == hash_token(raw_token))
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    now = datetime.now(timezone.utc)
    if row.revoked_at is not None or now >= _as_utc(row.expires_at):
        return None

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        return None

    row.last_used_at = now
    await session.commit()
    return user
