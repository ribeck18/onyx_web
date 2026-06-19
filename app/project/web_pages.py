"""HTML page routes for the project domain.

Mounted at root with no ``/api`` prefix. Pages render by calling services
directly (ADR 0005) — never by self-calling the JSON API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
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


@router.get("/projects/{project_id}")
async def project_detail(
    project_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the project detail page: header + scannable VDI table.

    The VDI table and create/edit modal live here; the page renders by calling
    services directly (never the JSON API).
    """
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    vdis = await vdi_service.get_vdis(session, project_id)
    return render(
        request,
        "project/detail.html",
        {"project": project, "vdis": vdis},
    )
