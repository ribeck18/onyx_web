"""Admin-facing account management: the allowlist run from inside the app.

These operate on an injected ``AsyncSession`` like every other service; the
route layer owns the transaction. The defining capability here is instant
revocation: deactivating a User deletes their live Sessions on the spot (ADR
0007), so the bounce takes effect on their very next request.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.models.session import Session
from app.models.user import User


def is_break_glass(user: User) -> bool:
    """True when this User is a ``.env`` break-glass admin (never demotable).

    Break-glass admins are operator-controlled via ``ONYX_ADMIN_EMAILS`` and are
    always re-granted admin on login, so demoting one from the UI would be a
    no-op lie — it is refused instead.
    """
    return bool(user.email) and user.email.lower() in config.admin_emails


async def list_users(session: AsyncSession) -> list[User]:
    """Return every User, newest-provisioned first."""
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    """Return a single User by ID, or None if not found."""
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Return a User by email (case-insensitive), or None if not found."""
    result = await session.execute(select(User).where(User.email.ilike(email)))
    return result.scalar_one_or_none()


async def provision_user(
    session: AsyncSession,
    email: str,
    display_name: str | None = None,
    is_admin: bool = False,
) -> User:
    """Provision a new, login-ready User row (no Entra binding yet) and flush.

    The ``entra_oid`` stays null until this person's first Microsoft login binds
    it; existence of the row is what lets that first login succeed (ADR 0007).
    """
    user = User(
        entra_oid=None,
        email=email.strip(),
        display_name=display_name,
        is_admin=is_admin,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user


async def invalidate_user_sessions(session: AsyncSession, user: User) -> None:
    """Delete every live Session for this User, revoking them server-side at once."""
    await session.execute(delete(Session).where(Session.user_id == user.id))
    await session.flush()


async def set_active(session: AsyncSession, user: User, active: bool) -> User:
    """Activate or deactivate a User; deactivation kills their live sessions now."""
    user.is_active = active
    if not active:
        await invalidate_user_sessions(session, user)
    await session.flush()
    return user


async def set_admin(session: AsyncSession, user: User, is_admin: bool) -> User:
    """Grant or revoke a User's admin rights and flush."""
    user.is_admin = is_admin
    await session.flush()
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    """Hard-delete a User; the ORM cascade removes any sessions they own."""
    await session.delete(user)
    await session.flush()
