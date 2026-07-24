from __future__ import annotations

from httpx import AsyncClient


async def create_library_document(client: AsyncClient) -> dict[str, object]:
    """Create a document whose initial version is a previewable PDF."""
    response = await client.post(
        "/api/library-documents",
        data={"title": "Mix Design Specification", "version_note": "Initial"},
        files={"file": ("mix-v1.pdf", b"version one", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def add_library_document_version(
    client: AsyncClient,
    library_document_id: int,
) -> dict[str, object]:
    """Create a second, download-only version for the detail timeline."""
    response = await client.post(
        f"/api/library-documents/{library_document_id}/versions",
        data={"version_note": "Corrected dimensions"},
        files={"file": ("mix-v2.csv", b"spec,updated", "text/csv")},
    )
    assert response.status_code == 201
    return response.json()


async def test_detail_page_defaults_to_newest_and_prerenders_historical_panes(
    client: AsyncClient,
) -> None:
    """Timeline buttons switch pre-rendered current and historical file panes."""
    document = await create_library_document(client)
    current_version = await add_library_document_version(client, document["id"])

    response = await client.get(f"/library-documents/{document['id']}")

    assert response.status_code == 200
    body = response.text
    assert 'data-doc-preview' in body
    assert 'data-doc-historical-banner hidden' in body
    assert "VIEWING PAST REVISION — NOT THE CURRENT STATE OF THIS LIBRARY DOCUMENT." in body
    assert f'data-doc-pane="{current_version["id"]}"' in body
    assert f'data-doc-pane="{document["current_version"]["id"]}" hidden' in body
    assert f'data-doc-version="{current_version["id"]}"' in body
    assert f'data-doc-version="{document["current_version"]["id"]}"' in body
    assert body.index("VERSION 2") < body.index("VERSION 1")
    assert "Corrected dimensions" in body
    assert f'/api/files/{current_version["file"]["id"]}?download=1' in body
    assert "CANNOT PREVIEW INLINE" in body


async def test_detail_page_returns_404_for_unknown_document(client: AsyncClient) -> None:
    """The Library Document detail route does not render an empty shell."""
    response = await client.get("/library-documents/999")

    assert response.status_code == 404


async def test_detail_page_keeps_metadata_editable_and_current_note_inline(
    client: AsyncClient,
) -> None:
    """Metadata actions share the header and the current note saves inline."""
    document = await create_library_document(client)
    current_version = await add_library_document_version(client, document["id"])

    update_response = await client.patch(
        f"/api/library-documents/{document['id']}",
        json={"title": "Renamed Mix Design"},
    )
    response = await client.get(f"/library-documents/{document['id']}")

    assert update_response.status_code == 200
    assert response.status_code == 200
    body = response.text
    assert "Renamed Mix Design" in body
    assert f'data-url="/api/library-documents/{document["id"]}"' in body
    assert 'data-prefill=' in body
    assert (
        f'data-notes-url="/api/library-documents/{document["id"]}/versions/'
        f'{current_version["id"]}"'
    ) in body
    assert 'data-notes-field="version_note"' in body
    assert "Corrected dimensions" in body
    assert body.index('class="h1-detail"') < body.index('data-modal-open="library-document-modal"')
    delete_start = body.rfind("<button", 0, body.index('data-modal-open="delete-library-document-modal"'))
    delete_button = body[delete_start : body.index(">Delete</button>", delete_start)]
    assert 'btn-row-danger' in delete_button
    assert 'data-method="DELETE"' in delete_button
    assert 'data-redirect="/library"' in delete_button
    assert 'data-modal="delete-library-document-modal"' in body
    assert 'data-modal-error hidden' in body
