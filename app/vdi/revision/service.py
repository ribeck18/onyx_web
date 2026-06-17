from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.revision import Revision
from app.vdi.submit_status import SubmitStatus

if TYPE_CHECKING:
    from app.models.vdi import VendorDataItem


async def _next_revision_number(session: AsyncSession, vdi_id: int) -> int:
    """Return the next sequential revision number for a VDI (first is 0)."""
    result = await session.execute(
        select(func.max(Revision.revision_number)).where(
            Revision.vendor_data_item_id == vdi_id
        )
    )
    current_max = result.scalar_one()
    return 0 if current_max is None else current_max + 1


async def create_revision(
    session: AsyncSession,
    vendor_data_item: VendorDataItem,
    submit_document: str,
) -> Revision:
    """Open the next Revision on a VDI as a real submittal and flush.

    The revision number is max-existing-plus-one per VDI, submitted_at is
    server-set, and status defaults to SUBMITTED via the model. This module
    never imports vdi.service: the dependency only runs vdi.service -> here.
    """
    revision = Revision(
        vendor_data_item=vendor_data_item,
        revision_number=await _next_revision_number(session, vendor_data_item.id),
        submit_document=submit_document,
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(revision)
    await session.flush()
    return revision


async def record_return(
    session: AsyncSession,
    revision: Revision,
    return_code: SubmitStatus,
    return_document: str,
    comments: str | None,
) -> Revision:
    """Write the buyer's return side onto a revision and flush.

    The return code is stored as the revision's status (A/D approved,
    B/C rejected); returned_at is server-set. This module owns revision
    mutations; the dependency runs vdi.service -> here only.
    """
    revision.return_document = return_document
    revision.returned_at = datetime.now(timezone.utc)
    revision.comments = comments
    revision.status = return_code
    await session.flush()
    return revision


async def get_revisions(session: AsyncSession, vdi_id: int) -> list[Revision]:
    """Return a VDI's revision history, oldest first."""
    result = await session.execute(
        select(Revision)
        .where(Revision.vendor_data_item_id == vdi_id)
        .order_by(Revision.revision_number)
    )
    return list(result.scalars().all())


async def get_revision(session: AsyncSession, revision_id: int) -> Revision | None:
    """Return a single revision by ID, or None if not found."""
    result = await session.execute(select(Revision).where(Revision.id == revision_id))
    return result.scalar_one_or_none()


async def get_latest_revision(session: AsyncSession, vdi_id: int) -> Revision | None:
    """Return a VDI's most recent revision, or None if it has none yet."""
    result = await session.execute(
        select(Revision)
        .where(Revision.vendor_data_item_id == vdi_id)
        .order_by(Revision.revision_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
