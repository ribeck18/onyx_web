from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.revision import Revision
from app.models.vdi import VendorDataItem

if TYPE_CHECKING:
    from app.models.file import File
from app.vdi.revision import service as revision_service
from app.vdi.schema import VdiCreate, VdiUpdate
from app.vdi.submit_status import SubmitStatus

# A submit opens the next round-trip, so it is valid only before the first
# submittal (NOT_STARTED) or after a rejection (B/C). SUBMITTED is already out
# for review; A/D are approved (terminal).
SUBMITTABLE_STATUSES = frozenset(
    {SubmitStatus.NOT_STARTED, SubmitStatus.B, SubmitStatus.C}
)

# A return records the buyer's response to the current submittal, so it is valid
# only while the VDI is out for review.
RETURNABLE_STATUSES = frozenset({SubmitStatus.SUBMITTED})


async def create_vdi(session: AsyncSession, data: VdiCreate) -> VendorDataItem:
    """Create a new vendor data item and flush it to the session.

    Status is left to the model default (NOT_STARTED); the submit/return
    lifecycle owns every later status change.
    """
    vendor_data_item = VendorDataItem(
        project_id=data.project_id,
        item_number=data.item_number,
        submittal_number=data.submittal_number,
        name=data.name,
        description=data.description,
        approval_type=data.approval_type,
        submit_code=data.submit_code,
        spec_drawing_reference=data.spec_drawing_reference,
        notes=data.notes,
    )
    session.add(vendor_data_item)
    await session.flush()
    return vendor_data_item


async def get_vdi(session: AsyncSession, vdi_id: int) -> VendorDataItem | None:
    """Return a single vendor data item by ID, or None if not found."""
    result = await session.execute(
        select(VendorDataItem).where(VendorDataItem.id == vdi_id)
    )
    return result.scalar_one_or_none()


async def get_vdis(session: AsyncSession, project_id: int) -> list[VendorDataItem]:
    """Return all vendor data items belonging to one project."""
    result = await session.execute(
        select(VendorDataItem)
        .where(VendorDataItem.project_id == project_id)
        .order_by(VendorDataItem.item_number)
    )
    return list(result.scalars().all())


async def update_vdi(
    session: AsyncSession,
    vendor_data_item: VendorDataItem,
    data: VdiUpdate,
) -> VendorDataItem:
    """Apply partial updates to a VDI's editable fields and flush.

    Status is never among the editable fields; it stays lifecycle-driven.
    """
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor_data_item, field, value)
    vendor_data_item.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return vendor_data_item


async def delete_vdi(session: AsyncSession, vendor_data_item: VendorDataItem) -> None:
    """Delete a VDI; ORM cascade removes its Revisions."""
    await session.delete(vendor_data_item)
    await session.flush()


async def submit_vdi(
    session: AsyncSession,
    vendor_data_item: VendorDataItem,
    submit_file: File,
) -> Revision:
    """Open the next Revision and move the VDI out for review.

    Revision creation is delegated to revision.service (the only direction the
    dependency runs); the new Revision links the already-saved submit File, and
    it and the VDI's SUBMITTED status are flushed together so the route commits
    them atomically. Callers must check SUBMITTABLE_STATUSES first.
    """
    revision = await revision_service.create_revision(
        session, vendor_data_item, submit_file
    )
    vendor_data_item.status = SubmitStatus.SUBMITTED
    await session.flush()
    return revision


async def return_vdi(
    session: AsyncSession,
    vendor_data_item: VendorDataItem,
    return_code: SubmitStatus,
    return_file: File,
    comments: str | None,
) -> Revision:
    """Record the buyer's return on the latest Revision and set VDI status.

    The return side is written by revision.service onto the latest Revision
    (the one currently out for review), linking the already-saved return File;
    the VDI status is set to the return code and flushed together so the route
    commits them atomically. Callers must check RETURNABLE_STATUSES first, which
    guarantees a latest Revision exists.
    """
    latest_revision = await revision_service.get_latest_revision(
        session, vendor_data_item.id
    )
    revision = await revision_service.record_return(
        session, latest_revision, return_code, return_file, comments
    )
    vendor_data_item.status = return_code
    await session.flush()
    return revision


async def get_vdi_by_item_number(
    session: AsyncSession,
    project_id: int,
    item_number: int,
) -> VendorDataItem | None:
    """Return the VDI with this buyer item number in the project, if any."""
    result = await session.execute(
        select(VendorDataItem).where(
            VendorDataItem.project_id == project_id,
            VendorDataItem.item_number == item_number,
        )
    )
    return result.scalar_one_or_none()
