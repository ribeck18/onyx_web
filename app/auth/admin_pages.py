"""Admin HTML page: the users screen (ADR 0007).

Mounted at root with no ``/api`` prefix. It renders by calling the admin
service directly (ADR 0005), never the JSON API. The auth middleware has
already ensured a session; this route additionally refuses non-admins with the
themed denied page rather than a bare JSON 403.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import admin_service
from app.auth.dependencies import current_user
from app.database import get_session
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/admin/users")
async def admin_users_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the user-management screen, with each User's break-glass flag.

    Break-glass admins are surfaced so the UI can hide the demote control — the
    same rule the JSON API enforces (ADR 0007).
    """
    user = current_user(request)
    if not user.is_admin:
        return render(request, "auth/denied.html", {}, status_code=403)

    users = await admin_service.list_users(session)
    rows = [
        {"user": managed_user, "is_break_glass": admin_service.is_break_glass(managed_user)}
        for managed_user in users
    ]
    return render(request, "auth/admin_users.html", {"rows": rows})
