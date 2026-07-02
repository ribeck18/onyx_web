from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doc_version import DocVersion
from tests.factories import make_doc_version, make_project, make_project_doc


async def test_document_type_stored_as_lowercase_string(
    session: AsyncSession,
) -> None:
    """The enum persists as its lowercase string value, not the member name."""
    project = make_project()
    project_doc = make_project_doc(project)
    session.add(project_doc)
    await session.flush()

    stored = await session.execute(
        text("SELECT type FROM project_docs WHERE id = :id"),
        {"id": project_doc.id},
    )
    assert stored.scalar_one() == "drawing"


async def test_duplicate_version_number_rejected(session: AsyncSession) -> None:
    """(project_doc_id, version_number) is unique per document."""
    project = make_project()
    project_doc = make_project_doc(project)
    session.add(project_doc)
    await session.flush()

    project_doc.versions.append(make_doc_version(version_number=1))
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_deleting_doc_cascades_versions(session: AsyncSession) -> None:
    """Deleting a ProjectDoc removes its DocVersions via ORM cascade."""
    project = make_project()
    project_doc = make_project_doc(project)
    session.add(project_doc)
    await session.flush()

    await session.delete(project_doc)
    await session.flush()

    remaining = await session.execute(
        text("SELECT COUNT(*) FROM doc_versions"),
    )
    assert remaining.scalar_one() == 0


async def test_current_version_is_highest_number(session: AsyncSession) -> None:
    """current_version resolves to the highest version_number."""
    project = make_project()
    project_doc = make_project_doc(project)
    project_doc.versions.append(make_doc_version(version_number=2))
    session.add(project_doc)
    await session.flush()

    assert isinstance(project_doc.current_version, DocVersion)
    assert project_doc.current_version.version_number == 2
