from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.project_doc import ProjectDoc
from app.project_doc.document_type import DocumentType
from tests.factories import (
    make_doc_version,
    make_file,
    make_project,
    make_project_doc,
)


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
    # The raw enum may appear only as an option value in the create modal.
    assert ">special_condition<" not in body
    assert "Version 2" in body
    assert doc.updated_at.strftime("%Y-%m-%d") in body
    assert f'data-row-href="/project-docs/{doc.id}"' in body


async def test_documents_list_row_is_the_click_target(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The row carries the detail URL and the label is a span, not an anchor."""
    project = await seed_project(session)
    doc = await add_doc(session, project, label="E-101")
    await session.commit()

    response = await client.get(f"/projects/{project.id}/documents")

    body = response.text
    assert f'data-row-href="/project-docs/{doc.id}"' in body
    assert '<span class="vdi-row-link">E-101</span>' in body
    assert f'<a class="vdi-row-link" href="/project-docs/{doc.id}"' not in body


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


async def test_detail_renders_one_pane_per_version_only_current_visible(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Every version is pre-rendered as a preview pane; only the current
    (highest-numbered) version's pane is visible on load."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101", version_count=3)
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    assert response.status_code == 200
    body = response.text
    assert body.count("data-doc-pane=") == 3
    current = doc.current_version
    assert f'data-doc-pane="{current.id}">' in body
    for version in doc.versions:
        if version.id == current.id:
            continue
        assert f'data-doc-pane="{version.id}" hidden>' in body
        # Panes are rendered inline (PDF iframes here), not links away.
        assert f'src="/api/files/{version.file_id}"' in body


async def test_detail_header_shows_current_filename_and_download(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The preview header carries the current version's filename and a
    DOWNLOAD link to that file."""
    project = await seed_project(session, project_number="26-131")
    doc = make_project_doc(project, label="E-101", with_first_version=False)
    doc.versions.append(
        make_doc_version(version_number=1, file=make_file(original_name="plan_v1.pdf"))
    )
    doc.versions.append(
        make_doc_version(version_number=2, file=make_file(original_name="plan_v2.pdf"))
    )
    session.add(doc)
    await session.flush()
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert "CURRENT VERSION" in body
    assert 'data-preview-filename>plan_v2.pdf<' in body
    current = doc.current_version
    assert f'href="/api/files/{current.file_id}?download=1">DOWNLOAD</a>' in body


async def test_detail_timeline_newest_first_with_descriptions_and_dates(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The timeline lists versions newest-first, each with its description
    (when present) and added date."""
    project = await seed_project(session, project_number="26-131")
    doc = make_project_doc(project, label="E-101", with_first_version=False)
    doc.versions.append(
        make_doc_version(version_number=1, description="Issued for review")
    )
    doc.versions.append(
        make_doc_version(version_number=2, description="Issued for construction")
    )
    session.add(doc)
    await session.flush()
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    newest_position = body.index('<span class="timeline-rev">VERSION 2</span>')
    oldest_position = body.index('<span class="timeline-rev">VERSION 1</span>')
    assert newest_position < oldest_position
    assert 'class="timeline-desc">Issued for review<' in body
    assert 'class="timeline-desc">Issued for construction<' in body
    for version in doc.versions:
        assert f"ADDED {version.created_at.strftime('%Y-%m-%d')}" in body


async def test_detail_newest_entry_marked_current(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The newest timeline entry is tagged CURRENT with the accent node; older
    entries carry a hidden VIEWING tag for the in-place pane swap."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101", version_count=2)
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert body.count(">CURRENT</span>") == 1
    assert body.count('class="timeline-node is-current"') == 1
    current = doc.current_version
    assert f'data-doc-version="{current.id}"' in body
    assert 'data-is-current="true"' in body
    assert "data-doc-viewing hidden>VIEWING</span>" in body


async def test_detail_breadcrumbs_link_home_project_and_documents(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Breadcrumbs run Home / project / Documents / this document."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101")
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert '<a class="crumb-link" href="/">HOME</a>' in body
    assert f'<a class="crumb-link" href="/projects/{project.id}">26-131</a>' in body
    assert (
        f'<a class="crumb-link" href="/projects/{project.id}/documents">DOCUMENTS</a>'
        in body
    )
    assert '<span class="crumb-current">E-101</span>' in body


async def test_detail_heading_follows_a_renamed_label(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The page heading and breadcrumb read the current label, so a rename is
    reflected everywhere the document is named."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101", version_count=2)
    await session.commit()

    patch = await client.patch(
        f"/api/project-docs/{doc.id}", json={"label": "E-102"}
    )
    assert patch.status_code == 200

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert "E-102" in body
    assert "E-101" not in body


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


async def test_detail_actions_row_has_add_version_button(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A full-width actions row above the columns carries an Add Version
    primary button wired to the add-version endpoint."""
    project = await seed_project(session, project_number="26-131")
    doc = await add_doc(session, project, label="E-101", version_count=2)
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert 'class="doc-actions"' in body
    # The actions row sits above the two-column layout.
    assert body.index('class="doc-actions"') < body.index('class="vdi-columns"')
    assert 'data-modal-open="version-modal"' in body
    assert f'data-url="/api/project-docs/{doc.id}/versions"' in body
    assert 'data-method="POST"' in body


async def test_detail_add_version_modal_fields(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The Add Version modal is multipart with a required file input and an
    optional description."""
    project = await seed_project(session)
    doc = await add_doc(session, project)
    await session.commit()

    response = await client.get(f"/project-docs/{doc.id}")

    body = response.text
    assert 'data-modal="version-modal"' in body
    assert 'data-encoding="multipart"' in body
    assert '<input type="file" name="file" class="field-file" required>' in body
    assert '<textarea name="description"' in body


async def test_project_detail_documents_chip_shows_count(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The actions row below the divider carries a chip linking to the
    documents list with the total count."""
    project = await seed_project(session, project_number="26-131")
    await add_doc(session, project, label="E-101")
    await add_doc(session, project, label="SPEC-1")
    await session.commit()

    response = await client.get(f"/projects/{project.id}")

    body = response.text
    assert 'class="doc-actions"' in body
    assert f'class="doc-pill" href="/projects/{project.id}/documents"' in body
    assert 'class="doc-pill-count">2<' in body


async def test_project_detail_documents_chip_zero_count(
    client: AsyncClient, session: AsyncSession
) -> None:
    """With no documents the chip still renders, counting zero."""
    project = await seed_project(session)
    await session.commit()

    response = await client.get(f"/projects/{project.id}")

    assert 'class="doc-pill-count">0<' in response.text


async def test_project_detail_documents_link_not_in_header_actions(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The header actions no longer link to documents; the chip below the
    divider is the only entry point."""
    project = await seed_project(session, project_number="26-131")
    await session.commit()

    response = await client.get(f"/projects/{project.id}")

    body = response.text
    # The chip is the sole documents link on the page.
    assert body.count(f'href="/projects/{project.id}/documents"') == 1
    assert "Documents (" not in body
    # Edit stays in the header actions.
    assert 'data-modal-open="project-modal"' in body
