from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.rfi import service as rfi_service
from app.rfi.revision import service
from app.rfi.revision.schema import RfiRevisionRead

router = APIRouter(prefix="/rfis/{rfi_id}/revisions", tags=["rfi revisions"])


@router.get("", response_model=list[RfiRevisionRead])
async def list_revisions(
    rfi_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[RfiRevisionRead]:
    """Return the read-only revision history for an RFI."""
    if await rfi_service.get_rfi(session, rfi_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI not found",
        )
    revisions = await service.get_revisions(session, rfi_id)
    return [RfiRevisionRead.model_validate(revision) for revision in revisions]


@router.get("/latest", response_model=RfiRevisionRead)
async def get_latest_revision(
    rfi_id: int,
    session: AsyncSession = Depends(get_session),
) -> RfiRevisionRead:
    """Return the latest submitted revision for an RFI."""
    revision = await service.get_latest_revision(session, rfi_id)
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI revision not found",
        )
    return RfiRevisionRead.model_validate(revision)


@router.get("/{revision_id}", response_model=RfiRevisionRead)
async def get_revision(
    rfi_id: int,
    revision_id: int,
    session: AsyncSession = Depends(get_session),
) -> RfiRevisionRead:
    """Return one revision when it belongs to the requested RFI."""
    revision = await service.get_revision(session, revision_id)
    if revision is None or revision.rfi_id != rfi_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI revision not found",
        )
    return RfiRevisionRead.model_validate(revision)
