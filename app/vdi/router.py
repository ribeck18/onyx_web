from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.vdi import service
from app.vdi.schema import VdiCreate, VdiRead, VdiUpdate

router = APIRouter(prefix="/vdi", tags=["vdi"])


@router.post("", response_model=VdiRead, status_code=status.HTTP_201_CREATED)
async def create_vdi(
    data: VdiCreate,
    session: AsyncSession = Depends(get_session),
) -> VdiRead:
    """Create a vendor data item under an existing project."""
    project = await project_service.get_project(session, data.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    existing = await service.get_vdi_by_item_number(
        session, data.project_id, data.item_number
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item number already used in this project",
        )

    vendor_data_item = await service.create_vdi(session, data)
    await session.commit()
    return VdiRead.model_validate(vendor_data_item)


@router.get("", response_model=list[VdiRead])
async def list_vdis(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[VdiRead]:
    """Return the vendor data items in one project (project_id is required)."""
    vendor_data_items = await service.get_vdis(session, project_id)
    return [VdiRead.model_validate(vendor_data_item) for vendor_data_item in vendor_data_items]


@router.get("/{vdi_id}", response_model=VdiRead)
async def get_vdi(
    vdi_id: int,
    session: AsyncSession = Depends(get_session),
) -> VdiRead:
    """Return a single vendor data item."""
    vendor_data_item = await service.get_vdi(session, vdi_id)
    if vendor_data_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor data item not found"
        )
    return VdiRead.model_validate(vendor_data_item)


@router.patch("/{vdi_id}", response_model=VdiRead)
async def update_vdi(
    vdi_id: int,
    data: VdiUpdate,
    session: AsyncSession = Depends(get_session),
) -> VdiRead:
    """Partially update a VDI's editable fields (status is never editable)."""
    vendor_data_item = await service.get_vdi(session, vdi_id)
    if vendor_data_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor data item not found"
        )
    vendor_data_item = await service.update_vdi(session, vendor_data_item, data)
    await session.commit()
    return VdiRead.model_validate(vendor_data_item)


@router.delete("/{vdi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vdi(
    vdi_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a VDI; the ORM cascade removes its Revisions."""
    vendor_data_item = await service.get_vdi(session, vdi_id)
    if vendor_data_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor data item not found"
        )
    await service.delete_vdi(session, vendor_data_item)
    await session.commit()
