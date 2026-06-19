"""HTML page route for the historical revision view.

Mounted at root with no ``/api`` prefix. Reuses ``vdi/detail.html`` with
``historical=True`` so a chosen past revision renders the full VDI layout,
unambiguously read-only (ADR 0005).
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


@router.get("/vdi/{vdi_id}/revisions/{revision_id}")
async def revision_detail(
    vdi_id: int,
    revision_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render a past revision in the VDI layout, read-only (historical=True).

    The chosen revision drives the hero status, file preview, and buyer comments;
    the notes box still shows the VDI's current, item-level notes. The revision
    must belong to the VDI in the path or the view is a 404.
    """
    vdi = await vdi_service.get_vdi(session, vdi_id)
    if vdi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="VDI not found"
        )
    revision = await revision_service.get_revision(session, revision_id)
    if revision is None or revision.vendor_data_item_id != vdi_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found"
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
            "revision": revision,
            "revisions": revisions,
            "latest_revision": latest_revision,
            "historical": True,
        },
    )
