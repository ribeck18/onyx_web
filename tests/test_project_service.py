from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.project import service
from tests.factories import make_project, make_revision, make_vdi


async def test_delete_project_removes_project(session: AsyncSession) -> None:
    """delete_project actually deletes the loaded project row."""
    project = make_project()
    session.add(project)
    await session.flush()

    await service.delete_project(session, project)

    remaining = await session.execute(text("SELECT COUNT(*) FROM projects"))
    assert remaining.scalar_one() == 0


async def test_delete_project_cascades_to_vdis_and_revisions(
    session: AsyncSession,
) -> None:
    """Deleting a project through the service cascades to its VDIs and Revisions."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()

    await service.delete_project(session, project)

    vdi_count = await session.execute(text("SELECT COUNT(*) FROM vendor_data_items"))
    revision_count = await session.execute(text("SELECT COUNT(*) FROM revisions"))
    assert vdi_count.scalar_one() == 0
    assert revision_count.scalar_one() == 0
