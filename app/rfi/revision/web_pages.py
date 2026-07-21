"""HTML page route for read-only RFI revision history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.rfi import service as rfi_service
from app.rfi.revision import service as revision_service
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/rfis/{rfi_id}/revisions/{revision_id}")
async def revision_detail(
    rfi_id: int,
    revision_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render one RFI revision in the immutable detail layout."""
    rfi = await rfi_service.get_rfi(session, rfi_id)
    if rfi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI not found",
        )
    revision = await revision_service.get_revision(session, revision_id)
    if revision is None or revision.rfi_id != rfi_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI revision not found",
        )
    project = await project_service.get_project(session, rfi.project_id)
    revisions = await revision_service.get_revisions(session, rfi_id)
    return render(
        request,
        "rfi/detail.html",
        {
            "rfi": rfi,
            "project": project,
            "revision": revision,
            "revisions": revisions,
            "latest_revision": revisions[-1] if revisions else None,
            "historical": True,
        },
    )
