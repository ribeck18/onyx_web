from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.vdi import service as vdi_service
from app.vdi.revision import service
from app.vdi.revision.schema import RevisionRead

router = APIRouter(prefix="/vdi/{vdi_id}/revisions", tags=["revisions"])


@router.get("", response_model=list[RevisionRead])
async def list_revisions(
    vdi_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[RevisionRead]:
    """Return a VDI's revision history."""
    vendor_data_item = await vdi_service.get_vdi(session, vdi_id)
    if vendor_data_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor data item not found"
        )
    revisions = await service.get_revisions(session, vdi_id)
    return [RevisionRead.model_validate(revision) for revision in revisions]


@router.get("/{revision_id}", response_model=RevisionRead)
async def get_revision(
    vdi_id: int,
    revision_id: int,
    session: AsyncSession = Depends(get_session),
) -> RevisionRead:
    """Return a single revision belonging to the VDI."""
    revision = await service.get_revision(session, revision_id)
    if revision is None or revision.vendor_data_item_id != vdi_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found"
        )
    return RevisionRead.model_validate(revision)


@router.get("/latest", response_model=RevisionRead)
async def get_latest_revsion(vdi_id: int, session: AsyncSession = Depends(get_session)):
    """Return the latest revision belonging to a VDI."""
    revision = await service.get_latest_revision(session, vdi_id)
    if revision is None or revision.vendor_data_item_id != vdi_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found"
        )
    return RevisionRead.model_validate(revision)
