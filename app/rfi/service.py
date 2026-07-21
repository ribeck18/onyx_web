from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rfi import Rfi
from app.rfi.revision import service as revision_service
from app.rfi.schema import RfiCreate, RfiUpdate
from app.rfi.status import RfiStatus

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.rfi_revision import RfiRevision


SUBMITTABLE_STATUSES = frozenset(
    {RfiStatus.NOT_STARTED, RfiStatus.APPROVED, RfiStatus.REJECTED}
)
RETURNABLE_STATUSES = frozenset({RfiStatus.SUBMITTED})


async def create_rfi(session: AsyncSession, data: RfiCreate) -> Rfi:
    """Create an RFI in Not Started status and flush it to the session."""
    rfi = Rfi(
        project_id=data.project_id,
        rfi_number=data.rfi_number,
        title=data.title,
        spec_drawing_reference=data.spec_drawing_reference,
        notes=data.notes,
    )
    session.add(rfi)
    await session.flush()
    return rfi


async def get_rfi(session: AsyncSession, rfi_id: int) -> Rfi | None:
    """Return one RFI by ID, or None if it does not exist."""
    result = await session.execute(select(Rfi).where(Rfi.id == rfi_id))
    return result.scalar_one_or_none()


async def get_rfis(session: AsyncSession, project_id: int) -> list[Rfi]:
    """Return one project's RFIs ordered by their entered RFI Number."""
    result = await session.execute(
        select(Rfi).where(Rfi.project_id == project_id).order_by(Rfi.rfi_number)
    )
    return list(result.scalars().all())


async def submit_rfi(
    session: AsyncSession,
    rfi: Rfi,
    submit_file: File,
) -> RfiRevision:
    """Create an RFI revision and move the live RFI to Submitted."""
    revision = await revision_service.create_revision(session, rfi, submit_file)
    rfi.status = RfiStatus.SUBMITTED
    await session.flush()
    return revision


async def return_rfi(
    session: AsyncSession,
    rfi: Rfi,
    decision: RfiStatus,
    return_file: File | None,
    comments: str | None,
) -> RfiRevision:
    """Record the buyer's decision on the latest RFI revision."""
    latest_revision = await revision_service.get_latest_revision(session, rfi.id)
    if latest_revision is None:
        raise RuntimeError("Submitted RFI has no revision")
    revision = await revision_service.record_return(
        session,
        latest_revision,
        decision,
        return_file,
        comments,
    )
    rfi.status = decision
    await session.flush()
    return revision


async def get_rfi_by_number(
    session: AsyncSession,
    project_id: int,
    rfi_number: str,
) -> Rfi | None:
    """Return an RFI by its project-scoped RFI Number, if present."""
    result = await session.execute(
        select(Rfi).where(
            Rfi.project_id == project_id,
            Rfi.rfi_number == rfi_number,
        )
    )
    return result.scalar_one_or_none()


async def count_rfis(session: AsyncSession, project_id: int) -> int:
    """Return how many RFIs belong to one project."""
    result = await session.execute(
        select(func.count()).select_from(Rfi).where(Rfi.project_id == project_id)
    )
    return result.scalar_one()


async def update_rfi(session: AsyncSession, rfi: Rfi, data: RfiUpdate) -> Rfi:
    """Apply supplied editable metadata fields and flush."""
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rfi, field, value)
    rfi.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return rfi


async def delete_rfi(session: AsyncSession, rfi: Rfi) -> None:
    """Delete an RFI and flush the pending transaction."""
    await session.delete(rfi)
    await session.flush()
