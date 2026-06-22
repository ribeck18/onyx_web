"""HTML page routes for the vdi domain.

Mounted at root with no ``/api`` prefix. Pages render by calling services
directly (ADR 0005).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.vdi import service as vdi_service
from app.vdi.revision import service as revision_service
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/vdi/{vdi_id}")
async def vdi_detail(
    vdi_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the VDI detail page read-only.

    The latest revision drives the file preview and buyer comments; the hero
    reflects the VDI's live status. The timeline lists every revision.
    """
    vdi = await vdi_service.get_vdi(session, vdi_id)
    if vdi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="VDI not found"
        )
    project = await project_service.get_project(session, vdi.project_id)
    revisions = await revision_service.get_revisions(session, vdi_id)
    latest_revision = revisions[-1] if revisions else None
    return render(
        request,
        "vdi/detail.html",
        {
            "vdi": vdi,
            "project": project,
            "revisions": revisions,
            "latest_revision": latest_revision,
        },
    )
