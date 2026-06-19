"""HTML page routes for the project domain.

Mounted at root with no ``/api`` prefix. Pages render by calling services
directly (ADR 0005) — never by self-calling the JSON API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.vdi import service as vdi_service
from app.vdi.service import OPEN_STATUSES
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/")
async def home_gallery(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the Home project gallery with each project's open/total counts."""
    projects = await project_service.get_projects(session)
    cards = []
    for project in projects:
        vdis = await vdi_service.get_vdis(session, project.id)
        open_count = sum(1 for vdi in vdis if vdi.status in OPEN_STATUSES)
        cards.append(
            {
                "project": project,
                "total_count": len(vdis),
                "open_count": open_count,
            }
        )
    return render(request, "project/list.html", {"cards": cards})
