from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vdi import VendorDataItem
from app.vdi.schema import VdiCreate


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
