"""Admin account-management JSON API, mounted under ``/api`` (ADR 0007).

Every route here is gated by ``current_admin``, so a non-admin authenticated
User gets a 403 on all of them. Routes call the admin service, commit, and
return the schema, like every other domain.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import admin_service
from app.auth.dependencies import current_admin
from app.auth.schema import UserProvision, UserRead
from app.database import get_session
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(current_admin)])


async def _get_or_404(session: AsyncSession, user_id: int) -> User:
    """Return the User or raise a 404 — the shared lookup for every action route."""
    user = await admin_service.get_user(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.get("", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_session),
) -> list[UserRead]:
    """List every User with active / admin / has-logged-in status."""
    users = await admin_service.list_users(session)
    return [UserRead.model_validate(user) for user in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def provision_user(
    data: UserProvision,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Provision a User by email so their first Microsoft login can succeed."""
    email = data.email.strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Email is required",
        )
    existing = await admin_service.get_user_by_email(session, email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    user = await admin_service.provision_user(
        session, email, data.display_name, data.is_admin
    )
    await session.commit()
    return UserRead.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: int,
    admin: User = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Deactivate a User, invalidating their live sessions immediately."""
    user = await _get_or_404(session, user_id)
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account",
        )
    user = await admin_service.set_active(session, user, active=False)
    await session.commit()
    return UserRead.model_validate(user)


@router.post("/{user_id}/reactivate", response_model=UserRead)
async def reactivate_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Reactivate a previously deactivated User."""
    user = await _get_or_404(session, user_id)
    user = await admin_service.set_active(session, user, active=True)
    await session.commit()
    return UserRead.model_validate(user)


@router.post("/{user_id}/promote", response_model=UserRead)
async def promote_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Grant a User admin rights."""
    user = await _get_or_404(session, user_id)
    user = await admin_service.set_admin(session, user, is_admin=True)
    await session.commit()
    return UserRead.model_validate(user)


@router.post("/{user_id}/demote", response_model=UserRead)
async def demote_user(
    user_id: int,
    admin: User = Depends(current_admin),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Revoke a User's admin rights; break-glass admins can never be demoted."""
    user = await _get_or_404(session, user_id)
    if admin_service.is_break_glass(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Break-glass admins cannot be demoted",
        )
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot demote your own account",
        )
    user = await admin_service.set_admin(session, user, is_admin=False)
    await session.commit()
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a never-logged-in User (cleanup of a mistyped email).

    A User who has logged in is bound to a real identity and its lifecycle is
    deactivation, not deletion — that path is refused with a 409.
    """
    user = await _get_or_404(session, user_id)
    if user.last_login_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user who has logged in cannot be deleted; deactivate instead",
        )
    await admin_service.delete_user(session, user)
    await session.commit()
