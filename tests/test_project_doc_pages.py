from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.project_doc import ProjectDoc
from app.project_doc.document_type import DocumentType
from tests.factories import make_doc_version, make_project, make_project_doc


async def seed_project(session: AsyncSession, **kwargs: str) -> Project:
    """Persist a project for the page tests and return it."""
    project = make_project(**kwargs)
    session.add(project)
    await session.flush()
    return project


async def add_doc(
    session: AsyncSession,
    project: Project,
    *,
    label: str = "E-101",
    document_type: DocumentType = DocumentType.DRAWING,
    version_count: int = 1,
) -> ProjectDoc:
    """Persist a document with the given number of versions and return it."""
    project_doc = make_project_doc(project, label=label, document_type=document_type)
    for version_number in range(2, version_count + 1):
        project_doc.versions.append(make_doc_version(version_number=version_number))
    session.add(project_doc)
    await session.flush()
    return project_doc


async def test_documents_list_unknown_project_returns_404(
    client: AsyncClient,
) -> None:
    """A missing project id is a 404 on the documents list page."""
    response = await client.get("/projects/9999/documents")
    assert response.status_code == 404


async def test_documents_list_shows_label_chip_version_and_date(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Each row carries the label, human type chip, current version, and date."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(
        session,
        project,
        label="SC-01",
        document_type=DocumentType.SPECIAL_CONDITION,
        version_count=2,
    )
    await session.commit()

    response = await client.get(f"/projects/{project.id}/documents")

    assert response.status_code == 200
    body = response.text
    assert "SC-01" in body
    assert "Special Condition" in body  # human chip label, never the raw enum
    assert "special_condition" not in body
    assert "Version 2" in body
    assert doc.updated_at.strftime("%Y-%m-%d") in body
    assert f'href="/project-docs/{doc.id}"' in body


async def test_documents_list_scoped_to_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Only the requested project's documents appear on its list page."""
    first_project = await seed_project(session, project_number="26-131")
    second_project = await seed_project(session, project_number="26-007")
    await add_doc(session, first_project, label="E-101")
    await add_doc(session, second_project, label="X-999")
    await session.commit()

    response = await client.get(f"/projects/{first_project.id}/documents")

    body = response.text
    assert "E-101" in body
    assert "X-999" not in body


async def test_documents_list_empty_state(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A project with no documents shows the empty state."""
    project = await seed_project(session)
    await session.commit()

    response = await client.get(f"/projects/{project.id}/documents")

    assert "No documents yet." in response.text


async def test_detail_unknown_document_returns_404(client: AsyncClient) -> None:
    """A missing document id is a 404 on the detail page."""
    response = await client.get("/project-docs/9999")
    assert response.status_code == 404


async def test_detail_lists_version_history_with_downloads(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The detail page names each version from the current label and links its
    file for download."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101", version_count=2)
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    assert response.status_code == 200
    body = response.text
    assert "E-101 Version 1" in body
    assert "E-101 Version 2" in body
    for version in doc.versions:
        assert f'href="/api/files/{version.file_id}"' in body


async def test_detail_version_names_follow_a_renamed_label(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Display names are composed from the current label, so a rename shows on
    every version — including those recorded before the rename."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101", version_count=2)
    await session.commit()

    patch = await client.patch(
        f"/api/project-docs/{doc.id}", json={"label": "E-102"}
    )
    assert patch.status_code == 200

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert "E-102 Version 1" in body
    assert "E-102 Version 2" in body
    assert "E-101 Version" not in body


async def test_detail_shows_type_chip_not_raw_enum(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The document type renders as a family-colored chip with a human label."""
    project = await seed_project(session)
    doc = await add_doc(
        session, project, document_type=DocumentType.VENDOR_DATA_SCHEDULE
    )
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert "Vendor Data Schedule" in body
    assert "vendor_data_schedule" not in body
    assert 'class="type-chip fam-' in body


async def test_project_detail_documents_button_shows_count(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The project page links to the documents list with the total count."""
    project = await seed_project(session, project_number="26-131")
    await add_doc(session, project, label="E-101")
    await add_doc(session, project, label="SPEC-1")
    await session.commit()

    response = await client.get(f"/projects/{project.id}")

    body = response.text
    assert f'href="/projects/{project.id}/documents"' in body
    assert "Documents (2)" in body


async def test_project_detail_documents_button_zero_count(
    client: AsyncClient, session: AsyncSession
) -> None:
    """With no documents the button still renders, counting zero."""
    project = await seed_project(session)
    await session.commit()

    response = await client.get(f"/projects/{project.id}")

    assert "Documents (0)" in response.text
