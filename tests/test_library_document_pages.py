from __future__ import annotations

import re

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.library_document import LibraryDocument
from app.models.library_document_version import LibraryDocumentVersion


async def add_library_document(
    session: AsyncSession,
    title: str,
) -> LibraryDocument:
    """Persist a Library Document with one file-backed current version."""
    library_document = LibraryDocument(title=title)
    library_document.versions.append(
        LibraryDocumentVersion(
            version_number=1,
            file=File(
                stored_path=f"{title}.pdf",
                original_name=f"{title}.pdf",
                content_type="application/pdf",
            ),
        )
    )
    session.add(library_document)
    await session.flush()
    return library_document


async def test_library_page_has_empty_state_and_global_navigation(
    client: AsyncClient,
) -> None:
    """The empty Library page is reachable from the persistent header link."""
    response = await client.get("/library")

    assert response.status_code == 200
    assert "No library documents yet." in response.text
    assert "data-list-filter" not in response.text
    assert "No library documents match your search." not in response.text
    assert 'href="/">PROJECTS</a>' in response.text
    assert 'href="/library">LIBRARY</a>' in response.text
    assert ">+ Add Library Document</button>" in response.text


async def test_library_page_populated_filter_uses_title_only(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A populated Library list exposes the shared title-only filter contract."""
    library_document = await add_library_document(session, "Safety Manual")
    library_document.description = "Internal document description"
    library_document.current_version.version_note = "Initial issue note"
    await session.commit()

    response = await client.get("/library")

    body = response.text
    search_text = re.search(
        r'<tr[^>]*data-list-filter-text="([^"]+)"',
        body,
    )
    assert response.status_code == 200
    assert 'class="list-filter" data-list-filter' in body
    assert 'data-list-filter-count aria-live="polite">Showing all 1</p>' in body
    assert 'id="library-document-search"' in body
    assert 'aria-controls="library-document-table"' in body
    assert 'data-list-filter-input' in body
    assert body.index('data-list-filter-input') < body.index('+ Add Library Document')
    assert 'id="library-document-table" data-list-filter-table' in body
    assert search_text is not None
    assert search_text.group(1) == "Safety Manual"
    assert 'data-list-filter-no-results hidden' in body
    assert "No library documents match your search." in body
    assert "Search by title." in body


async def test_library_page_lists_alphabetically_with_current_version_and_updated(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Each Library row has its title, current version, updated date, and link."""
    zulu = await add_library_document(session, "Zulu Form")
    alpha = await add_library_document(session, "Alpha Form")
    await session.commit()

    response = await client.get("/library")

    assert response.status_code == 200
    body = response.text
    assert body.index("Alpha Form") < body.index("Zulu Form")
    assert "Version 1" in body
    assert alpha.updated_at.strftime("%Y-%m-%d") in body
    assert f'data-row-href="/library-documents/{alpha.id}"' in body
    assert f'data-row-href="/library-documents/{zulu.id}"' in body
