from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project, make_revision, make_vdi


async def test_vdi_defaults_to_not_started(session: AsyncSession) -> None:
    """A freshly created VDI starts in NOT_STARTED without being told to."""
    project = make_project()
    vdi = make_vdi(project)
    session.add(vdi)
    await session.flush()

    assert vdi.status is SubmitStatus.NOT_STARTED


async def test_vdi_timestamps_populate(session: AsyncSession) -> None:
    """Creating a VDI records both created_at and updated_at."""
    project = make_project()
    vdi = make_vdi(project)
    session.add(vdi)
    await session.flush()

    assert vdi.created_at is not None
    assert vdi.updated_at is not None


@pytest.mark.parametrize("missing_field", ["item_number", "name", "approval_type", "submit_code"])
async def test_vdi_required_fields_reject_null(
    session: AsyncSession, missing_field: str
) -> None:
    """The buyer-facing identifier, name, and classification are all required."""
    project = make_project()
    vdi = make_vdi(project)
    setattr(vdi, missing_field, None)
    session.add(vdi)

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_item_number_unique_within_project(session: AsyncSession) -> None:
    """Two VDIs in the same project cannot share an item number."""
    project = make_project()
    session.add(make_vdi(project, item_number=5))
    session.add(make_vdi(project, item_number=5))

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_same_item_number_allowed_across_projects(session: AsyncSession) -> None:
    """The same buyer item number can appear on two different projects."""
    project_one = make_project(project_number="P-001")
    project_two = make_project(project_number="P-002")
    session.add(make_vdi(project_one, item_number=5))
    session.add(make_vdi(project_two, item_number=5))

    await session.flush()  # no IntegrityError


async def test_enum_persisted_as_lowercase_value(session: AsyncSession) -> None:
    """Enum columns store the lowercase .value, not the member name."""
    project = make_project()
    vdi = make_vdi(
        project,
        approval_type=ApprovalType.INFORMATION_ONLY,
        submit_code=SubmitCode.PTC,
    )
    session.add(vdi)
    await session.flush()

    row = await session.execute(
        text(
            "SELECT approval_type, submit_code, status "
            "FROM vendor_data_items WHERE id = :id"
        ),
        {"id": vdi.id},
    )
    approval_type, submit_code, status = row.one()
    assert approval_type == "information_only"
    assert submit_code == "ptc"
    assert status == "not_started"


async def test_delete_project_cascades_to_vdis_and_revisions(
    session: AsyncSession,
) -> None:
    """Deleting a project removes its VDIs and, through them, their revisions."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()

    await session.delete(project)
    await session.flush()

    remaining_vdis = await session.execute(select(VendorDataItem))
    assert remaining_vdis.scalars().all() == []
    remaining_revisions = await session.execute(
        text("SELECT COUNT(*) FROM revisions")
    )
    assert remaining_revisions.scalar_one() == 0
