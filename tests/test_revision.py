from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project, make_revision, make_vdi


async def test_revision_defaults_to_submitted(session: AsyncSession) -> None:
    """A new revision is out for the buyer's review, so it starts SUBMITTED."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()

    assert revision.status is SubmitStatus.SUBMITTED


async def test_revision_timestamps_populate(session: AsyncSession) -> None:
    """Creating a revision records both created_at and updated_at."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()

    assert revision.created_at is not None
    assert revision.updated_at is not None


@pytest.mark.parametrize("missing_field", ["submit_document", "submitted_at"])
async def test_revision_requires_a_real_submittal(
    session: AsyncSession, missing_field: str
) -> None:
    """A revision can never exist with nothing actually submitted."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    setattr(revision, missing_field, None)
    session.add(revision)

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_revision_number_unique_within_vdi(session: AsyncSession) -> None:
    """Two revisions of the same VDI cannot share a revision number."""
    project = make_project()
    vdi = make_vdi(project)
    session.add(make_revision(vdi, revision_number=0))
    session.add(make_revision(vdi, revision_number=0))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_return_side_is_optional(session: AsyncSession) -> None:
    """A revision may sit awaiting the buyer with its whole return side empty."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()

    assert revision.return_document is None
    assert revision.returned_at is None
    assert revision.comments is None


async def test_revision_status_persisted_as_lowercase_value(
    session: AsyncSession,
) -> None:
    """The revision status enum stores its lowercase .value."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()

    stored_status = await session.execute(
        text("SELECT status FROM revisions WHERE id = :id"), {"id": revision.id}
    )
    assert stored_status.scalar_one() == "submitted"
