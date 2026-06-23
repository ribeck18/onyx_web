"""Self-service API token page routes.

Mounted at root with no ``/api`` prefix. The page renders token metadata from
the auth service directly; create/revoke actions use the JSON API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.dependencies import current_user
from app.auth.schema import ApiTokenRead
from app.database import get_session
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/tokens")
async def tokens_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the current user's Personal Access Token management screen."""
    user = current_user(request)
    tokens = await auth_service.list_api_tokens(session, user)
    rows = [ApiTokenRead.model_validate(api_token) for api_token in tokens]
    return render(request, "auth/tokens.html", {"tokens": rows})
