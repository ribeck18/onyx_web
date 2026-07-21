from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rfi_revision import RfiRevision
from app.rfi.status import RfiStatus

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.rfi import Rfi


async def _next_revision_number(session: AsyncSession, rfi_id: int) -> int:
    """Return the next sequential revision number for an RFI, beginning at 0."""
    result = await session.execute(
        select(func.max(RfiRevision.revision_number)).where(RfiRevision.rfi_id == rfi_id)
    )
    current_max = result.scalar_one()
    return 0 if current_max is None else current_max + 1


async def create_revision(
    session: AsyncSession,
    rfi: Rfi,
    submit_file: File,
) -> RfiRevision:
    """Create and flush the next submitted revision for an RFI."""
    revision = RfiRevision(
        rfi=rfi,
        revision_number=await _next_revision_number(session, rfi.id),
        submit_file=submit_file,
        submitted_at=datetime.now(timezone.utc),
    )
    session.add(revision)
    await session.flush()
    return revision


async def record_return(
    session: AsyncSession,
    revision: RfiRevision,
    decision: RfiStatus,
    return_file: File | None,
    comments: str | None,
) -> RfiRevision:
    """Record the buyer's optional return material and required decision."""
    revision.return_file = return_file
    revision.returned_at = datetime.now(timezone.utc)
    revision.comments = comments
    revision.status = decision
    await session.flush()
    return revision


async def get_revisions(session: AsyncSession, rfi_id: int) -> list[RfiRevision]:
    """Return an RFI's submitted revisions oldest first."""
    result = await session.execute(
        select(RfiRevision)
        .where(RfiRevision.rfi_id == rfi_id)
        .order_by(RfiRevision.revision_number)
    )
    return list(result.scalars().all())


async def get_revision(
    session: AsyncSession,
    revision_id: int,
) -> RfiRevision | None:
    """Return one RFI revision by ID, or None when it does not exist."""
    result = await session.execute(
        select(RfiRevision).where(RfiRevision.id == revision_id)
    )
    return result.scalar_one_or_none()


async def get_latest_revision(
    session: AsyncSession,
    rfi_id: int,
) -> RfiRevision | None:
    """Return an RFI's latest submitted revision, if one exists."""
    result = await session.execute(
        select(RfiRevision)
        .where(RfiRevision.rfi_id == rfi_id)
        .order_by(RfiRevision.revision_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
