"""HTML page routes for the RFI domain."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.rfi import service as rfi_service
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/projects/{project_id}/rfis")
async def rfi_list(
    project_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the project-scoped RFI list and its create/edit modal."""
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    rfis = await rfi_service.get_rfis(session, project_id)
    return render(request, "rfi/list.html", {"project": project, "rfis": rfis})
