from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.file import service as file_service
from app.file.dependencies import get_storage_root
from app.project import service as project_service
from app.vdi import service
from app.vdi.schema import RETURN_CODES, VdiCreate, VdiRead, VdiUpdate
from app.vdi.submit_status import SubmitStatus

router = APIRouter(prefix="/vdi", tags=["vdi"])

# Fields that record the terms under which a VDI was submitted to the buyer.
# They lock once the VDI leaves NOT_STARTED so the stored record cannot drift
# from what was actually submitted (ADR 0010).
LOCKED_AFTER_SUBMISSION = ("item_number", "approval_type", "submit_code")


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

    supplied = data.model_dump(exclude_unset=True)

    # Guard the submission-defining fields once the VDI has been submitted. The
    # check is on actual change, so a no-op resubmit of the same value passes
    # (read-modify-write clients are not punished). Lives in the route layer,
    # consistent with the create route's uniqueness check (ADR 0010).
    if vendor_data_item.status is not SubmitStatus.NOT_STARTED:
        for field in LOCKED_AFTER_SUBMISSION:
            if field in supplied and supplied[field] != getattr(
                vendor_data_item, field
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Submission fields are locked once the VDI is submitted",
                )

    # Reject an item-number collision with a sibling in the same project,
    # mirroring the create route. Only an actual change is checked, so any match
    # is necessarily a different VDI (this one still holds its old number).
    new_item_number = supplied.get("item_number")
    if (
        new_item_number is not None
        and new_item_number != vendor_data_item.item_number
    ):
        sibling = await service.get_vdi_by_item_number(
            session, vendor_data_item.project_id, new_item_number
        )
        if sibling is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item number already used in this project",
            )

    vendor_data_item = await service.update_vdi(session, vendor_data_item, data)
    await session.commit()
    return VdiRead.model_validate(vendor_data_item)


@router.post("/{vdi_id}/submit", response_model=VdiRead)
async def submit_vdi(
    vdi_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> VdiRead:
    """Submit a VDI: store the uploaded submittal and open its next Revision.

    The status guard runs before the file is saved so a rejected submit (409)
    never writes orphaned bytes; save_upload then rejects an empty upload (400).
    """
    vendor_data_item = await service.get_vdi(session, vdi_id)
    if vendor_data_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor data item not found"
        )
    if vendor_data_item.status not in service.SUBMITTABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VDI cannot be submitted from its current status",
        )
    submit_file = await file_service.save_upload(session, file, storage_root)
    await service.submit_vdi(session, vendor_data_item, submit_file)
    await session.commit()
    return VdiRead.model_validate(vendor_data_item)


@router.post("/{vdi_id}/return", response_model=VdiRead)
async def return_vdi(
    vdi_id: int,
    return_code: SubmitStatus = Form(...),
    file: UploadFile = File(...),
    comments: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> VdiRead:
    """Record the buyer's return on a VDI's current submittal.

    return_code, status, and emptiness are all validated before the file is
    saved so a rejected return never writes orphaned bytes. The A/B/C/D rule
    lives here now that the body is multipart form fields, not a JSON model.
    """
    if return_code not in RETURN_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="return_code must be one of A, B, C, or D",
        )
    vendor_data_item = await service.get_vdi(session, vdi_id)
    if vendor_data_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Vendor data item not found"
        )
    if vendor_data_item.status not in service.RETURNABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VDI cannot be returned from its current status",
        )
    return_file = await file_service.save_upload(session, file, storage_root)
    await service.return_vdi(
        session,
        vendor_data_item,
        return_code,
        return_file,
        comments,
    )
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
