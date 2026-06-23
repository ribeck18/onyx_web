"""Self-service Personal Access Token JSON API, mounted under ``/api``.

These endpoints are scoped to the authenticated User, not admins. Creating a
token returns the raw secret once; list/revoke expose metadata only (ADR 0008).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.dependencies import current_user
from app.auth.schema import ApiTokenCreate, ApiTokenCreated, ApiTokenRead
from app.database import get_session
from app.models.user import User

router = APIRouter(prefix="/tokens", tags=["tokens"])


@router.get("", response_model=list[ApiTokenRead])
async def list_tokens(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[ApiTokenRead]:
    """List the current user's token metadata, never raw secrets."""
    user = current_user(request)
    tokens = await auth_service.list_api_tokens(session, user)
    return [ApiTokenRead.model_validate(api_token) for api_token in tokens]


@router.post("", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_token(
    data: ApiTokenCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiTokenCreated:
    """Create a named PAT and return its raw secret exactly once."""
    name = data.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Name is required",
        )

    secret, api_token = await auth_service.mint_api_token(session, user, name)
    await session.commit()
    return ApiTokenCreated(
        id=api_token.id,
        name=api_token.name,
        created_at=api_token.created_at,
        expires_at=api_token.expires_at,
        last_used_at=api_token.last_used_at,
        revoked_at=api_token.revoked_at,
        secret=secret,
    )


@router.post("/{token_id}/revoke", response_model=ApiTokenRead)
async def revoke_token(
    token_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiTokenRead:
    """Revoke one token owned by the current user."""
    api_token = await auth_service.get_api_token(session, user, token_id)
    if api_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )
    api_token = await auth_service.revoke_api_token(session, api_token)
    await session.commit()
    return ApiTokenRead.model_validate(api_token)
