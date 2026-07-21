from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.rfi import service
from app.rfi.schema import RfiCreate, RfiRead, RfiUpdate

router = APIRouter(prefix="/rfis", tags=["rfis"])


@router.post("", response_model=RfiRead, status_code=status.HTTP_201_CREATED)
async def create_rfi(
    data: RfiCreate,
    session: AsyncSession = Depends(get_session),
) -> RfiRead:
    """Create an RFI under an existing project."""
    project = await project_service.get_project(session, data.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if await service.get_rfi_by_number(session, data.project_id, data.rfi_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RFI number already used in this project",
        )
    rfi = await service.create_rfi(session, data)
    await session.commit()
    return RfiRead.model_validate(rfi)


@router.get("", response_model=list[RfiRead])
async def list_rfis(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[RfiRead]:
    """Return a project's RFIs in RFI Number order."""
    rfis = await service.get_rfis(session, project_id)
    return [RfiRead.model_validate(rfi) for rfi in rfis]


@router.get("/{rfi_id}", response_model=RfiRead)
async def get_rfi(
    rfi_id: int,
    session: AsyncSession = Depends(get_session),
) -> RfiRead:
    """Return one RFI."""
    rfi = await service.get_rfi(session, rfi_id)
    if rfi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI not found",
        )
    return RfiRead.model_validate(rfi)


@router.patch("/{rfi_id}", response_model=RfiRead)
async def update_rfi(
    rfi_id: int,
    data: RfiUpdate,
    session: AsyncSession = Depends(get_session),
) -> RfiRead:
    """Partially update an RFI's editable metadata."""
    rfi = await service.get_rfi(session, rfi_id)
    if rfi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI not found",
        )

    supplied = data.model_dump(exclude_unset=True)
    rfi_number = supplied.get("rfi_number")
    if rfi_number is not None and rfi_number != rfi.rfi_number:
        sibling = await service.get_rfi_by_number(session, rfi.project_id, rfi_number)
        if sibling is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RFI number already used in this project",
            )

    rfi = await service.update_rfi(session, rfi, data)
    await session.commit()
    return RfiRead.model_validate(rfi)


@router.delete("/{rfi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rfi(
    rfi_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an RFI."""
    rfi = await service.get_rfi(session, rfi_id)
    if rfi is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFI not found",
        )
    await service.delete_rfi(session, rfi)
    await session.commit()
